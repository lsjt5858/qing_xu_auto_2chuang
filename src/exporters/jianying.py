"""
Export analysis artifacts or composition timelines as Jianying draft folders.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import AnalysisArtifacts, TimelineClip, probe_media


DEFAULT_DRAFT_ROOT = Path(
    "/Users/apple1/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
)
DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "jianying"


def _new_id() -> str:
    return str(uuid.uuid4()).upper()


def _now_us() -> int:
    return int(datetime.now().timestamp() * 1_000_000)


def _safe_name(name: str) -> str:
    name = re.sub(r"[/:\\\0]", "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:80] or f"chai_export_{datetime.now():%Y%m%d_%H%M%S}"


def _dump_json(path: Path, data: Any, *, pretty: bool = True) -> None:
    with path.open("w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=4)
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _unique_draft_dir(root: Path, requested_name: str) -> tuple[str, Path]:
    requested_name = _safe_name(requested_name)
    candidate = root / requested_name
    if not candidate.exists():
        return requested_name, candidate

    index = 2
    while True:
        name = f"{requested_name}_{index}"
        candidate = root / name
        if not candidate.exists():
            return name, candidate
        index += 1


def _copy_template(template_dir: Path, draft_dir: Path) -> dict[str, Any]:
    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")
    shutil.copytree(template_dir, draft_dir)
    for subdir in ("video", "audio", "Resources", "common_attachment", "Timelines"):
        (draft_dir / subdir).mkdir(exist_ok=True)
    return _load_json(template_dir / "draft_info.json")


def _make_speed(speed_id: str, speed: float = 1.0) -> dict[str, Any]:
    return {
        "curve_speed": None,
        "id": speed_id,
        "mode": 0,
        "speed": speed,
        "type": "speed",
    }


def _make_video_material(
    material_id: str,
    path: str,
    name: str,
    duration_us: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    return {
        "audio_fade": None,
        "category_id": "",
        "category_name": "local",
        "check_flag": 63487,
        "crop": {
            "upper_left_x": 0.0,
            "upper_left_y": 0.0,
            "upper_right_x": 1.0,
            "upper_right_y": 0.0,
            "lower_left_x": 0.0,
            "lower_left_y": 1.0,
            "lower_right_x": 1.0,
            "lower_right_y": 1.0,
        },
        "crop_ratio": "free",
        "crop_scale": 1.0,
        "duration": duration_us,
        "height": height,
        "id": material_id,
        "local_material_id": "",
        "material_id": material_id,
        "material_name": name,
        "media_path": path,
        "path": path,
        "remote_url": None,
        "type": "video",
        "width": width,
    }


def _make_audio_material(material_id: str, path: str, name: str, duration_us: int) -> dict[str, Any]:
    return {
        "app_id": 0,
        "category_id": "",
        "category_name": "local",
        "check_flag": 1,
        "copyright_limit_type": "none",
        "duration": duration_us,
        "effect_id": "",
        "formula_id": "",
        "id": material_id,
        "intensifies_path": "",
        "is_ai_clone_tone": False,
        "is_text_edit_overdub": False,
        "is_ugc": False,
        "local_material_id": material_id,
        "music_id": material_id,
        "name": name,
        "path": path,
        "remote_url": None,
        "query": "",
        "request_id": "",
        "resource_id": "",
        "search_id": "",
        "source_from": "",
        "source_platform": 0,
        "team_id": "",
        "text_id": "",
        "tone_category_id": "",
        "tone_category_name": "",
        "tone_effect_id": "",
        "tone_effect_name": "",
        "tone_platform": "",
        "tone_second_category_id": "",
        "tone_second_category_name": "",
        "tone_speaker": "",
        "tone_type": "",
        "type": "extract_music",
        "video_id": "",
        "wave_points": [],
    }


def _make_text_material(material_id: str, text: str, *, fixed_width: int) -> dict[str, Any]:
    text = text.strip()
    content = {
        "styles": [
            {
                "fill": {
                    "alpha": 1.0,
                    "content": {
                        "render_type": "solid",
                        "solid": {"alpha": 1.0, "color": [1.0, 1.0, 1.0]},
                    },
                },
                "range": [0, len(text)],
                "size": 5.0,
                "bold": False,
                "italic": False,
                "underline": False,
                "strokes": [
                    {
                        "alpha": 1.0,
                        "content": {
                            "render_type": "solid",
                            "solid": {"alpha": 1.0, "color": [0.0, 0.0, 0.0]},
                        },
                        "width": 0.08,
                    }
                ],
            }
        ],
        "text": text,
    }
    return {
        "id": material_id,
        "content": json.dumps(content, ensure_ascii=False),
        "type": "text",
        "typesetting": 0,
        "alignment": 1,
        "letter_spacing": 0,
        "line_spacing": 0.02,
        "line_feed": 1,
        "line_max_width": 0.82,
        "force_apply_line_max_width": False,
        "check_flag": 15,
        "fixed_width": fixed_width,
        "fixed_height": -1,
        "font_category_id": "",
        "font_category_name": "",
        "font_id": "",
        "font_name": "",
        "font_path": "",
        "font_resource_id": "",
        "font_size": 5.0,
        "font_source_platform": 0,
        "font_team_id": "",
        "font_title": "none",
        "font_url": "",
        "fonts": [],
        "text_color": "#ffffff",
        "text_size": 30,
        "border_color": "#000000",
        "border_alpha": 1,
        "border_width": 0.08,
        "background_alpha": 1,
        "background_color": "",
        "background_style": 0,
        "background_height": 0.14,
        "background_width": 0.14,
        "background_round_radius": 0,
        "background_horizontal_offset": 0,
        "background_vertical_offset": 0,
    }


def _base_segment(
    segment_id: str,
    material_id: str,
    start_us: int,
    duration_us: int,
    *,
    render_index: int,
    volume: float,
    speed_id: str | None,
    source_timerange: dict[str, int] | None,
) -> dict[str, Any]:
    refs = [speed_id] if speed_id else []
    return {
        "enable_adjust": True,
        "enable_color_correct_adjust": False,
        "enable_color_curves": True,
        "enable_color_match_adjust": False,
        "enable_color_wheels": True,
        "enable_lut": True,
        "enable_smart_color_adjust": False,
        "last_nonzero_volume": 1.0,
        "reverse": False,
        "track_attribute": 0,
        "track_render_index": 0,
        "visible": True,
        "id": segment_id,
        "material_id": material_id,
        "target_timerange": {"start": start_us, "duration": duration_us},
        "source_timerange": source_timerange,
        "speed": 1.0,
        "volume": volume,
        "extra_material_refs": refs,
        "common_keyframes": [],
        "keyframe_refs": [],
        "render_index": render_index,
    }


def _make_visual_segment(
    segment_id: str,
    material_id: str,
    start_us: int,
    duration_us: int,
    *,
    render_index: int,
    volume: float,
    speed_id: str | None,
    source_timerange: dict[str, int] | None,
    transform_y: float = 0.0,
) -> dict[str, Any]:
    segment = _base_segment(
        segment_id,
        material_id,
        start_us,
        duration_us,
        render_index=render_index,
        volume=volume,
        speed_id=speed_id,
        source_timerange=source_timerange,
    )
    segment.update(
        {
            "clip": {
                "alpha": 1.0,
                "flip": {"horizontal": False, "vertical": False},
                "rotation": 0.0,
                "scale": {"x": 1.0, "y": 1.0},
                "transform": {"x": 0.0, "y": transform_y},
            },
            "uniform_scale": {"on": True, "value": 1.0},
            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        }
    )
    return segment


def _make_audio_segment(
    segment_id: str,
    material_id: str,
    start_us: int,
    duration_us: int,
    speed_id: str,
) -> dict[str, Any]:
    segment = _base_segment(
        segment_id,
        material_id,
        start_us,
        duration_us,
        render_index=0,
        volume=1.0,
        speed_id=speed_id,
        source_timerange={"start": 0, "duration": duration_us},
    )
    segment.update({"clip": None, "hdr_settings": None})
    return segment


def _make_track(track_type: str, name: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "attribute": 0,
        "flag": 0,
        "id": _new_id(),
        "is_default_name": False,
        "name": name,
        "segments": segments,
        "type": track_type,
    }


def _update_meta(draft_dir: Path, draft_id: str, draft_name: str, duration_us: int) -> None:
    meta_path = draft_dir / "draft_meta_info.json"
    meta = _load_json(meta_path)
    timestamp = _now_us()
    meta.update(
        {
            "draft_cover": "draft_cover.jpg",
            "draft_fold_path": str(draft_dir),
            "draft_id": draft_id,
            "draft_name": draft_name,
            "draft_root_path": str(draft_dir.parent),
            "tm_draft_create": timestamp,
            "tm_draft_modified": timestamp,
            "tm_duration": duration_us,
            "draft_timeline_materials_size": meta.get(
                "draft_timeline_materials_size",
                meta.get("draft_timeline_materials_size_", 0),
            ),
        }
    )
    _dump_json(meta_path, meta, pretty=True)


def _build_root_meta_entry(draft_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": meta.get("draft_cloud_last_action_download", False),
        "draft_cloud_purchase_info": meta.get("draft_cloud_purchase_info", ""),
        "draft_cloud_template_id": meta.get("draft_cloud_template_id", ""),
        "draft_cloud_tutorial_info": meta.get("draft_cloud_tutorial_info", ""),
        "draft_cloud_videocut_purchase_info": meta.get(
            "draft_cloud_videocut_purchase_info",
            "",
        ),
        "draft_cover": str(draft_dir / "draft_cover.jpg"),
        "draft_fold_path": str(draft_dir),
        "draft_id": meta["draft_id"],
        "draft_is_ai_shorts": meta.get("draft_is_ai_shorts", False),
        "draft_is_cloud_temp_draft": False,
        "draft_is_invisible": meta.get("draft_is_invisible", False),
        "draft_is_web_article_video": False,
        "draft_json_file": str(draft_dir / "draft_info.json"),
        "draft_name": meta.get("draft_name", draft_dir.name),
        "draft_new_version": meta.get("draft_new_version", ""),
        "draft_root_path": str(draft_dir.parent),
        "draft_timeline_materials_size": meta.get(
            "draft_timeline_materials_size",
            meta.get("draft_timeline_materials_size_", 0),
        ),
        "draft_type": meta.get("draft_type", ""),
        "draft_web_article_video_enter_from": "",
        "streaming_edit_draft_ready": True,
        "tm_draft_cloud_completed": meta.get("tm_draft_cloud_completed", ""),
        "tm_draft_cloud_entry_id": meta.get("tm_draft_cloud_entry_id", -1),
        "tm_draft_cloud_modified": meta.get("tm_draft_cloud_modified", 0),
        "tm_draft_cloud_parent_entry_id": meta.get("tm_draft_cloud_parent_entry_id", -1),
        "tm_draft_cloud_space_id": meta.get("tm_draft_cloud_space_id", -1),
        "tm_draft_cloud_user_id": meta.get("tm_draft_cloud_user_id", -1),
        "tm_draft_create": meta.get("tm_draft_create", _now_us()),
        "tm_draft_modified": meta.get("tm_draft_modified", _now_us()),
        "tm_draft_removed": meta.get("tm_draft_removed", 0),
        "tm_duration": meta.get("tm_duration", 0),
    }


def _update_root_meta(draft_root: Path, draft_dir: Path) -> None:
    root_meta_path = draft_root / "root_meta_info.json"
    if root_meta_path.exists():
        root_meta = _load_json(root_meta_path)
    else:
        root_meta = {
            "all_draft_store": [],
            "draft_ids": 0,
            "root_path": str(draft_root),
        }

    meta = _load_json(draft_dir / "draft_meta_info.json")
    stores = [
        item
        for item in root_meta.get("all_draft_store", [])
        if not (
            isinstance(item, dict)
            and (
                item.get("draft_id") == meta.get("draft_id")
                or item.get("draft_fold_path") == str(draft_dir)
            )
        )
    ]
    stores_before = len(stores)

    stores.append(_build_root_meta_entry(draft_dir, meta))
    stores.sort(key=lambda item: item.get("tm_draft_modified", 0), reverse=True)

    existing_draft_ids = root_meta.get("draft_ids", 0)
    if not isinstance(existing_draft_ids, int):
        existing_draft_ids = stores_before

    root_meta.update(
        {
            "all_draft_store": stores,
            "draft_ids": max(existing_draft_ids, stores_before) + 1,
            "root_path": str(draft_root),
        }
    )
    _dump_json(root_meta_path, root_meta, pretty=True)


def _write_timeline_files(draft_dir: Path, draft_id: str, draft_content: dict[str, Any]) -> None:
    timelines_dir = draft_dir / "Timelines"
    timeline_dir = timelines_dir / draft_id
    timeline_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _now_us()
    project = {
        "config": {
            "color_space": -1,
            "render_index_track_mode_on": True,
            "use_float_render": False,
        },
        "create_time": timestamp,
        "id": draft_id,
        "main_timeline_id": draft_id,
        "timelines": [
            {
                "create_time": timestamp,
                "id": draft_id,
                "is_marked_delete": False,
                "name": "",
                "update_time": timestamp,
            }
        ],
        "update_time": timestamp,
        "version": 0,
    }
    _dump_json(timelines_dir / "project.json", project, pretty=False)
    _dump_json(timeline_dir / "draft_info.json", draft_content, pretty=True)


def _try_generate_cover(draft_dir: Path, source_video: Path) -> None:
    cover = draft_dir / "draft_cover.jpg"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(source_video),
                "-frames:v",
                "1",
                str(cover),
            ],
            check=True,
        )
    except Exception:
        pass


def export_to_jianying_draft(
    artifacts: AnalysisArtifacts,
    *,
    timeline_clips: list[TimelineClip] | None = None,
    draft_root: str | Path = DEFAULT_DRAFT_ROOT,
    template_dir: str | Path = DEFAULT_TEMPLATE_DIR,
    draft_name: str | None = None,
) -> Path:
    timeline_clips = timeline_clips or artifacts.default_timeline()
    if not timeline_clips:
        raise ValueError("No timeline clips available for export")

    draft_root = Path(draft_root).expanduser()
    template_dir = Path(template_dir).expanduser()
    requested_name = draft_name or f"chai_{artifacts.video_name}_{datetime.now():%H%M%S}"
    final_name, draft_dir = _unique_draft_dir(draft_root, requested_name)

    base_info = _copy_template(template_dir, draft_dir)
    draft_id = _new_id()
    video_dir = draft_dir / "video"
    audio_dir = draft_dir / "audio"

    materials = {key: [] for key in base_info.get("materials", {}).keys()}
    for extra_key in (
        "common_mask",
        "audio_pannings",
        "audio_pitch_shifts",
        "hsl_curves",
        "manual_beautys",
        "placeholder_infos",
        "video_radius",
        "video_shadows",
        "video_strokes",
    ):
        materials.setdefault(extra_key, [])

    timeline_duration_us = max(
        clip.timeline_start_us + clip.timeline_duration_us for clip in timeline_clips
    )
    if artifacts.audio_metadata:
        timeline_duration_us = max(timeline_duration_us, artifacts.audio_metadata.duration_us)

    media_cache: dict[Path, tuple[str, Path, Any]] = {}
    canvas_width = 1920
    canvas_height = 1080
    video_segments: list[dict[str, Any]] = []

    def ensure_video_material(source_path: Path) -> tuple[str, Path, Any]:
        source_path = source_path.resolve()
        if source_path in media_cache:
            return media_cache[source_path]

        metadata = probe_media(source_path)
        nonlocal canvas_width, canvas_height
        if metadata.width and metadata.height:
            canvas_width, canvas_height = metadata.width, metadata.height

        copy_name = f"{len(media_cache) + 1:03d}_{source_path.name}"
        copied_path = video_dir / copy_name
        shutil.copy2(source_path, copied_path)
        material_id = _new_id()
        materials["videos"].append(
            _make_video_material(
                material_id,
                str(copied_path),
                copied_path.name,
                metadata.duration_us,
                metadata.width or canvas_width,
                metadata.height or canvas_height,
            )
        )
        media_cache[source_path] = (material_id, copied_path, metadata)
        return media_cache[source_path]

    for clip in timeline_clips:
        material_id, _, metadata = ensure_video_material(clip.source_path)
        speed_id = _new_id()
        materials["speeds"].append(_make_speed(speed_id))
        source_duration_us = min(
            clip.effective_source_duration_us,
            max(0, metadata.duration_us - clip.source_start_us) or clip.timeline_duration_us,
        )
        video_segments.append(
            _make_visual_segment(
                _new_id(),
                material_id,
                clip.timeline_start_us,
                clip.timeline_duration_us,
                render_index=0,
                volume=0.0,
                speed_id=speed_id,
                source_timerange={
                    "start": clip.source_start_us,
                    "duration": source_duration_us,
                },
            )
        )

    audio_segments: list[dict[str, Any]] = []
    if artifacts.audio_path and artifacts.audio_metadata:
        copied_audio = audio_dir / artifacts.audio_path.name
        shutil.copy2(artifacts.audio_path, copied_audio)
        audio_material_id = _new_id()
        audio_speed_id = _new_id()
        materials["audios"].append(
            _make_audio_material(
                audio_material_id,
                str(copied_audio),
                copied_audio.name,
                min(artifacts.audio_metadata.duration_us, timeline_duration_us),
            )
        )
        materials["speeds"].append(_make_speed(audio_speed_id))
        audio_segments.append(
            _make_audio_segment(
                _new_id(),
                audio_material_id,
                0,
                min(artifacts.audio_metadata.duration_us, timeline_duration_us),
                audio_speed_id,
            )
        )

    text_segments: list[dict[str, Any]] = []
    fixed_width = int(canvas_width * 0.7) if canvas_width >= canvas_height else int(canvas_width * 0.82)
    for transcript in artifacts.transcript_segments:
        text = transcript.text.strip()
        if not text:
            continue
        start_us = transcript.start_us
        duration_us = min(transcript.duration_us, max(0, timeline_duration_us - start_us))
        if duration_us <= 0:
            continue
        material_id = _new_id()
        materials["texts"].append(
            _make_text_material(material_id, text, fixed_width=fixed_width)
        )
        text_segments.append(
            _make_visual_segment(
                _new_id(),
                material_id,
                start_us,
                duration_us,
                render_index=15000,
                volume=1.0,
                speed_id=None,
                source_timerange=None,
                transform_y=-0.78,
            )
        )

    tracks = [_make_track("video", "主视频", video_segments)]
    if audio_segments:
        tracks.append(_make_track("audio", "音频", audio_segments))
    if text_segments:
        tracks.append(_make_track("text", "字幕", text_segments))

    timestamp = _now_us()
    platform = {
        "app_id": 3704,
        "app_source": "lv",
        "app_version": "5.9.0",
        "device_id": "",
        "hard_disk_id": "",
        "mac_address": "",
        "os": "mac",
        "os_version": "",
    }
    base_info.update(
        {
            "id": draft_id,
            "name": final_name,
            "duration": timeline_duration_us,
            "fps": 30.0,
            "canvas_config": {
                "height": canvas_height,
                "ratio": "original",
                "width": canvas_width,
            },
            "create_time": timestamp,
            "update_time": timestamp,
            "materials": materials,
            "tracks": tracks,
            "static_cover_image_path": "draft_cover.jpg",
            "platform": platform,
            "last_modified_platform": platform,
        }
    )

    for name in ("draft_info.json", "draft_info.json.bak", "template.tmp", "template-2.tmp", "template.json.bak"):
        _dump_json(draft_dir / name, base_info, pretty=True)

    _update_meta(draft_dir, draft_id, final_name, timeline_duration_us)
    _update_root_meta(draft_root, draft_dir)
    _write_timeline_files(draft_dir, draft_id, base_info)
    _try_generate_cover(draft_dir, timeline_clips[0].source_path)
    return draft_dir
