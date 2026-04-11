"""
Head/tail composition tests.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from src.composition import CompositionSettings, HeadTailComposer, ShotCandidate, ShotPoolIndex
from src.models import AnalysisArtifacts, SceneSegment, TimelineClip, TranscriptSegment


class TestHeadTailComposer(unittest.TestCase):
    def test_compose_keeps_head_and_fills_tail_by_slots(self):
        artifacts = AnalysisArtifacts(
            output_dir=Path("/tmp/output"),
            video_name="demo",
            original_video_path=Path("/tmp/input.mp4"),
            processed_video_path=Path("/tmp/processed.mp4"),
            report_path=None,
            audio_path=None,
            audio_metadata=None,
            scenes=(
                SceneSegment(1, Path("/tmp/scene1.mp4"), 0, 2_000_000),
                SceneSegment(2, Path("/tmp/scene2.mp4"), 2_000_000, 6_000_000),
            ),
            transcript_segments=(
                TranscriptSegment(0, 2_000_000, "head"),
                TranscriptSegment(2_000_000, 4_000_000, "slot1"),
                TranscriptSegment(4_500_000, 6_000_000, "slot2"),
            ),
        )
        shot_pool = ShotPoolIndex(
            [
                ShotCandidate(Path("/tmp/pool_a.mp4"), 2_100_000, 1920, 1080, "group-a", 1),
                ShotCandidate(Path("/tmp/pool_b.mp4"), 2_300_000, 1920, 1080, "group-b", 1),
                ShotCandidate(Path("/tmp/pool_c.mp4"), 4_100_000, 1920, 1080, "group-c", 1),
            ]
        )
        composer = HeadTailComposer(
            shot_pool,
            CompositionSettings(head_mode="first-scene", random_seed=7),
        )

        timeline = composer.compose(artifacts)

        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0].role, "head")
        self.assertEqual(timeline[0].timeline_duration_us, 2_000_000)
        self.assertEqual(timeline[1].timeline_start_us, 2_000_000)
        self.assertEqual(timeline[1].timeline_duration_us, 4_000_000)
        self.assertTrue(all(isinstance(item, TimelineClip) for item in timeline))


if __name__ == "__main__":
    unittest.main()
