"""
Index reusable shot clips from a pool directory.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from src.models import probe_media


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


@dataclass(frozen=True)
class ShotCandidate:
    path: Path
    duration_us: int
    width: int
    height: int


class ShotPoolIndex:
    def __init__(self, shots: list[ShotCandidate]):
        self.shots = shots

    @classmethod
    def from_directory(cls, pool_dir: str | Path) -> "ShotPoolIndex":
        pool_dir = Path(pool_dir).expanduser().resolve()
        if not pool_dir.exists():
            raise FileNotFoundError(f"Shot pool directory not found: {pool_dir}")

        shots: list[ShotCandidate] = []
        for path in sorted(pool_dir.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            metadata = probe_media(path)
            if metadata.duration_us <= 0:
                continue
            shots.append(
                ShotCandidate(
                    path=metadata.path,
                    duration_us=metadata.duration_us,
                    width=metadata.width,
                    height=metadata.height,
                )
            )

        if not shots:
            raise ValueError(f"No usable video shots found in pool: {pool_dir}")
        return cls(shots)

    def pick(
        self,
        target_duration_us: int,
        *,
        exclude_paths: set[Path] | None = None,
        rng: random.Random | None = None,
    ) -> ShotCandidate:
        exclude_paths = {path.resolve() for path in (exclude_paths or set())}
        rng = rng or random.Random()

        available = [shot for shot in self.shots if shot.path not in exclude_paths]
        if not available:
            available = self.shots

        longer = [shot for shot in available if shot.duration_us >= target_duration_us]
        if longer:
            min_gap = min(shot.duration_us - target_duration_us for shot in longer)
            shortlist = [
                shot
                for shot in longer
                if (shot.duration_us - target_duration_us) <= min_gap + 300_000
            ]
            return rng.choice(shortlist)

        longest = max(available, key=lambda shot: shot.duration_us)
        fallback = [
            shot for shot in available if shot.duration_us == longest.duration_us
        ]
        return rng.choice(fallback)
