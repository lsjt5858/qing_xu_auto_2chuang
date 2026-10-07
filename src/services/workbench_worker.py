"""One-task, non-interactive video worker.

Run: python -m src.services.workbench_worker input.json result.json events.jsonl

Only a successful run publishes result.json (atomically, without replacement).
Exit 0 means completed or hard-skipped; exit 1 means failure, with details on
stderr and in the append-only, flushed UTC events log. stdout is not a protocol.
The caller must use a fresh result path for each attempt and retain workDir.

All returned paths are absolute. Analysis updates use original-source seconds,
stable "<materialId>:scene:<number>" IDs, and status "analyzed". A hard skip
requires a readable report whose source path or content identity matches the input.
newMaterials contains only existing shot files; the parent assigns their IDs.
Mix outputs link to the first plan clip's materialId. Preview duration/size and
dimensions are probed; draft path is a directory and its size excludes workDir.

Steps are executed in CLI order, not request order. Semantic implies scenes.
Complete reports can be reused; semantic completion writes a new report and
never modifies the old one. The existing-target hard skip always wins.
preserveLongShots never introduces a duration cap: native real-cut detection
retains long shots even when the UI preference is false.

Mix preserves every planned clip and explicit source offset, rejecting ranges
past EOF. The existing renderer rounds timings to 30 fps. Canvas follows the
first source, even-sized, without upscaling, within 1920x1080 or 1080x1920.
Draft-only requests still render internally to retain the identical timeline
and audio. Explicit draftDirectory is mandatory; no interactive discovery runs.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


def _number(value, name, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'non-negative'}")
    return value


def _path(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an explicit non-empty path")
    return Path(value).expanduser().absolute()


def _read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _write_json(path, value):
    with Path(path).open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _file_identity(path):
    path = Path(path)
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return {"sizeBytes": path.stat().st_size, "sha256": hasher.hexdigest()}


def _report_matches_source(report, report_path, source, source_identity):
    source = source.absolute()
    original = report.get("original_video_path")
    declared_paths = set()
    if isinstance(original, str) and original.strip():
        path = Path(original).expanduser()
        declared_paths = {path.absolute(), (Path(report_path).parent / path).absolute()}
        existing_declared = {path for path in declared_paths if path.is_file()}
        if existing_declared and source not in existing_declared:
            return False

    metadata = report.get("workbench", {})
    identity = metadata.get("sourceIdentity") if isinstance(metadata, dict) else None
    return isinstance(identity, dict) and identity == source_identity


def _publish_result(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".worker-result-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink()


def _probe(path):
    from src.models import probe_media

    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing or empty media: {path}")
    try:
        metadata = probe_media(path)
    except FileNotFoundError as exc:
        raise RuntimeError("Install ffmpeg and ffprobe and put them on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe failed for {path}: {(exc.stderr or '')[-2000:]}") from exc
    if metadata.duration_us <= 0:
        raise ValueError(f"Media has no positive duration: {path}")
    return metadata


def _canvas(width, height):
    if width < 2 or height < 2:
        raise ValueError("First material has no usable video dimensions")
    scale = min(1, 1920 / max(width, height), 1080 / min(width, height))
    return max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)


def _analysis_directory(root, stem):
    # Preserve the CLI's exact timestamp pattern, reserving with exclusive mkdir.
    stamp = datetime.now().replace(microsecond=0)
    while True:
        directory = root / f"{stem}_{stamp:%Y%m%d_%H%M%S}"
        try:
            directory.mkdir()
            return directory
        except FileExistsError:
            stamp += timedelta(seconds=1)


def _material_update(material, report, report_path):
    scenes = []
    for index, scene in enumerate(report.get("scenes") or [], 1):
        start = _number(scene["start_time"], "scene.start_time")
        duration = scene.get("duration")
        if duration is None:
            duration = scene["end_time"] - start
        _number(duration, "scene.duration", positive=True)
        scenes.append({
            "id": f"{material['id']}:scene:{index}",
            "startSeconds": start, "durationSeconds": duration,
        })
    transcript = []
    for segment in report.get("transcript_segments") or []:
        start = _number(segment["start"], "transcript.start")
        if not isinstance(segment["text"], str):
            raise ValueError("transcript.text must be a string")
        transcript.append({"startSeconds": start, "text": segment["text"]})
    return {
        "id": material["id"], "scenes": scenes, "transcript": transcript,
        "status": "analyzed", "reportPath": str(report_path.absolute()),
    }


def _load_report(path, material, emit):
    if not path.is_file():
        return None
    try:
        report = _read_json(path)
        if not isinstance(report, dict):
            raise ValueError("report must be an object")
        metadata = report.get("workbench", {})
        if not isinstance(metadata, dict) or not isinstance(metadata.get("completedSteps", []), list):
            raise ValueError("Invalid workbench report metadata")
        for key in ("scenes", "transcript_segments", "semantic_scenes"):
            if key in report and not isinstance(report[key], list):
                raise ValueError(f"report.{key} must be a list")
        _material_update(material, report, path)
        return report
    except (OSError, ValueError, KeyError, TypeError) as exc:
        emit(f"report ignored: {path}: {exc}")
        return None


def _report_paths(material, source, output_root):
    candidates = []
    if material.get("reportPath"):
        candidates.append(_path(material["reportPath"], "reportPath"))
    pattern = re.compile(rf"{re.escape(source.stem)}_\d{{8}}_\d{{6}}")
    candidates.extend(
        directory / "report.json"
        for directory in sorted(output_root.iterdir(), reverse=True)
        if directory.is_dir() and pattern.fullmatch(directory.name)
    )
    return list(dict.fromkeys(candidates))


def _existing_target_candidates(source, output_root):
    pattern = re.compile(rf"{re.escape(source.stem)}_\d{{8}}_\d{{6}}")
    if not output_root.is_dir():
        return []
    return [
        directory / "video_no_subtitles.mp4"
        for directory in sorted(output_root.iterdir(), reverse=True)
        if directory.is_dir()
        and pattern.fullmatch(directory.name)
        and (directory / "video_no_subtitles.mp4").is_file()
    ]


def _report_video(report, report_path, source):
    for key in ("processed_video_path", "original_video_path"):
        value = report.get(key)
        if isinstance(value, str) and value:
            path = Path(value).expanduser()
            for candidate in (path.absolute(), (report_path.parent / path).absolute()):
                if candidate.is_file():
                    return candidate
    return source


def _base_complete(report, steps, threshold, model):
    recorded = report.get("workbench", {})
    completed = recorded.get("completedSteps", [])
    if "clean" in steps and not (
        "clean" in completed or report.get("subtitle_removed") is True
    ):
        return False
    if "scenes" in steps or "semantic" in steps:
        if not report.get("scenes"):
            return False
        config = report.get("scene_detection")
        if "scenes" in steps and (
            not isinstance(config, dict) or config.get("content_threshold") != threshold
        ):
            return False
    if "transcribe" in steps:
        if not isinstance(report.get("transcript_segments"), list):
            return False
        if not isinstance(report.get("transcript"), str) and "transcribe" not in completed:
            return False
        if recorded.get("transcriptionModel", model) != model:
            return False
    return True


def _semantic_complete(report):
    groups = report.get("semantic_scenes")
    return bool(groups) and all(
        isinstance(group, dict) and isinstance(group.get("output_path"), str)
        and Path(group["output_path"]).is_file() and Path(group["output_path"]).stat().st_size > 0
        for group in groups
    )


def _with_semantic_sidecar(report, directory, emit):
    if _semantic_complete(report):
        return report
    path = directory / "semantic_scenes.json"
    if not path.is_file():
        return report
    try:
        groups = _read_json(path)
        if not isinstance(groups, list):
            raise ValueError("semantic sidecar must be a list")
        candidate = dict(report, semantic_scenes=groups, semantic_scene_count=len(groups))
        if not _semantic_complete(candidate):
            raise ValueError("semantic sidecar outputs are incomplete")
        return candidate
    except (OSError, ValueError, TypeError) as exc:
        emit(f"semantic sidecar ignored: {path}: {exc}")
        return report


def _shots(report, directory, category, *, strict=False, semantic=False):
    records = report.get("semantic_scenes" if semantic else "scenes") or []
    folder = directory / ("semantic_scenes" if semantic else "scenes")
    paths = sorted(folder.glob("SemanticScene-*.mp4" if semantic else "Scene-*.mp4"))
    if semantic:
        paths = [Path(item["output_path"]).absolute() for item in records]
    if strict and (not records or len(paths) != len(records)):
        raise RuntimeError(f"Scene split did not produce all expected files: {folder}")
    result = []
    for index, path in enumerate(paths):
        if not path.is_file():
            if strict:
                raise FileNotFoundError(f"Missing shot: {path}")
            continue
        duration = None
        if strict:
            metadata = _probe(path)
            if not metadata.width or not metadata.height:
                raise ValueError(f"Shot has no video stream: {path}")
            duration = metadata.duration_us / 1_000_000
        elif index < len(records):
            duration = records[index].get("duration")
        item = {"name": path.name, "kind": "shot", "path": str(path.absolute()),
                "category": "semantic" if semantic else category}
        if duration is not None:
            item["durationSeconds"] = duration
        result.append(item)
    return result


def _semantic(report, directory, video, emit):
    from src.core.semantic_scene_grouper import SemanticSceneGrouper

    emit(f"semantic: {video.name}")
    groups = SemanticSceneGrouper.from_config().group_and_export(
        str(video), report["scenes"], report.get("transcript_segments") or [], str(directory),
    )
    report["semantic_scenes"] = groups
    report["semantic_scene_count"] = len(groups)
    shots = _shots(report, directory, "semantic", strict=True, semantic=True)
    report.setdefault("workbench", {}).setdefault("completedSteps", []).append("semantic")
    _write_json(directory / "report.json", report)
    return shots


def _analyze_one(material, source, task, settings, work, output_root, emit):
    # PySceneDetect imports MoviePy's optional backend, which probes ffplay.
    # Like AudioExtractor, keep this unused GUI probe out of the worker.
    os.environ.setdefault("FFPLAY_BINARY", "ffmpeg")

    steps = task["steps"]
    threshold = task.get("threshold", 27.0)
    category = material.get("category") or "scenes"
    source_identity = _file_identity(source)
    emit(f"checking existing target: {source.name}")
    for existing in _existing_target_candidates(source, output_root):
        report_path = existing.parent / "report.json"
        report = _load_report(report_path, material, emit)
        if report is not None and _report_matches_source(
            report, report_path, source, source_identity
        ):
            emit(f"skipped: target already exists: {existing}")
            return True, _material_update(material, report, report_path), []
        emit(f"existing target ignored: source identity does not match: {existing}")

    model = settings.get("transcriptionModel", "base")
    reuse = settings.get("reuseAnalysis", False)
    if reuse or "semantic" in steps:
        for report_path in _report_paths(material, source, output_root):
            report = _load_report(report_path, material, emit)
            if (report is None or not _report_matches_source(
                    report, report_path, source, source_identity)
                    or not _base_complete(report, steps, threshold, model)):
                continue
            video = _report_video(report, report_path, source)
            if "clean" in steps and report.get("subtitle_removed") and video == source:
                continue
            if "semantic" in steps:
                report = _with_semantic_sidecar(report, report_path.parent, emit)
            if "semantic" not in steps or _semantic_complete(report):
                if not reuse and "semantic" not in steps:
                    continue
                emit(f"reusing complete report: {report_path}")
                shots = _shots(report, report_path.parent, category)
                shots += _shots(report, report_path.parent, category, semantic=True)
                return False, _material_update(material, report, report_path), shots
            emit(f"reusing base report for semantic: {report_path}")
            directory = _analysis_directory(output_root, source.stem)
            # Copy only analysis assets, not arbitrary files from the old directory.
            if (report_path.parent / "scenes").is_dir():
                shutil.copytree(report_path.parent / "scenes", directory / "scenes")
            for name in ("audio.mp3", "transcript.txt", "transcript_detailed.json"):
                old = report_path.parent / name
                if old.is_file():
                    shutil.copy2(old, directory / name)
            report["output_directory"] = str(directory)
            report.setdefault("scene_detection", None)
            report["semantic_scenes"] = []
            report["semantic_scene_count"] = 0
            _write_json(directory / "report.json", report)
            shots = _shots(report, directory, category)
            shots += _semantic(report, directory, video, emit)
            return False, _material_update(material, report, directory / "report.json"), shots

    from src.core.video_analyzer import VideoAnalyzer

    # Isolate the legacy constructor's exist_ok=True timestamp directory before
    # redirecting all work into an exclusively reserved, CLI-discoverable folder.
    scratch = Path(tempfile.mkdtemp(prefix="analysis-", dir=work))
    analyzer = VideoAnalyzer(str(source), str(scratch))
    directory = _analysis_directory(output_root, source.stem)
    analyzer.output_dir = str(directory)
    scenes = None
    transcript = None
    completed = []
    if "clean" in steps:
        emit(f"clean: {source.name}")
        analyzer.remove_subtitles()
        _probe(Path(analyzer.video_path))
        completed.append("clean")
    shots = []
    if "scenes" in steps or "semantic" in steps:
        emit(f"scenes: {source.name}; threshold={threshold}; retaining full shots")
        scenes = analyzer.analyze_scenes(threshold)
        shots = _shots({"scenes": scenes}, directory, category, strict=True)
        completed.append("scenes")
    if "transcribe" in steps:
        emit(f"extract audio: {source.name}")
        audio = analyzer.extract_audio()
        if audio:
            emit(f"transcribe: {source.name}; model={model}")
            transcript = analyzer.transcribe_audio(audio, model)
            if not isinstance(transcript, dict) or not isinstance(transcript.get("segments"), list):
                raise RuntimeError("Transcription did not return a valid result")
        else:
            # None may mean "no audio", but must not mask an extraction failure.
            if _probe(Path(analyzer.video_path)).has_audio:
                raise RuntimeError(f"Audio extraction produced no file: {source}")
            emit(f"transcribe: no audio track: {source.name}")
        completed.append("transcribe")
    emit(f"report: saving base analysis for {source.name}")
    report = analyzer.generate_report(scenes, transcript)
    report["workbench"] = {
        "completedSteps": completed,
        "transcriptionModel": model,
        "sourceIdentity": source_identity,
    }
    _material_update(material, report, directory / "report.json")
    _write_json(directory / "report.json", report)
    if "semantic" in steps:
        shots += _semantic(report, directory, Path(analyzer.video_path), emit)
    return False, _material_update(material, report, directory / "report.json"), shots


def _mix(task, materials, paths, settings, work, output_root, emit):
    from src.models import AnalysisArtifacts, TimelineClip
    from src.exporters.video import render_timeline

    requested = task["requestedOutputs"]
    draft_root = None
    if "draft" in requested:
        draft_root = _path(settings.get("draftDirectory"), "settings.draftDirectory")
        draft_root.mkdir(parents=True, exist_ok=True)
        if not draft_root.is_dir():
            raise ValueError("draftDirectory must be a directory")
    clips = []
    cursor = 0
    metadata = {}
    emit("mix: validating the frozen plan")
    for item in task["plan"]["clips"]:
        source = paths[item["materialId"]]
        if source not in metadata:
            metadata[source] = _probe(source)
        info = metadata[source]
        if info.width < 2 or info.height < 2:
            raise ValueError(f"Material has no video stream: {source}")
        start = round(_number(item.get("sourceStartSeconds", 0), "sourceStartSeconds") * 1_000_000)
        duration = round(_number(item.get("durationSeconds"), "durationSeconds",
                                 positive=True) * 1_000_000)
        if duration < 1 or start + duration > info.duration_us:
            raise ValueError(f"Plan duration exceeds source duration or is too small: {source}")
        clips.append(TimelineClip(
            source_path=source, timeline_start_us=cursor, timeline_duration_us=duration,
            source_start_us=start, source_duration_us=duration, label=item.get("label", source.name),
        ))
        cursor += duration
    first = metadata[clips[0].source_path]
    width, height = _canvas(first.width, first.height)
    run = Path(tempfile.mkdtemp(prefix="mix-", dir=work))
    _write_json(run / "plan.json", task["plan"])
    if "preview" in requested:
        destination = Path(tempfile.mkdtemp(prefix="mix-", dir=output_root)) / "preview.mp4"
    else:
        destination = run / "preview.mp4"
    emit(f"render: {len(clips)} full plan clips; {width}x{height}")
    rendered = render_timeline(clips, destination, work_dir=run, width=width, height=height)
    info = _probe(rendered.video_path)
    first_id = task["plan"]["clips"][0]["materialId"]
    outputs = []
    if "preview" in requested:
        outputs.append({
            "name": rendered.video_path.name, "kind": "preview",
            "path": str(rendered.video_path), "durationSeconds": info.duration_us / 1_000_000,
            "sizeBytes": rendered.video_path.stat().st_size,
            "width": info.width, "height": info.height, "materialId": first_id,
        })
    if draft_root is not None:
        from src.exporters import export_to_jianying_draft

        emit(f"draft: exporting to {draft_root}")
        artifacts = AnalysisArtifacts(
            output_dir=run, video_name=str(task.get("name") or "workbench"),
            original_video_path=rendered.video_path, processed_video_path=rendered.video_path,
            report_path=None, audio_path=rendered.audio_path,
            audio_metadata=_probe(rendered.audio_path), scenes=(), transcript_segments=(),
        )
        draft = export_to_jianying_draft(
            artifacts, timeline_clips=list(rendered.clips), draft_root=draft_root,
            draft_name=f"workbench_{run.name}", style_template="basic",
        )
        content = _read_json(draft / "draft_info.json")
        duration = _number(content["duration"], "draft.duration", positive=True) / 1_000_000
        outputs.append({
            "name": draft.name, "kind": "draft", "path": str(draft),
            "durationSeconds": duration, "width": info.width, "height": info.height,
            "sizeBytes": sum(path.stat().st_size for path in draft.rglob("*") if path.is_file()),
            "materialId": first_id,
        })
    return outputs


def run_task(payload, emit):
    """Execute a decoded request; raise on any failed stage, never fake success."""
    if not isinstance(payload, dict):
        raise ValueError("input must be an object")
    task, settings = payload.get("task"), payload.get("settings")
    if not isinstance(task, dict) or task.get("kind") not in ("analysis", "mix"):
        raise ValueError("task.kind must be analysis or mix")
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    raw_work = payload.get("workDir")
    work = _path(raw_work, "workDir")
    if not Path(raw_work).expanduser().is_absolute():
        raise ValueError("workDir must be absolute and persistent")
    output_root = _path(settings.get("outputDirectory"), "settings.outputDirectory")
    steps = task.get("steps", [])
    if not isinstance(steps, list) or any(step not in ("clean", "scenes", "transcribe", "semantic")
                                         for step in steps):
        raise ValueError("task.steps must contain clean, scenes, transcribe or semantic")
    task = dict(task, steps=steps)
    requested = task.get("requestedOutputs", [])
    if not isinstance(requested, list) or any(kind not in ("preview", "draft") for kind in requested):
        raise ValueError("requestedOutputs only supports preview and draft")
    task["requestedOutputs"] = list(dict.fromkeys(requested))
    if task["kind"] == "analysis":
        if not steps:
            raise ValueError("analysis requires at least one step")
        if requested:
            raise ValueError("analysis does not export mix outputs; submit a mix task")
        threshold = _number(task.get("threshold", 27.0), "threshold")
        if threshold > 255:
            raise ValueError("threshold must be between 0 and 255")
    elif not requested:
        raise ValueError("mix requires at least one requested output")
    for flag in ("reuseAnalysis", "preserveLongShots"):
        if flag in settings and type(settings[flag]) is not bool:
            raise ValueError(f"settings.{flag} must be a boolean")
    if settings.get("transcriptionModel", "base") not in ("tiny", "base", "small", "medium", "large"):
        raise ValueError("Unsupported transcriptionModel")
    entries = payload.get("materials")
    if not isinstance(entries, list):
        raise ValueError("materials must be a list")
    materials = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise ValueError("Each material requires a string id")
        if entry["id"] in materials:
            raise ValueError(f"Duplicate material id: {entry['id']}")
        materials[entry["id"]] = entry
    ids = task.get("materialIds")
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
        raise ValueError("task.materialIds must be a non-empty list of ids")
    if len(set(ids)) != len(ids) or any(i not in materials for i in ids):
        raise ValueError("task.materialIds contains unknown or duplicate ids")
    if task["kind"] == "mix":
        plan = task.get("plan")
        if not isinstance(plan, dict) or not isinstance(plan.get("clips"), list) or not plan["clips"]:
            raise ValueError("mix requires a non-empty plan.clips")
        for clip in plan["clips"]:
            if not isinstance(clip, dict) or clip.get("materialId") not in ids:
                raise ValueError("plan clip materialId must be in task.materialIds")
        if "draft" in requested:
            _path(settings.get("draftDirectory"), "settings.draftDirectory")
    paths = {}
    for material_id in ids:
        source = _path(materials[material_id].get("path"), f"material {material_id} path")
        if not source.is_file():
            raise FileNotFoundError(f"Source material does not exist: {source}")
        paths[material_id] = source
    work.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    result = {"status": "completed", "stage": "completed",
              "materialUpdates": [], "newMaterials": [], "outputs": []}
    if task["kind"] == "mix":
        result["outputs"] = _mix(task, materials, paths, settings, work, output_root, emit)
    else:
        skipped = []
        for material_id in ids:
            skip, update, shots = _analyze_one(
                materials[material_id], paths[material_id], task, settings, work, output_root, emit,
            )
            skipped.append(skip)
            result["materialUpdates"].append(update)
            result["newMaterials"].extend(shots)
        if all(skipped):
            result.update(status="skipped", stage="skipped_existing_target")
    return result


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        print("Usage: python -m src.services.workbench_worker <input.json> <result.json> "
              "<events.jsonl>", file=sys.stderr)
        return 1
    stream = None

    def emit(message):
        if stream is not None:
            stream.write(json.dumps({
                "at": datetime.now(timezone.utc).isoformat(), "message": message,
            }, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()

    try:
        input_path, result_path, events_path = [_path(arg, "protocol path") for arg in args]
        paths = (input_path, result_path, events_path)
        for index, path in enumerate(paths):
            for other in paths[index + 1:]:
                if path.resolve() == other.resolve() or (
                    path.exists() and other.exists() and path.samefile(other)
                ):
                    raise ValueError("input, result and events paths must be distinct")
        if result_path.exists() or result_path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite result: {result_path}")
        start_gate = os.environ.get("WORKBENCH_START_GATE")
        if start_gate:
            deadline = time.monotonic() + 30
            while not Path(start_gate).is_file():
                if time.monotonic() >= deadline:
                    raise RuntimeError("service did not authorize this worker attempt")
                time.sleep(0.05)
        events_path.parent.mkdir(parents=True, exist_ok=True)
        stream = events_path.open("a", encoding="utf-8")
        emit("worker: started")
        payload = _read_json(input_path)
        with redirect_stdout(sys.stderr):
            result = run_task(payload, emit)
        emit(f"worker: {result['stage']}")
        _publish_result(result_path, result)
        return 0
    except Exception as exc:
        message = f"worker failed: {type(exc).__name__}: {exc}"
        print(message, file=sys.stderr)
        try:
            emit(message)
        except OSError:
            pass
        return 1
    finally:
        if stream is not None:
            stream.close()


if __name__ == "__main__":
    raise SystemExit(main())
