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
    collection_key: str = ""

    @property
    def effective_collection_key(self) -> str:
        return self.collection_key or str(self.path.parent.resolve())


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
                    collection_key=str(path.parent.resolve()),
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
        recent_collections: set[str] | None = None,
        used_collections: set[str] | None = None,
        rng: random.Random | None = None,
    ) -> ShotCandidate:
        exclude_paths = {path.resolve() for path in (exclude_paths or set())}
        used_paths = {path.resolve() for path in (used_paths or set())}
        recent_groups = set(recent_groups or set())
        used_groups = set(used_groups or set())
        recent_collections = set(recent_collections or set())
        used_collections = set(used_collections or set())
        rng = rng or random.Random()

        available = [shot for shot in self.shots if shot.path not in exclude_paths]
        if not available:
            available = self.shots

        unused = [shot for shot in available if shot.path not in used_paths]
        if unused:
            available = unused

        preference_tiers = (
            [
                shot
                for shot in available
                if shot.group_key not in recent_groups
                and shot.effective_collection_key not in recent_collections
                and shot.group_key not in used_groups
                and shot.effective_collection_key not in used_collections
            ],
            [
                shot
                for shot in available
                if shot.group_key not in recent_groups
                and shot.effective_collection_key not in recent_collections
            ],
            [shot for shot in available if shot.group_key not in recent_groups],
            [shot for shot in available if shot.effective_collection_key not in recent_collections],
            [shot for shot in available if shot.group_key not in used_groups],
            [shot for shot in available if shot.effective_collection_key not in used_collections],
        )
        for tier in preference_tiers:
            if tier:
                available = tier
                break

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
        by_collection: dict[str, list[ShotCandidate]] = {}
        for shot in shortlist:
            by_collection.setdefault(shot.effective_collection_key, []).append(shot)

        collection_diverse = [collection_shots[0] for collection_shots in by_collection.values()]
        pool = collection_diverse or shortlist
        pool = pool[: min(len(pool), 12)]
        if len(pool) == 1:
            return pool[0]

        weights: list[float] = []
        for shot in pool:
            gap = abs(shot.duration_us - target_duration_us)
            weight = 1.0 / (1.0 + (gap / 250_000))
            if shot.group_key not in recent_groups:
                weight *= 1.4
            if shot.effective_collection_key not in recent_collections:
                weight *= 1.35
            if shot.group_key not in used_groups:
                weight *= 1.2
            if shot.effective_collection_key not in used_collections:
                weight *= 1.15
            weights.append(weight)
        return rng.choices(pool, weights=weights, k=1)[0]
