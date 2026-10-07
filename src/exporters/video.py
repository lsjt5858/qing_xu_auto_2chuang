"""FFmpeg rendering of a shared video and draft timeline."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from src.composition.directory_composer import IMAGE_EXTENSIONS
from src.models.artifacts import MediaMetadata, TimelineClip, probe_media


@dataclass(frozen=True)
class RenderedTimeline:
    video_path: Path
    clips: tuple[TimelineClip, ...]
    audio_path: Path


def _ffmpeg(args: list[str], *, stage: str) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", *args],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Install ffmpeg and ffprobe and make them available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()[-4000:]
        raise RuntimeError(f"ffmpeg failed while {stage}: {detail or exc}") from exc


def _probe(path: Path) -> MediaMetadata:
    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: {path}")
    try:
        return probe_media(path)
    except FileNotFoundError as exc:
        raise RuntimeError("Install ffmpeg and ffprobe and make them available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()[-4000:]
        raise RuntimeError(f"ffprobe failed for {path}: {detail or exc}") from exc
    except (ValueError, OverflowError) as exc:
        raise RuntimeError(f"ffprobe returned invalid metadata for {path}: {exc}") from exc


def render_timeline(
    clips: list[TimelineClip],
    output_path: Path,
    *,
    work_dir: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    bgm_path: Path | None = None,
    bgm_volume: float = 0.35,
    mute_source: bool = False,
) -> RenderedTimeline:
    """Render clips in list order, retaining draft media in caller-owned work_dir.

    Durations are rounded to frames; returned timings use probed video durations.
    Invalid options raise ValueError, existing output raises FileExistsError, and
    tool failures raise RuntimeError with the failing stage and stderr.
    """
    output_path = output_path.expanduser().absolute()
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing output: {output_path}")
    if not clips:
        raise ValueError("At least one timeline clip is required")
    for name, value in (("width", width), ("height", height), ("fps", fps)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        if name != "fps" and value % 2:
            raise ValueError(f"{name} must be even")
    if (type(bgm_volume) not in (int, float) or not math.isfinite(bgm_volume)
            or not 0 <= bgm_volume <= 1):
        raise ValueError("bgm_volume must be finite and between 0 and 1")
    inputs_to_render = []
    for clip in clips:
        for name, minimum in (
            ("timeline_start_us", 0), ("source_start_us", 0),
            ("timeline_duration_us", 1), ("source_duration_us", 1),
        ):
            value = getattr(clip, name)
            if name == "source_duration_us" and value is None:
                continue
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}: {clip.source_path}")
        source = clip.source_path.expanduser().resolve()
        metadata = _probe(source)
        is_image = source.suffix.lower() in IMAGE_EXTENSIONS
        if metadata.width <= 0 or metadata.height <= 0:
            raise ValueError(f"Media has no usable video stream: {source}")
        if not is_image and clip.source_start_us >= metadata.duration_us:
            raise ValueError(f"source_start_us is outside the video duration: {source}")
        inputs_to_render.append((clip, source, metadata, is_image))
    if bgm_path is not None:
        bgm_path = bgm_path.expanduser().resolve()
        metadata = _probe(bgm_path)
        if not metadata.has_audio or metadata.duration_us <= 0:
            raise ValueError(f"BGM has no usable audio stream: {bgm_path}")

    work_dir = work_dir.expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    render_dir = Path(tempfile.mkdtemp(prefix="render-", dir=work_dir))
    normalized: list[TimelineClip] = []
    cursor = 0
    for index, (clip, source, metadata, is_image) in enumerate(inputs_to_render):
        duration_us = clip.effective_source_duration_us
        if not is_image:
            duration_us = min(duration_us, metadata.duration_us - clip.source_start_us)
        duration = duration_us / 1_000_000
        frames = max(1, round(duration * fps))
        duration_text = f"{frames / fps:.9f}"
        path = render_dir / f"clip_{index:06d}.mov"
        inputs = []
        if not is_image:
            inputs += ["-ss", f"{clip.source_start_us / 1_000_000:.9f}"]
        inputs += ["-i", str(source)]
        video_filter = (
            "setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={duration_text},"
        )
        # dar includes non-square sample pixels; resize before resetting SAR.
        video_filter += (
            f"scale=w='if(gt(dar,{width}/{height}),{width},"
            f"max(2,trunc({height}*dar/2)*2))':"
            f"h='if(gt(dar,{width}/{height}),max(2,trunc({width}/dar/2)*2),{height})',"
            f"setsar=1,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"fps={fps},format=yuv420p"
        )
        audio_filter = (
            "[0:a:0]asetpts=PTS-STARTPTS,aresample=48000,"
            "aformat=sample_rates=48000:channel_layouts=stereo,"
            f"apad,atrim=duration={duration_text}[a]"
            if metadata.has_audio and not mute_source else
            "anullsrc=channel_layout=stereo:sample_rate=48000,"
            f"atrim=duration={duration_text}[a]"
        )
        _ffmpeg([
            *inputs, "-filter_complex", f"[0:v:0]{video_filter}[v];{audio_filter}",
            "-map", "[v]", "-map", "[a]", "-t", duration_text,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "pcm_s16le", str(path),
        ], stage=f"normalizing {source}")
        actual_duration = _probe(path).duration_us
        normalized.append(replace(
            clip, source_path=path, source_start_us=0,
            source_duration_us=actual_duration, timeline_start_us=cursor,
            timeline_duration_us=actual_duration,
        ))
        cursor += actual_duration

    concat_path = render_dir / "concat.txt"
    concat_path.write_text(
        "".join(f"file '{clip.source_path.name}'\n" for clip in normalized), encoding="ascii",
    )
    concat_input = ["-f", "concat", "-safe", "1", "-i", str(concat_path)]
    audio_path = render_dir / "audio.m4a"
    audio_inputs = [*concat_input]
    audio_map = ["-map", "0:a:0"]
    if bgm_path is not None:
        audio_inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
        audio_map = [
            "-filter_complex",
            "[1:a:0]aresample=48000,"
            "aformat=sample_rates=48000:channel_layouts=stereo,"
            f"volume={bgm_volume}[bgm];"
            "[0:a:0][bgm]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[a]",
            "-map", "[a]",
        ]
    _ffmpeg([
        *audio_inputs, *audio_map, "-t", f"{cursor / 1_000_000:.9f}",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(audio_path),
    ], stage=f"mixing audio for {output_path}")
    assembled = render_dir / "assembled.mp4"
    _ffmpeg([
        *concat_input, "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
        "-c", "copy", "-movflags", "+faststart", str(assembled),
    ], stage=f"assembling {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects even racing files and dangling symlinks.
    with output_path.open("xb") as destination, assembled.open("rb") as source_file:
        shutil.copyfileobj(source_file, destination)
    return RenderedTimeline(output_path, tuple(normalized), audio_path)
