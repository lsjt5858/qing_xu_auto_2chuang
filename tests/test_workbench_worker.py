from __future__ import annotations

from contextlib import contextmanager, redirect_stderr
from datetime import datetime
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def worker():
    try:
        return importlib.import_module("src.services.workbench_worker")
    except ModuleNotFoundError as exc:
        raise AssertionError("The workbench worker is not implemented") from exc


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value), encoding="utf-8")


class WorkerCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="workbench-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "original name's.mp4"
        self.source.write_bytes(b"test input, not real media")
        self.payload = {
            "task": {
                "id": "task-1", "name": "Example", "kind": "analysis",
                "materialIds": ["m1"], "steps": ["scenes"], "threshold": 27,
                "requestedOutputs": [],
            },
            "materials": [{
                "id": "m1", "name": self.source.name, "path": str(self.source),
                "durationSeconds": 4, "category": "local", "status": "pending",
            }],
            "settings": {
                "sourceDirectory": str(self.root),
                "outputDirectory": str(self.root / "output"),
                "draftDirectory": "", "transcriptionModel": "tiny",
                "reuseAnalysis": True, "preserveLongShots": True,
            },
            "workDir": str(self.root / "work"),
        }
        self.input = self.root / "input.json"
        self.result = self.root / "result.json"
        self.events = self.root / "events.jsonl"

    def execute(self):
        write_json(self.input, self.payload)
        with redirect_stderr(io.StringIO()):
            return worker().main([str(self.input), str(self.result), str(self.events)])

    def invoke(self, *, expected=0):
        write_json(self.input, self.payload)
        environment = dict(os.environ)
        environment.pop("FFPLAY_BINARY", None)
        process = subprocess.run(
            [sys.executable, "-m", "src.services.workbench_worker",
             str(self.input), str(self.result), str(self.events)],
            cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=120, env=environment,
        )
        self.assertEqual(process.returncode, expected, process.stderr)
        return process

    def cache(self, *, target=False, transcript=True):
        directory = self.root / "output" / f"{self.source.stem}_20261001_120000"
        directory.mkdir(parents=True)
        if target:
            (directory / "video_no_subtitles.mp4").write_bytes(b"existing target")
        report = {
            "video_name": self.source.stem,
            "original_video_path": str(self.source),
            "processed_video_path": str(self.source),
            "output_directory": str(directory),
            "subtitle_removed": False,
            "scene_detection": {"detector_type": "adaptive", "content_threshold": 27},
            "scenes": [
                {"scene_number": 1, "start_time": 0, "end_time": 4, "duration": 4},
            ],
            "total_scenes": 1,
            "transcript": "hello" if transcript else None,
            "transcript_segments": [{"start": 0.5, "end": 1, "text": "hello"}]
            if transcript else [],
            "semantic_scene_count": 0, "semantic_scenes": [],
            "workbench": {
                "completedSteps": ["scenes"] + (["transcribe"] if transcript else []),
                "transcriptionModel": "tiny",
                "sourceIdentity": {
                    "sizeBytes": self.source.stat().st_size,
                    "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
                },
            },
        }
        write_json(directory / "report.json", report)
        return directory

    def mix(self, outputs=("preview",)):
        self.payload["task"].update(
            kind="mix", steps=[], requestedOutputs=list(outputs),
            plan={"clips": [{"materialId": "m1", "label": "first", "durationSeconds": 4}]},
        )


