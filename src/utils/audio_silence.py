"""
Audio silence detection helpers backed by ffmpeg.
"""
from __future__ import annotations

import re
import subprocess
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB")
SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
SILENCE_END_RE = re.compile(
    r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)"
)


@dataclass(frozen=True)
class SilenceInterval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def midpoint(self) -> float:
        return (self.start + self.end) / 2.0


class AudioSilenceProfile:
    def __init__(self, silences: list[SilenceInterval]):
        self.silences = sorted(silences, key=lambda item: item.start)

    def between(self, start: float, end: float, *, min_duration: float = 0.12) -> list[SilenceInterval]:
        result: list[SilenceInterval] = []
        for silence in self.silences:
            if silence.end <= start:
                continue
            if silence.start >= end:
                break
            clipped = SilenceInterval(max(start, silence.start), min(end, silence.end))
            if clipped.duration >= min_duration:
                result.append(clipped)
        return result


def _run_ffmpeg(args: list[str]) -> str:
    result = subprocess.run(
        ["ffmpeg", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return (result.stderr or "") + (result.stdout or "")


def _project_venv_python() -> Path | None:
    candidate = Path(__file__).resolve().parents[2] / "venv" / "bin" / "python"
    return candidate if candidate.exists() else None


def _detect_silences_with_project_venv(audio_path: Path) -> list[SilenceInterval] | None:
    venv_python = _project_venv_python()
    if venv_python is None:
        return None

    helper = """
import json
import sys
from pydub import AudioSegment, silence

audio = AudioSegment.from_file(sys.argv[1])
threshold = max(-45.0, min(-18.0, audio.dBFS - 12.0))
intervals = silence.detect_silence(
    audio,
    min_silence_len=140,
    silence_thresh=threshold,
    seek_step=10,
)
print(json.dumps({"silences": intervals}, ensure_ascii=False))
""".strip()

    result = subprocess.run(
        [str(venv_python), "-c", helper, str(audio_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    return [
        SilenceInterval(start=start_ms / 1000.0, end=end_ms / 1000.0)
        for start_ms, end_ms in payload.get("silences", [])
        if end_ms > start_ms
    ]


def _detect_mean_volume(audio_path: Path) -> float | None:
    output = _run_ffmpeg(
        [
            "-v",
            "info",
            "-i",
            str(audio_path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ]
    )
    match = MEAN_VOLUME_RE.search(output)
    return float(match.group(1)) if match else None


def _detect_silences(audio_path: Path, noise_db: float, *, min_silence: float) -> list[SilenceInterval]:
    output = _run_ffmpeg(
        [
            "-v",
            "info",
            "-i",
            str(audio_path),
            "-af",
            f"silencedetect=noise={noise_db:.1f}dB:d={min_silence:.2f}",
            "-f",
            "null",
            "-",
        ]
    )

    silences: list[SilenceInterval] = []
    pending_start: float | None = None
    for line in output.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue

        end_match = SILENCE_END_RE.search(line)
        if end_match and pending_start is not None:
            silences.append(
                SilenceInterval(
                    start=pending_start,
                    end=float(end_match.group(1)),
                )
            )
            pending_start = None

    return silences


@lru_cache(maxsize=16)
def load_audio_silence_profile(audio_path: str | Path) -> AudioSilenceProfile | None:
    path = Path(audio_path).expanduser().resolve()
    if not path.exists():
        return None

    pydub_silences = _detect_silences_with_project_venv(path)
    if pydub_silences:
        return AudioSilenceProfile(pydub_silences)

    mean_volume = _detect_mean_volume(path)
    if mean_volume is None:
        noise_db = -26.0
    else:
        noise_db = max(-45.0, min(-18.0, mean_volume - 12.0))

    silences = _detect_silences(path, noise_db, min_silence=0.14)
    if not silences:
        return None
    return AudioSilenceProfile(silences)
