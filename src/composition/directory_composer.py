"""Select complete clips from ordered directories without changing source media."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import random
import subprocess

from src.models import TimelineClip, probe_media
from src.models.artifacts import VIDEO_EXTENSIONS


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | {".flv", ".wmv", ".ts"}


@dataclass(frozen=True)
class DirectoryStage:
    directory: Path
    count: int | None = 1
    role: str = "part"


def _seconds_us(value: float, name: str, *, allow_zero: bool = False) -> int:
    if not math.isfinite(value) or not math.isfinite(value * 1_000_000) or value < 0:
        raise ValueError(f"{name} 必须为有限的非负秒数")
    result = round(value * 1_000_000)
    if not allow_zero and result <= 0:
        raise ValueError(f"{name} 必须至少为 0.000001 秒")
    return result


def compose_directories(
    stages: list[DirectoryStage], *, seed: int,
    selection: str = "random", photo_duration: float = 2.0,
    clip_start: float = 0.0, clip_duration: float | None = None,
    probe=None,
) -> list[TimelineClip]:
    """Keep stage order; selection randomness never implies random source trimming."""
    probe = probe or probe_media
    if not stages:
        raise ValueError("请至少提供一个素材目录")
    if selection not in {"random", "ordered"}:
        raise ValueError("selection 必须为 random 或 ordered")
    photo_us = _seconds_us(photo_duration, "photo-duration")
    start_us = _seconds_us(clip_start, "clip-start", allow_zero=True)
    limit_us = _seconds_us(clip_duration, "clip-duration") if clip_duration is not None else None
    rng = random.Random(seed)
    clips: list[TimelineClip] = []
    cursor = 0

    for stage in stages:
        if stage.count is not None and (type(stage.count) is not int or stage.count <= 0):
            raise ValueError(f"{stage.role} 数量必须为正整数或 all")
        directory = Path(stage.directory).expanduser().resolve()
        if not directory.is_dir():
            raise ValueError(f"素材目录不存在或不是目录: {directory}")
        paths = sorted(
            path for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
            and not any(part.startswith(".") for part in path.relative_to(directory).parts)
        )
        count = len(paths) if stage.count is None else stage.count
        if not count or len(paths) < count:
            raise ValueError(f"{stage.role}: {directory} 需要 {count or '至少 1'} 个素材，只有 {len(paths)} 个")
        selected = rng.sample(paths, count) if selection == "random" else paths[:count]
        for path in selected:
            try:
                metadata = probe(path)
            except (subprocess.CalledProcessError, ValueError) as exc:
                raise ValueError(f"无法读取素材: {path}") from exc
            is_image = path.suffix.lower() in IMAGE_EXTENSIONS
            if not metadata.width or not metadata.height or (not is_image and metadata.duration_us <= 0):
                raise ValueError(f"素材没有有效画面或视频时长: {path}")
            source_start = 0 if is_image else start_us
            duration = photo_us if is_image else metadata.duration_us - source_start
            if duration <= 0:
                raise ValueError(f"clip-start 超出素材长度: {path}")
            if not is_image and limit_us is not None:
                duration = min(duration, limit_us)
            clips.append(TimelineClip(
                source_path=path.resolve(), timeline_start_us=cursor,
                timeline_duration_us=duration, source_start_us=source_start,
                source_duration_us=duration, role=stage.role, label=path.name,
            ))
            cursor += duration
    return clips
