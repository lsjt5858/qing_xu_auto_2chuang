"""
Structured models for analysis output directories.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.audio_silence import load_audio_silence_profile
from src.utils.subtitle_segmentation import split_transcript_segments
from src.utils.text_normalizer import normalize_chinese_text


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".mov"}


@dataclass(frozen=True)
class MediaMetadata:
    path: Path
    duration_us: int
    width: int
    height: int
    has_audio: bool


@dataclass(frozen=True)
class TranscriptSegment:
    start_us: int
    end_us: int
    text: str

    @property
    def duration_us(self) -> int:
        return max(0, self.end_us - self.start_us)


@dataclass(frozen=True)
class SceneSegment:
    index: int
    path: Path
    start_us: int
    end_us: int

    @property
    def duration_us(self) -> int:
        return max(0, self.end_us - self.start_us)


@dataclass(frozen=True)
class TimelineClip:
    source_path: Path
    timeline_start_us: int
    timeline_duration_us: int
    source_start_us: int = 0
    source_duration_us: int | None = None
    role: str = "scene"
    label: str = ""

    @property
    def effective_source_duration_us(self) -> int:
        return self.source_duration_us or self.timeline_duration_us


@dataclass(frozen=True)
class AnalysisArtifacts:
    output_dir: Path
    video_name: str
    original_video_path: Path | None
    processed_video_path: Path | None
    report_path: Path | None
    audio_path: Path | None
    audio_metadata: MediaMetadata | None
    scenes: tuple[SceneSegment, ...]
    transcript_segments: tuple[TranscriptSegment, ...]
    english_transcript_segments: tuple[TranscriptSegment, ...] = ()

    @property
    def total_duration_us(self) -> int:
        candidates = [
            self.audio_metadata.duration_us if self.audio_metadata else 0,
            max((scene.end_us for scene in self.scenes), default=0),
            max((segment.end_us for segment in self.transcript_segments), default=0),
            max((segment.end_us for segment in self.english_transcript_segments), default=0),
        ]
        return max(candidates, default=0)

    def default_timeline(self) -> list[TimelineClip]:
        clips: list[TimelineClip] = []
        cursor = 0
        for scene in self.scenes:
            clips.append(
                TimelineClip(
                    source_path=scene.path,
                    timeline_start_us=cursor,
                    timeline_duration_us=scene.duration_us,
                    source_start_us=0,
                    source_duration_us=scene.duration_us,
                    role="scene",
                    label=scene.path.name,
                )
            )
            cursor += scene.duration_us
        return clips


def to_us(seconds: float | int | None) -> int:
    return max(0, int(round(float(seconds or 0) * 1_000_000)))


def _resolve_path(candidate: str | None, *, fallback_dir: Path) -> Path | None:
    if not candidate:
        return None
    path = Path(candidate)
    if path.exists():
        return path.resolve()
    alt = (fallback_dir / candidate).resolve()
    if alt.exists():
        return alt
    return path.resolve() if path.is_absolute() else None


def _sorted_media_files(directory: Path, extensions: set[str]) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in extensions and not path.name.startswith(".")
    )


def probe_media(path: Path) -> MediaMetadata:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-print_format",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)
    streams = info.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)

    duration = None
    for source in (video_stream, audio_stream, info.get("format", {})):
        if source and source.get("duration") not in (None, "N/A"):
            duration = float(source["duration"])
            break

    return MediaMetadata(
        path=path.resolve(),
        duration_us=to_us(duration),
        width=int(video_stream.get("width", 0)) if video_stream else 0,
        height=int(video_stream.get("height", 0)) if video_stream else 0,
        has_audio=audio_stream is not None,
    )


def _load_transcript_source(
    output_dir: Path,
    report: dict[str, Any],
    *,
    file_candidates: list[str],
    report_keys: list[str],
) -> list[dict[str, Any]]:
    for filename in file_candidates:
        path = output_dir / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    for key in report_keys:
        if report.get(key):
            return report[key]
    return []


def load_analysis_artifacts(output_dir: str | Path) -> AnalysisArtifacts:
    if isinstance(output_dir, str):
        output_dir = output_dir.strip()
    output_dir = Path(output_dir).expanduser().resolve()
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    report_path = output_dir / "report.json"
    report = {}
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))

    video_name = report.get("video_name") or output_dir.name
    original_video_path = _resolve_path(report.get("original_video_path"), fallback_dir=output_dir)

    processed_video_path = None
    explicit_processed = report.get("processed_video_path")
    if explicit_processed:
        processed_video_path = _resolve_path(explicit_processed, fallback_dir=output_dir.parent)
    if processed_video_path is None:
        default_processed = output_dir / "video_no_subtitles.mp4"
        if default_processed.exists():
            processed_video_path = default_processed.resolve()
        else:
            processed_video_path = original_video_path

    audio_path = output_dir / "audio.mp3"
    if not audio_path.exists():
        audio_candidates = _sorted_media_files(output_dir, AUDIO_EXTENSIONS)
        audio_path = audio_candidates[0] if audio_candidates else None
    else:
        audio_path = audio_path.resolve()

    audio_metadata = probe_media(audio_path) if audio_path and audio_path.exists() else None

    scene_files = _sorted_media_files(output_dir / "scenes", VIDEO_EXTENSIONS)
    report_scenes = report.get("scenes") or []
    scenes: list[SceneSegment] = []
    cursor = 0
    for index, scene_path in enumerate(scene_files, start=1):
        if index <= len(report_scenes):
            start_us = to_us(report_scenes[index - 1].get("start_time", cursor / 1_000_000))
            end_us = to_us(report_scenes[index - 1].get("end_time", start_us / 1_000_000))
        else:
            metadata = probe_media(scene_path)
            start_us = cursor
            end_us = cursor + metadata.duration_us
        if end_us < start_us:
            end_us = start_us
        scenes.append(
            SceneSegment(
                index=index,
                path=scene_path.resolve(),
                start_us=start_us,
                end_us=end_us,
            )
        )
        cursor = end_us

    silence_profile = load_audio_silence_profile(audio_path) if audio_path and audio_path.exists() else None
    transcript_source = split_transcript_segments(
        _load_transcript_source(
            output_dir,
            report,
            file_candidates=["transcript_detailed.json"],
            report_keys=["transcript_segments"],
        ),
        silence_profile=silence_profile,
    )
    english_transcript_source = _load_transcript_source(
        output_dir,
        report,
        file_candidates=[
            "transcript_english_detailed.json",
            "transcript_en_detailed.json",
        ],
        report_keys=[
            "english_transcript_segments",
            "transcript_segments_en",
        ],
    )

    transcript_segments = tuple(
        TranscriptSegment(
            start_us=to_us(item.get("start")),
            end_us=to_us(item.get("end")),
            text=normalize_chinese_text(str(item.get("text", "")).strip()),
        )
        for item in transcript_source
        if str(item.get("text", "")).strip()
    )
    english_transcript_segments = tuple(
        TranscriptSegment(
            start_us=to_us(item.get("start")),
            end_us=to_us(item.get("end")),
            text=str(item.get("text", "")).strip(),
        )
        for item in english_transcript_source
        if str(item.get("text", "")).strip()
    )

    return AnalysisArtifacts(
        output_dir=output_dir,
        video_name=video_name,
        original_video_path=original_video_path,
        processed_video_path=processed_video_path,
        report_path=report_path if report_path.exists() else None,
        audio_path=audio_path if audio_path and audio_path.exists() else None,
        audio_metadata=audio_metadata,
        scenes=tuple(scenes),
        transcript_segments=transcript_segments,
        english_transcript_segments=english_transcript_segments,
    )
