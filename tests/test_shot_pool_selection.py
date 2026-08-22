"""
Shot pool selection should avoid immediate repetition and prefer fresh groups.
"""
from __future__ import annotations

import random
import unittest
from pathlib import Path

from config.feature_flags import feature_flags
from src.composition.shot_pool import ShotCandidate, ShotPoolIndex


class TestShotPoolSelection(unittest.TestCase):
    def test_pick_prefers_unused_non_recent_groups(self):
        pool = ShotPoolIndex(
            [
                ShotCandidate(Path("/tmp/a_scene1.mp4"), 2_100_000, 1920, 1080, "group-a", 1),
                ShotCandidate(Path("/tmp/a_scene2.mp4"), 2_200_000, 1920, 1080, "group-a", 2),
                ShotCandidate(Path("/tmp/b_scene1.mp4"), 2_150_000, 1920, 1080, "group-b", 1),
                ShotCandidate(Path("/tmp/c_scene1.mp4"), 2_180_000, 1920, 1080, "group-c", 1),
            ]
        )

        shot = pool.pick(
            2_000_000,
            used_paths={Path("/tmp/b_scene1.mp4")},
            recent_groups={"group-a"},
            used_groups={"group-a", "group-b"},
            rng=random.Random(1),
        )

        self.assertEqual(shot.group_key, "group-c")

    def test_pick_prefers_fresh_collections_when_durations_are_similar(self):
        pool = ShotPoolIndex(
            [
                ShotCandidate(
                    Path("/tmp/set_a/a_scene1.mp4"),
                    2_100_000,
                    1920,
                    1080,
                    "group-a",
                    1,
                    "collection-a",
                ),
                ShotCandidate(
                    Path("/tmp/set_a/b_scene1.mp4"),
                    2_120_000,
                    1920,
                    1080,
                    "group-b",
                    1,
                    "collection-a",
                ),
                ShotCandidate(
                    Path("/tmp/set_b/c_scene1.mp4"),
                    2_140_000,
                    1920,
                    1080,
                    "group-c",
                    1,
                    "collection-b",
                ),
            ]
        )

        shot = pool.pick(
            2_000_000,
            recent_collections={"collection-a"},
            used_collections={"collection-a"},
            rng=random.Random(2),
        )

        self.assertEqual(shot.effective_collection_key, "collection-b")

    def test_pick_can_ignore_collection_diversity_when_flag_disabled(self):
        pool = ShotPoolIndex(
            [
                ShotCandidate(
                    Path("/tmp/set_a/a_scene1.mp4"),
                    2_100_000,
                    1920,
                    1080,
                    "group-a",
                    1,
                    "collection-a",
                ),
                ShotCandidate(
                    Path("/tmp/set_b/c_scene1.mp4"),
                    2_700_000,
                    1920,
                    1080,
                    "group-c",
                    1,
                    "collection-b",
                ),
            ]
        )

        with feature_flags.override(shot_pool_collection_diversity=False):
            shot = pool.pick(
                2_000_000,
                recent_collections={"collection-a"},
                used_collections={"collection-a"},
                rng=random.Random(1),
            )

        self.assertEqual(shot.effective_collection_key, "collection-a")
