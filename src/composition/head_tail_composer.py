"""
Compose a new timeline by keeping the original head and filling the rest from a shot pool.
"""
from __future__ import annotations

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
        for slot in self._build_tail_slots(artifacts, head_duration_us, total_duration_us):
            candidate = self.shot_pool.pick(
                slot.duration_us,
                exclude_paths={last_pool_path} if last_pool_path else set(),
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
        slots: list[_TimelineSlot] = []
        cursor = head_duration_us

        if not artifacts.transcript_segments:
            return [
                _TimelineSlot(
                    start_us=head_duration_us,
                    duration_us=total_duration_us - head_duration_us,
                    kind="tail",
                )
            ]

        for segment in artifacts.transcript_segments:
            seg_start = max(segment.start_us, head_duration_us)
            seg_end = min(segment.end_us, total_duration_us)
            if seg_end <= seg_start:
                continue

            if seg_start > cursor:
                slots.append(
                    _TimelineSlot(
                        start_us=cursor,
                        duration_us=seg_start - cursor,
                        kind="gap",
                    )
                )
                cursor = seg_start

            if seg_end > cursor:
                slots.append(
                    _TimelineSlot(
                        start_us=cursor,
                        duration_us=seg_end - cursor,
                        kind="subtitle",
                        text=segment.text,
                    )
                )
                cursor = seg_end

        if cursor < total_duration_us:
            slots.append(
                _TimelineSlot(
                    start_us=cursor,
                    duration_us=total_duration_us - cursor,
                    kind="tail",
                )
            )

        return [slot for slot in slots if slot.duration_us > 0]
