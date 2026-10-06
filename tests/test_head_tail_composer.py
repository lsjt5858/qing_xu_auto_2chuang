"""
Head/tail composition tests.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from config.feature_flags import feature_flags
from src.composition import CompositionSettings, HeadTailComposer, ShotCandidate, ShotPoolIndex
from src.models import AnalysisArtifacts, SceneSegment, TimelineClip, TranscriptSegment


class TestHeadTailComposer(unittest.TestCase):
    def test_pool_internal_start_is_zero_unless_random_is_explicit(self):
        artifacts = AnalysisArtifacts(
            output_dir=Path("/tmp/output"), video_name="demo",
            original_video_path=None, processed_video_path=None,
            report_path=None, audio_path=None, audio_metadata=None,
            scenes=(), transcript_segments=(TranscriptSegment(0, 2_000_000, "slot"),),
        )
        pool = ShotPoolIndex([
            ShotCandidate(Path("/tmp/long.mp4"), 30_000_000, 320, 180, "g", 1),
        ])
        default = HeadTailComposer(pool, CompositionSettings(head_mode="none", random_seed=7))
        self.assertEqual(default.compose(artifacts)[0].source_start_us, 0)
        explicit = HeadTailComposer(pool, CompositionSettings(
            head_mode="none", random_seed=7, pool_clip_start="random",
        ))
        clip = explicit.compose(artifacts)[0]
        self.assertGreater(clip.source_start_us, 0)
        self.assertLessEqual(clip.source_start_us + clip.timeline_duration_us, 30_000_000)

    def test_compose_splits_tail_when_prevent_frame_extension_enabled(self):
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
                ShotCandidate(Path("/tmp/pool_c.mp4"), 1_900_000, 1920, 1080, "group-c", 1),
            ]
        )
        composer = HeadTailComposer(
            shot_pool,
            CompositionSettings(head_mode="first-scene", random_seed=7),
        )

        timeline = composer.compose(artifacts)
        tail_clips = timeline[1:]

        self.assertEqual(len(timeline), 3)
        self.assertEqual(timeline[0].role, "head")
        self.assertEqual(timeline[0].timeline_duration_us, 2_000_000)
        self.assertEqual(tail_clips[0].timeline_start_us, 2_000_000)
        self.assertEqual(sum(item.timeline_duration_us for item in tail_clips), 4_000_000)
        self.assertTrue(all(item.timeline_duration_us <= 2_300_000 for item in tail_clips))
        self.assertTrue(all(isinstance(item, TimelineClip) for item in timeline))

    def test_compose_keeps_old_single_clip_behavior_when_flag_disabled(self):
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
                ShotCandidate(Path("/tmp/pool_c.mp4"), 1_900_000, 1920, 1080, "group-c", 1),
            ]
        )
        composer = HeadTailComposer(
            shot_pool,
            CompositionSettings(head_mode="first-scene", random_seed=7),
        )

        with feature_flags.override(prevent_video_frame_extension=False):
            timeline = composer.compose(artifacts)

        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[1].timeline_start_us, 2_000_000)
        self.assertEqual(timeline[1].timeline_duration_us, 4_000_000)
        self.assertEqual(timeline[1].effective_source_duration_us, 4_000_000)


if __name__ == "__main__":
    unittest.main()