class TestWorkerProtocol(WorkerCase):
    def test_canvas_even_no_upscale_and_1080_class_limit(self):
        for source, expected in [
            ((3840, 2160), (1920, 1080)), ((2160, 3840), (1080, 1920)),
            ((3000, 3000), (1080, 1080)), ((4000, 1000), (1920, 480)),
            ((95, 159), (94, 158)), ((96, 160), (96, 160)),
        ]:
            with self.subTest(source=source):
                self.assertEqual(worker()._canvas(*source), expected)

    def test_import_is_lightweight(self):
        process = subprocess.run(
            [sys.executable, "-S", "-c",
             "import sys; import src.services.workbench_worker; "
             "print([m for m in ('cv2','whisper','torch','moviepy','scenedetect',"
             "'src.core.video_analyzer','src.utils.batch_processor') if m in sys.modules])"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout.strip(), "[]")

    def test_invalid_task_exits_nonzero_with_no_result(self):
        self.payload["task"]["kind"] = "unsupported"
        process = self.invoke(expected=1)
        self.assertIn("kind", process.stderr)
        self.assertFalse(self.result.exists())
        events = [json.loads(line) for line in self.events.read_text().splitlines()]
        self.assertIn("failed", events[-1]["message"].lower())
        for event in events:
            self.assertEqual(set(event), {"at", "message"})
            self.assertIsNotNone(datetime.fromisoformat(event["at"]).tzinfo)

    def test_protocol_paths_must_be_distinct(self):
        write_json(self.input, self.payload)
        before = self.input.read_bytes()
        self.assertEqual(worker().main([str(self.input), str(self.input), str(self.events)]), 1)
        self.assertEqual(self.input.read_bytes(), before)

    def test_existing_result_is_not_overwritten(self):
        self.result.write_bytes(b"existing")
        self.assertEqual(self.execute(), 1)
        self.assertEqual(self.result.read_bytes(), b"existing")

    def test_result_symlink_is_not_followed(self):
        target = self.root / "absent.json"
        self.result.symlink_to(target)
        self.assertEqual(self.execute(), 1)
        self.assertFalse(target.exists())

    def test_result_publication_is_exclusive_even_if_racing(self):
        module = worker()
        with patch.object(module.os, "link", side_effect=FileExistsError("racing writer")):
            with self.assertRaises(FileExistsError):
                module._publish_result(self.result, {"status": "completed"})
        self.assertFalse(self.result.exists())
        self.assertEqual(list(self.root.glob(".worker-result-*")), [])

    def test_analysis_directory_collision_keeps_existing_results(self):
        module = worker()
        directory = self.root / "output"
        directory.mkdir()
        with patch.object(module, "datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 7, 12)
            first = module._analysis_directory(directory, "original")
            (first / "report.json").write_bytes(b"unchanged")
            second = module._analysis_directory(directory, "original")
        self.assertNotEqual(first, second)
        self.assertEqual((first / "report.json").read_bytes(), b"unchanged")

    def test_invalid_numeric_options_fail_without_output(self):
        for value in (-1, float("nan"), float("inf"), True, "27", 256):
            with self.subTest(value=value):
                self.payload["task"]["threshold"] = value
                self.assertEqual(self.execute(), 1)
                self.assertFalse(self.result.exists())

    def test_malformed_json_reports_failure_and_keeps_existing_events(self):
        self.input.write_text("{broken", encoding="utf-8")
        self.events.write_text('{"at":"old","message":"previous attempt"}\n', encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            code = worker().main([str(self.input), str(self.result), str(self.events)])
        self.assertEqual(code, 1)
        self.assertFalse(self.result.exists())
        self.assertEqual(json.loads(self.events.read_text().splitlines()[0])["at"], "old")

    def test_relative_workdir_fails_before_processing(self):
        self.payload["workDir"] = "relative-work"
        process = self.invoke(expected=1)
        self.assertIn("workDir", process.stderr)
        self.assertFalse(self.result.exists())

    def test_missing_source_fails_even_when_target_exists(self):
        self.cache(target=True)
        self.source.unlink()
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.result.exists())

    def test_unknown_material_and_unknown_step_fail(self):
        for key, value in (("materialIds", ["missing"]), ("steps", ["bogus"])):
            with self.subTest(key=key):
                original = self.payload["task"][key]
                self.payload["task"][key] = value
                self.assertEqual(self.execute(), 1)
                self.assertFalse(self.result.exists())
                self.payload["task"][key] = original

    def test_hard_skip_precedes_every_stage_and_reuse_setting(self):
        directory = self.cache(target=True)
        before = (directory / "report.json").read_bytes()
        self.payload["task"]["steps"] = ["semantic", "transcribe", "scenes", "clean"]
        self.payload["settings"]["reuseAnalysis"] = False
        module = worker()
        with patch.object(
                module, "_existing_target_candidates",
                wraps=module._existing_target_candidates,
        ) as finder, \
                patch("src.core.video_analyzer.VideoAnalyzer", side_effect=AssertionError), \
                patch("src.core.semantic_scene_grouper.SemanticSceneGrouper.from_config",
                      side_effect=AssertionError):
            self.assertEqual(self.execute(), 0)
        finder.assert_called_once()
        self.assertEqual(Path(finder.call_args.args[0]).name, self.source.name)
        result = read_json(self.result)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["outputs"], [])
        self.assertEqual(result["materialUpdates"][0]["scenes"],
                         [{"id": "m1:scene:1", "startSeconds": 0, "durationSeconds": 4}])
        self.assertEqual((directory / "report.json").read_bytes(), before)

    def test_hard_skip_does_not_trust_a_target_with_invalid_identity_report(self):
        directory = self.cache(target=True)
        (directory / "report.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.result.exists())

    def test_complete_report_reused_without_pipeline(self):
        directory = self.cache()
        self.payload["task"]["steps"] = ["transcribe", "scenes"]
        with patch("src.core.video_analyzer.VideoAnalyzer", side_effect=AssertionError):
            self.assertEqual(self.execute(), 0)
        result = read_json(self.result)
        self.assertEqual(result["status"], "completed")
        update = result["materialUpdates"][0]
        self.assertEqual(update["reportPath"], str(directory / "report.json"))
        self.assertEqual(update["transcript"], [{"startSeconds": 0.5, "text": "hello"}])

    def test_draft_requires_explicit_directory_before_render_or_input(self):
        self.mix(("draft",))
        with patch("builtins.input", side_effect=AssertionError), \
                patch("src.exporters.video.render_timeline", side_effect=AssertionError):
            self.assertEqual(self.execute(), 1)
        self.assertFalse(self.result.exists())
        self.assertIn("draftDirectory", self.events.read_text())


class TestWorkerAnalysis(WorkerCase):
    def test_legacy_report_without_content_identity_is_not_reused(self):
        worker()
        directory = self.cache(target=True)
        report = read_json(directory / "report.json")
        report.pop("workbench")
        write_json(directory / "report.json", report)
        with self.analyzer() as calls:
            self.assertEqual(self.execute(), 0)
        self.assertIn(("scenes", 27), calls)
        self.assertEqual(read_json(self.result)["status"], "completed")

    def test_same_stem_cache_from_another_source_is_not_reused(self):
        worker()
        directory = self.cache(target=True)
        report = read_json(directory / "report.json")
        other = self.root / "other" / self.source.name
        other.parent.mkdir()
        other.write_bytes(b"different source")
        report["original_video_path"] = str(other)
        report["processed_video_path"] = str(other)
        write_json(directory / "report.json", report)
        with self.analyzer() as calls:
            self.assertEqual(self.execute(), 0)
        self.assertIn(("scenes", 27), calls)
        self.assertEqual(read_json(self.result)["status"], "completed")

    def test_hard_skip_checks_older_matching_target_after_newer_mismatch(self):
        module = worker()
        matching = self.cache(target=True)
        newer = (
            self.root
            / "output"
            / f"{self.source.stem}_20261002_120000"
        )
        newer.mkdir()
        (newer / "video_no_subtitles.mp4").write_bytes(b"newer other target")
        other = self.root / "other" / self.source.name
        other.parent.mkdir()
        other.write_bytes(b"other")
        report = read_json(matching / "report.json")
        report["original_video_path"] = str(other)
        report["processed_video_path"] = str(other)
        report["workbench"]["sourceIdentity"] = {
            "sizeBytes": other.stat().st_size,
            "sha256": hashlib.sha256(other.read_bytes()).hexdigest(),
        }
        write_json(newer / "report.json", report)
        self.payload["settings"]["reuseAnalysis"] = False
        with patch(
            "src.core.video_analyzer.VideoAnalyzer",
            side_effect=AssertionError("must find older matching target"),
        ):
            self.assertEqual(self.execute(), 0)
        self.assertEqual(read_json(self.result)["status"], "skipped")

    def test_source_identity_is_hashed_once_across_cache_candidates(self):
        module = worker()
        for day in range(1, 4):
            directory = self.cache()
            renamed = directory.with_name(
                f"{self.source.stem}_2026100{day}_12000{day}"
            )
            if directory != renamed:
                directory.rename(renamed)
            report = read_json(renamed / "report.json")
            report["workbench"]["sourceIdentity"]["sha256"] = "0" * 64
            write_json(renamed / "report.json", report)
        with self.analyzer(), patch.object(
            module,
            "_file_identity",
            wraps=module._file_identity,
        ) as identity:
            self.assertEqual(self.execute(), 0)
        self.assertEqual(identity.call_count, 1)

    def test_cache_content_identity_mismatch_runs_fresh_analysis(self):
        worker()
        directory = self.cache(target=True)
        report = read_json(directory / "report.json")
        report["workbench"] = {
            "completedSteps": ["scenes"],
            "transcriptionModel": "tiny",
            "sourceIdentity": {
                "sizeBytes": self.source.stat().st_size,
                "sha256": hashlib.sha256(b"different source").hexdigest(),
            },
        }
        write_json(directory / "report.json", report)
        with self.analyzer() as calls:
            self.assertEqual(self.execute(), 0)
        self.assertIn(("scenes", 27), calls)
        self.assertEqual(read_json(self.result)["status"], "completed")

    def test_scene_processing_disables_the_unused_ffplay_probe(self):
        worker()
        with patch.dict(os.environ):
            os.environ.pop("FFPLAY_BINARY", None)
            with self.analyzer():
                self.assertEqual(self.execute(), 0)
            self.assertEqual(os.environ.get("FFPLAY_BINARY"), "ffmpeg")

    def test_invalid_cache_metadata_is_ignored_not_a_task_failure(self):
        worker()
        directory = self.cache()
        report = read_json(directory / "report.json")
        report["workbench"] = None
        write_json(directory / "report.json", report)
        with self.analyzer() as calls:
            self.assertEqual(self.execute(), 0)
        self.assertIn(("scenes", 27), calls)

    def test_cached_semantic_report_with_missing_outputs_is_not_complete(self):
        worker()
        directory = self.cache()
        report = read_json(directory / "report.json")
        report["semantic_scenes"] = [
            {"output_path": str(directory / "missing.mp4"), "duration": 4},
        ]
        write_json(directory / "report.json", report)
        self.payload["task"]["steps"] = ["semantic"]
        with patch("src.core.semantic_scene_grouper.SemanticSceneGrouper.from_config") as factory:
            factory.return_value.group_and_export.side_effect = RuntimeError("offline")
            self.assertEqual(self.execute(), 1)
        factory.assert_called_once()
        self.assertFalse(self.result.exists())

    def test_completed_semantic_sidecar_reused_without_api_or_rewriting_report(self):
        worker()
        directory = self.cache()
        before = (directory / "report.json").read_bytes()
        shot = directory / "semantic_scenes" / "SemanticScene-001.mp4"
        shot.parent.mkdir()
        shot.write_bytes(b"existing semantic shot")
        write_json(directory / "semantic_scenes.json", [{
            "semantic_scene_number": 1, "start_time": 0, "end_time": 4,
            "duration": 4, "output_path": str(shot),
        }])
        self.payload["task"]["steps"] = ["semantic"]
        with patch("src.core.semantic_scene_grouper.SemanticSceneGrouper.from_config",
                   side_effect=AssertionError("Must reuse the completed sidecar")):
            self.assertEqual(self.execute(), 0)
        result = read_json(self.result)
        self.assertEqual(result["newMaterials"][0]["path"], str(shot))
        self.assertEqual((directory / "report.json").read_bytes(), before)

    @contextmanager
    def analyzer(self, *, audio=True, split=True):
        from src.core.video_analyzer import VideoAnalyzer
        calls = []

        def clean(instance, *args):
            calls.append("clean")
            return instance.video_path

        def scenes(instance, threshold):
            calls.append(("scenes", threshold))
            instance.scene_detection_config = {"content_threshold": threshold}
            if split:
                directory = Path(instance.output_dir) / "scenes"
                directory.mkdir()
                (directory / "Scene-001.mp4").write_bytes(b"generated shot")
            return [{"scene_number": 1, "start_time": 0, "end_time": 4, "duration": 4}]

        def extract(instance):
            calls.append("extract")
            if not audio:
                return None
            path = Path(instance.output_dir) / "audio.mp3"
            path.write_bytes(b"audio")
            return str(path)

        def transcribe(instance, path, model):
            calls.append(("transcribe", model))
            return {"text": "hello", "segments": [{"start": 0.5, "end": 1, "text": "hello"}]}

        with patch.object(VideoAnalyzer, "remove_subtitles", clean), \
                patch.object(VideoAnalyzer, "analyze_scenes", scenes), \
                patch.object(VideoAnalyzer, "extract_audio", extract), \
                patch.object(VideoAnalyzer, "transcribe_audio", transcribe), \
                patch("src.services.workbench_worker._probe") as probe:
            from src.models import MediaMetadata
            probe.side_effect = lambda path: MediaMetadata(Path(path), 4_000_000, 96, 48, audio)
            yield calls

    def test_cli_order_checkpoint_and_events_are_flushed_before_semantic(self):
        worker()
        self.payload["task"]["steps"] = ["semantic", "transcribe", "scenes", "clean"]

        def semantic(video, scenes, transcript, output):
            calls.append("semantic")
            report = read_json(Path(output) / "report.json")
            self.assertEqual(report["transcript"], "hello")
            self.assertTrue(report["scene_detection"])
            self.assertIn("semantic", self.events.read_text().lower())
            directory = Path(output) / "semantic_scenes"
            directory.mkdir()
            path = directory / "SemanticScene-001.mp4"
            path.write_bytes(b"semantic shot")
            return [{"semantic_scene_number": 1, "start_time": 0, "end_time": 4,
                     "duration": 4, "output_path": str(path)}]

        with self.analyzer() as calls, \
                patch("src.core.semantic_scene_grouper.SemanticSceneGrouper.from_config") as factory:
            factory.return_value.group_and_export.side_effect = semantic
            self.assertEqual(self.execute(), 0)
        self.assertEqual(calls, ["clean", ("scenes", 27), "extract",
                                 ("transcribe", "tiny"), "semantic"])
        result = read_json(self.result)
        self.assertEqual(len(result["newMaterials"]), 2)
        self.assertEqual(result["materialUpdates"][0]["status"], "analyzed")
        report = read_json(result["materialUpdates"][0]["reportPath"])
        self.assertEqual(
            report["workbench"]["sourceIdentity"],
            {
                "sizeBytes": self.source.stat().st_size,
                "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
            },
        )

    def test_missing_split_artifact_is_a_failure(self):
        worker()
        with self.analyzer(split=False):
            self.assertEqual(self.execute(), 1)
        self.assertFalse(self.result.exists())

    def test_no_audio_does_not_load_whisper_and_empty_transcript_is_reusable(self):
        worker()
        self.payload["task"]["steps"] = ["transcribe"]
        with self.analyzer(audio=False) as calls:
            self.assertEqual(self.execute(), 0)
        self.assertEqual(calls, ["extract"])
        self.assertEqual(read_json(self.result)["materialUpdates"][0]["transcript"], [])
        self.result.unlink()
        with patch("src.core.video_analyzer.VideoAnalyzer", side_effect=AssertionError):
            self.assertEqual(self.execute(), 0)

    def test_partial_report_does_not_satisfy_requested_transcription(self):
        worker()
        original = self.cache(transcript=False)
        before = (original / "report.json").read_bytes()
        self.payload["task"]["steps"] = ["scenes", "transcribe"]
        with self.analyzer() as calls:
            self.assertEqual(self.execute(), 0)
        self.assertIn(("transcribe", "tiny"), calls)
        self.assertEqual((original / "report.json").read_bytes(), before)

    def test_reuse_disabled_and_changed_threshold_run_fresh_analysis(self):
        worker()
        original = self.cache()
        before = (original / "report.json").read_bytes()
        self.payload["settings"]["reuseAnalysis"] = False
        with self.analyzer() as calls:
            self.assertEqual(self.execute(), 0)
        self.assertIn(("scenes", 27), calls)
        self.result.unlink()
        self.payload["settings"]["reuseAnalysis"] = True
        self.payload["task"]["threshold"] = 31
        with self.analyzer() as calls:
            self.assertEqual(self.execute(), 0)
        self.assertIn(("scenes", 31), calls)
        self.assertEqual((original / "report.json").read_bytes(), before)

    def test_semantic_completion_reuses_report_but_never_overwrites_it(self):
        worker()
        directory = self.cache()
        before = (directory / "report.json").read_bytes()
        self.payload["task"]["steps"] = ["semantic"]
        self.payload["settings"]["reuseAnalysis"] = False
        with patch("src.core.video_analyzer.VideoAnalyzer", side_effect=AssertionError), \
                patch("src.core.semantic_scene_grouper.SemanticSceneGrouper.from_config") as factory:
            factory.return_value.group_and_export.side_effect = RuntimeError("semantic API offline")
            self.assertEqual(self.execute(), 1)
        self.assertFalse(self.result.exists())
        self.assertEqual((directory / "report.json").read_bytes(), before)
        reports = list((self.root / "output").glob("*/report.json"))
        self.assertEqual(len(reports), 2)
        self.assertEqual(len(read_json(next(p for p in reports if p.parent != directory))["scenes"]), 1)


def ffmpeg(*args):
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", *map(str, args)],
        check=True, capture_output=True, timeout=40,
    ).stdout


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class TestWorkerVideoIntegration(WorkerCase):
    def setUp(self):
        super().setUp()
        self.source.unlink()
        ffmpeg(
            "-f", "lavfi", "-i",
            "color=red:s=96x160:r=30:d=2[r];"
            "color=blue:s=96x160:r=30:d=2[b];[r][b]concat=n=2:v=1:a=0",
            "-c:v", "libx264", "-preset", "ultrafast", self.source,
        )

    def test_real_scene_detection_and_full_plan_preview_and_draft(self):
        self.invoke()
        analysis = read_json(self.result)
        self.assertEqual(analysis["status"], "completed")
        scenes = analysis["materialUpdates"][0]["scenes"]
        self.assertEqual(len(scenes), 2)
        self.assertEqual([scene["durationSeconds"] for scene in scenes], [2, 2])
        self.assertEqual(len(analysis["newMaterials"]), 2)
        report = read_json(analysis["materialUpdates"][0]["reportPath"])
        self.assertEqual(report["scene_detection"]["detector_type"], "adaptive")
        for material in analysis["newMaterials"]:
            self.assertTrue(Path(material["path"]).is_file())
            ffmpeg("-i", material["path"], "-f", "null", "-")

        self.result.unlink()
        self.mix(("preview", "draft"))
        self.payload["settings"]["draftDirectory"] = str(self.root / "drafts")
        self.payload["task"]["plan"]["clips"].append(
            {"materialId": "m1", "label": "blue ending", "durationSeconds": 1,
             "sourceStartSeconds": 2.5},
        )
        self.invoke()
        result = read_json(self.result)
        outputs = {item["kind"]: item for item in result["outputs"]}
        preview = outputs["preview"]
        self.assertEqual((preview["width"], preview["height"]), (96, 160))
        self.assertAlmostEqual(preview["durationSeconds"], 5, places=2)
        self.assertEqual(preview["sizeBytes"], Path(preview["path"]).stat().st_size)
        self.assertEqual(preview["materialId"], "m1")
        ffmpeg("-i", preview["path"], "-f", "null", "-")
        for time, channel in ((0.2, 0), (3.0, 2), (4.5, 2)):
            pixel = ffmpeg("-ss", time, "-i", preview["path"], "-frames:v", 1,
                           "-vf", "scale=1:1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-")
            self.assertGreater(pixel[channel], 200)

        draft = read_json(Path(outputs["draft"]["path"]) / "draft_info.json")
        video = next(track for track in draft["tracks"] if track["type"] == "video")
        self.assertEqual([s["target_timerange"]["duration"] for s in video["segments"]],
                         [4_000_000, 1_000_000])
        self.assertEqual(draft["canvas_config"]["width"], 96)
        for material in draft["materials"]["videos"] + draft["materials"]["audios"]:
            self.assertTrue(Path(material["path"]).is_file())
        self.assertTrue(list(Path(self.payload["workDir"]).rglob("clip_*.mov")))
        self.assertTrue(list(Path(self.payload["workDir"]).rglob("audio.m4a")))
        self.assertEqual({item["kind"] for item in result["outputs"]}, {"preview", "draft"})

    def test_fixed_plan_out_of_range_is_rejected_not_silently_clamped(self):
        self.mix()
        self.payload["task"]["plan"]["clips"][0]["sourceStartSeconds"] = 1
        process = self.invoke(expected=1)
        self.assertIn("duration", process.stderr.lower())
        self.assertFalse(self.result.exists())
        self.assertFalse(list((self.root / "output").rglob("*.mp4")))

    def test_draft_only_exports_no_public_preview(self):
        self.mix(("draft",))
        self.payload["settings"]["draftDirectory"] = str(self.root / "drafts")
        self.invoke()
        self.assertEqual([o["kind"] for o in read_json(self.result)["outputs"]], ["draft"])

    def test_mixed_aspects_and_audio_follow_first_plan_source(self):
        second = self.root / "landscape.mp4"
        ffmpeg("-f", "lavfi", "-i", "color=lime:s=160x96:r=30:d=1",
               "-f", "lavfi", "-i", "sine=frequency=400:duration=1",
               "-c:v", "libx264", "-c:a", "aac", second)
        self.payload["materials"].append(
            {"id": "m2", "name": second.name, "path": str(second), "durationSeconds": 1},
        )
        self.mix()
        self.payload["task"]["materialIds"] = ["m2", "m1"]
        self.payload["task"]["plan"]["clips"].append(
            {"materialId": "m2", "label": "landscape", "durationSeconds": 1},
        )
        self.invoke()
        output = read_json(self.result)["outputs"][0]
        self.assertEqual((output["width"], output["height"]), (96, 160))
        self.assertEqual(output["materialId"], "m1")
        self.assertAlmostEqual(output["durationSeconds"], 5, places=2)
        samples = ffmpeg("-ss", 4.1, "-i", output["path"], "-t", 0.2,
                         "-vn", "-ac", 1, "-f", "s16le", "-")
        self.assertGreater(sum(byte != 0 for byte in samples), 100)

    def test_clean_silent_video_preserves_source_and_can_be_reused(self):
        original = self.source.read_bytes()
        self.payload["task"]["steps"] = ["clean", "scenes", "transcribe"]
        self.invoke()
        result = read_json(self.result)
        self.assertEqual(result["materialUpdates"][0]["transcript"], [])
        self.assertEqual(self.source.read_bytes(), original)
        self.result.unlink()
        self.invoke()
        self.assertIn(read_json(self.result)["status"], ("completed", "skipped"))

    def test_uncut_long_shot_is_not_split_by_duration(self):
        self.source.unlink()
        ffmpeg("-f", "lavfi", "-i", "color=red:s=96x160:r=30:d=12",
               "-c:v", "libx264", "-preset", "ultrafast", self.source)
        self.payload["materials"][0]["durationSeconds"] = 12
        self.invoke()
        scenes = read_json(self.result)["materialUpdates"][0]["scenes"]
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["durationSeconds"], 12)

    def test_repeated_execution_creates_new_outputs_without_overwriting(self):
        self.mix()
        self.invoke()
        first = Path(read_json(self.result)["outputs"][0]["path"])
        original = first.read_bytes()
        self.result.unlink()
        self.invoke()
        second = Path(read_json(self.result)["outputs"][0]["path"])
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
