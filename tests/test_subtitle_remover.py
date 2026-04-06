"""
字幕去除器测试
"""
import unittest

import numpy as np

from src.core.subtitle_remover import SubtitleRemover


class TestSubtitleRemover(unittest.TestCase):
    """字幕去除器测试用例"""

    def setUp(self):
        self.remover = SubtitleRemover()

    def test_estimate_bottom_black_bar_height(self):
        """测试估算底部黑边高度"""
        frame = np.full((100, 200, 3), 255, dtype=np.uint8)
        frame[-18:, :, :] = 0

        height = self.remover.estimate_bottom_black_bar_height(
            frame,
            dark_threshold=20,
            dark_pixel_ratio=0.95
        )

        self.assertEqual(height, 18)

    def test_build_video_filter(self):
        """测试 ffmpeg 滤镜拼接"""
        filter_text = self.remover.build_video_filter(96)
        self.assertEqual(filter_text, "crop=iw:ih-96:0:0,pad=iw:ih+96:0:0:black")


if __name__ == "__main__":
    unittest.main()
