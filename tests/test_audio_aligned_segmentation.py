"""
Subtitle splitting should honor detected silence gaps when available.
"""
from __future__ import annotations

import unittest

from src.utils.audio_silence import AudioSilenceProfile, SilenceInterval
from src.utils.subtitle_segmentation import split_subtitle_segment, split_transcript_segments


class TestAudioAlignedSegmentation(unittest.TestCase):
    def test_split_segment_uses_silence_gaps_for_boundaries(self):
        profile = AudioSilenceProfile(
            [
                SilenceInterval(0.0, 0.3),
                SilenceInterval(2.0, 2.4),
                SilenceInterval(4.0, 4.3),
                SilenceInterval(5.8, 6.0),
            ]
        )

        result = split_subtitle_segment(
            0.0,
            6.0,
            "你只有游,不停地往前游。那些从一开始就选择放弃的人。",
            silence_profile=profile,
        )

        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0]["start"], 0.3, places=2)
        self.assertAlmostEqual(result[0]["end"], 2.0, places=2)
        self.assertAlmostEqual(result[1]["start"], 2.4, places=2)
        self.assertAlmostEqual(result[1]["end"], 5.8, places=2)

    def test_existing_segments_are_realigned_to_silence_gaps(self):
        profile = AudioSilenceProfile(
            [
                SilenceInterval(0.0, 0.3),
                SilenceInterval(2.0, 2.4),
                SilenceInterval(4.0, 4.3),
                SilenceInterval(5.8, 6.0),
            ]
        )

        result = split_transcript_segments(
            [
                {"start": 0.0, "end": 1.8, "text": "你只有游,"},
                {"start": 1.8, "end": 4.6, "text": "不停地往前游。"},
                {"start": 4.6, "end": 6.0, "text": "那些从一开始就选择放弃的人。"},
            ],
            silence_profile=profile,
        )

        self.assertAlmostEqual(result[0]["start"], 0.3, places=2)
        self.assertAlmostEqual(result[0]["end"], 2.0, places=2)
        self.assertAlmostEqual(result[1]["start"], 2.4, places=2)
        self.assertAlmostEqual(result[1]["end"], 4.0, places=2)
        self.assertAlmostEqual(result[2]["start"], 4.3, places=2)
        self.assertAlmostEqual(result[2]["end"], 5.8, places=2)
