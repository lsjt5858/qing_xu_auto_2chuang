"""
Subtitle segmentation tests.
"""
from __future__ import annotations

import unittest

from src.utils.subtitle_segmentation import split_subtitle_segment, split_transcript_segments


class TestSubtitleSegmentation(unittest.TestCase):
    def test_split_long_segment_by_punctuation_and_length(self):
        segments = split_subtitle_segment(
            0.0,
            19.0,
            "待在水内才会淹死,你只有不停地往前游。那些从一开始就选择放弃的人,他不会失败。因为他们从一开始就失败了。失败并不可怕,太怕失败了,才真正可怕。我们只有从失败。",
        )
        self.assertGreaterEqual(len(segments), 5)
        self.assertAlmostEqual(segments[0]["start"], 0.0)
        self.assertAlmostEqual(segments[-1]["end"], 19.0)
        self.assertTrue(all(len(item["text"]) <= 22 for item in segments))

    def test_split_transcript_segments_applies_to_list(self):
        items = split_transcript_segments(
            [
                {"start": 0.0, "end": 6.0, "text": "我们都没有上帝视角。爱和委屈都要大声说出来。"},
                {"start": 6.0, "end": 8.0, "text": "再绝望,也请求希望。"},
            ]
        )
        self.assertGreater(len(items), 2)
        self.assertAlmostEqual(items[0]["start"], 0.0)
        self.assertAlmostEqual(items[-1]["end"], 8.0)


if __name__ == "__main__":
    unittest.main()
