"""
Compose a new timeline by keeping the original head and filling the rest from a shot pool.
"""
from __future__ import annotations

from collections import deque
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from src.models import AnalysisArtifacts, TimelineClip

from .shot_pool import ShotPoolIndex


@dataclass(frozen=True)
class CompositionSettings:
    head_mode: str = "first-scene"
    head_duration_us: int | None = None
    random_seed: int | None = None
    min_visual_slot_us: int = 2_200_000
    recent_group_window: int = 4


@dataclass(frozen=True)
class _TimelineSlot:
    start_us: int
    duration_us: int
    kind: str
    text: str = ""


class HeadTailComposer:
    def __init__(self, shot_pool: ShotPoolIndex, settings: CompositionSettings | None = None):
        self.shot_pool = shot_pool
        self.settings = settings or CompositionSettings()
        self.rng = random.Random(self.settings.random_seed)

    def compose(self, artifacts: AnalysisArtifacts) -> list[TimelineClip]:
        total_duration_us = artifacts.total_duration_us
        if total_duration_us <= 0:
            raise ValueError("Artifacts do not provide a usable total duration")

        head_duration_us = self._resolve_head_duration(artifacts, total_duration_us)
        timeline: list[TimelineClip] = []

        head_source = artifacts.processed_video_path or artifacts.original_video_path
        if head_duration_us > 0 and head_source is not None:
            timeline.append(
                TimelineClip(
                    source_path=head_source,
                    timeline_start_us=0,
                    timeline_duration_us=head_duration_us,
                    source_start_us=0,
                    source_duration_us=head_duration_us,
                    role="head",
                    label=head_source.name,
                )
            )

        if head_duration_us >= total_duration_us:
            return timeline

        last_pool_path: Path | None = None
        used_paths: set[Path] = set()
        used_groups: set[str] = set()
        used_collections: set[str] = set()
        recent_groups: deque[str] = deque(maxlen=max(1, self.settings.recent_group_window))
        recent_collections: deque[str] = deque(maxlen=max(1, self.settings.recent_group_window))

        for slot in self._build_tail_slots(artifacts, head_duration_us, total_duration_us):
            candidate = self.shot_pool.pick(
                slot.duration_us,
                exclude_paths={last_pool_path} if last_pool_path else set(),
                used_paths=used_paths,
                recent_groups=set(recent_groups),
                used_groups=used_groups,
                recent_collections=set(recent_collections),
                used_collections=used_collections,
                rng=self.rng,
            )
            source_max_offset = max(0, candidate.duration_us - slot.duration_us)
            source_start_us = (
                self.rng.randint(0, source_max_offset)
                if source_max_offset > 0
                else 0
            )
            timeline.append(
                TimelineClip(
                    source_path=candidate.path,
                    timeline_start_us=slot.start_us,
                    timeline_duration_us=slot.duration_us,
                    source_start_us=source_start_us,
                    source_duration_us=slot.duration_us,
                    role=f"pool:{slot.kind}",
                    label=slot.text or candidate.path.name,
                )
            )
            last_pool_path = candidate.path
            used_paths.add(candidate.path)
            used_groups.add(candidate.group_key)
            used_collections.add(candidate.effective_collection_key)
            recent_groups.append(candidate.group_key)
            recent_collections.append(candidate.effective_collection_key)

        return timeline

    def save_plan(self, output_path: str | Path, timeline: list[TimelineClip]) -> Path:
        output_path = Path(output_path)
        payload = [
            {
                "source_path": str(clip.source_path),
                "timeline_start_us": clip.timeline_start_us,
                "timeline_duration_us": clip.timeline_duration_us,
                "source_start_us": clip.source_start_us,
                "source_duration_us": clip.effective_source_duration_us,
                "role": clip.role,
                "label": clip.label,
            }
            for clip in timeline
        ]
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path

    def _resolve_head_duration(self, artifacts: AnalysisArtifacts, total_duration_us: int) -> int:
        if self.settings.head_mode == "none":
            return 0
        if self.settings.head_mode == "fixed-seconds":
            return min(self.settings.head_duration_us or 0, total_duration_us)
        if artifacts.scenes:
            return min(artifacts.scenes[0].duration_us, total_duration_us)
        if self.settings.head_duration_us:
            return min(self.settings.head_duration_us, total_duration_us)
        return min(total_duration_us, 3_000_000)

    def _build_tail_slots(
        self,
        artifacts: AnalysisArtifacts,
        head_duration_us: int,
        total_duration_us: int,
    ) -> list[_TimelineSlot]:
        if not artifacts.transcript_segments:
            return [
                _TimelineSlot(
                    start_us=head_duration_us,
                    duration_us=total_duration_us - head_duration_us,
                    kind="tail",
                )
            ]

        boundaries = sorted(
            {
                min(max(segment.end_us, head_duration_us), total_duration_us)
                for segment in artifacts.transcript_segments
                if segment.end_us > head_duration_us
            }
        )
        boundaries.append(total_duration_us)

        slots: list[_TimelineSlot] = []
        slot_start = head_duration_us
        for boundary in boundaries:
            if boundary <= slot_start:
                continue
            current_duration = boundary - slot_start
            if current_duration < self.settings.min_visual_slot_us and boundary != total_duration_us:
                continue

            label = self._label_for_range(artifacts, slot_start, boundary)
            slots.append(
                _TimelineSlot(
                    start_us=slot_start,
                    duration_us=current_duration,
                    kind="subtitle",
                    text=label,
                )
            )
            slot_start = boundary

        if slot_start < total_duration_us:
            remaining = total_duration_us - slot_start
            if slots and remaining < max(700_000, self.settings.min_visual_slot_us // 2):
                previous = slots[-1]
                slots[-1] = _TimelineSlot(
                    start_us=previous.start_us,
                    duration_us=previous.duration_us + remaining,
                    kind=previous.kind,
                    text=previous.text,
                )
            else:
                slots.append(
                    _TimelineSlot(
                        start_us=slot_start,
                        duration_us=remaining,
                        kind="tail",
                    )
                )

        return [slot for slot in slots if slot.duration_us > 0]

    def _label_for_range(self, artifacts: AnalysisArtifacts, start_us: int, end_us: int) -> str:
        texts = [
            segment.text
            for segment in artifacts.transcript_segments
            if segment.end_us > start_us and segment.start_us < end_us
        ]
        return " ".join(texts[:2]).strip()
