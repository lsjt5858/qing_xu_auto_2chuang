"""
Index reusable shot clips from a pool directory.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path

from src.models import probe_media


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


SCENE_SUFFIX_RE = re.compile(r"(?i)(.*?)(?:[_-]scene[-_]?(\d+))?$")


def _parse_group_key(path: Path) -> tuple[str, int | None]:
    match = SCENE_SUFFIX_RE.fullmatch(path.stem)
    if not match:
        return (f"{path.parent.resolve()}::{path.stem.lower()}", None)
    base_name = (match.group(1) or path.stem).rstrip("_- ").lower()
    scene_index = int(match.group(2)) if match.group(2) else None
    return (f"{path.parent.resolve()}::{base_name}", scene_index)


@dataclass(frozen=True)
class ShotCandidate:
    path: Path
    duration_us: int
    width: int
    height: int
    group_key: str
    scene_index: int | None = None


class ShotPoolIndex:
    def __init__(self, shots: list[ShotCandidate]):
        self.shots = shots

    @classmethod
    def from_directory(cls, pool_dir: str | Path) -> "ShotPoolIndex":
        if isinstance(pool_dir, str):
            pool_dir = pool_dir.strip()
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
            group_key, scene_index = _parse_group_key(path)
            shots.append(
                ShotCandidate(
                    path=metadata.path,
                    duration_us=metadata.duration_us,
                    width=metadata.width,
                    height=metadata.height,
                    group_key=group_key,
                    scene_index=scene_index,
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
        used_paths: set[Path] | None = None,
        recent_groups: set[str] | None = None,
        used_groups: set[str] | None = None,
        rng: random.Random | None = None,
    ) -> ShotCandidate:
        exclude_paths = {path.resolve() for path in (exclude_paths or set())}
        used_paths = {path.resolve() for path in (used_paths or set())}
        recent_groups = set(recent_groups or set())
        used_groups = set(used_groups or set())
        rng = rng or random.Random()

        available = [shot for shot in self.shots if shot.path not in exclude_paths]
        if not available:
            available = self.shots

        unused = [shot for shot in available if shot.path not in used_paths]
        if unused:
            available = unused

        non_recent = [shot for shot in available if shot.group_key not in recent_groups]
        if non_recent:
            available = non_recent

        fresh_groups = [shot for shot in available if shot.group_key not in used_groups]
        if fresh_groups:
            available = fresh_groups

        longer = [shot for shot in available if shot.duration_us >= target_duration_us]
        if longer:
            min_gap = min(shot.duration_us - target_duration_us for shot in longer)
            shortlist = [
                shot
                for shot in longer
                if (shot.duration_us - target_duration_us) <= min_gap + 500_000
            ]
        else:
            min_gap = min(target_duration_us - shot.duration_us for shot in available)
            shortlist = [
                shot
                for shot in available
                if (target_duration_us - shot.duration_us) <= min_gap + 400_000
            ]

        shortlist.sort(key=lambda shot: abs(shot.duration_us - target_duration_us))
        by_group: dict[str, list[ShotCandidate]] = {}
        for shot in shortlist:
            by_group.setdefault(shot.group_key, []).append(shot)

        diverse = [group_shots[0] for group_shots in by_group.values()]
        pool = diverse or shortlist
        return rng.choice(pool[: min(len(pool), 8)])
