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

    def test_build_video_filter_normalizes_odd_bar_height(self):
        """测试奇数黑边高度会自动归一成偶数，避免输出尺寸被编码器截断"""
        filter_text = self.remover.build_video_filter(127)
        self.assertEqual(filter_text, "crop=iw:ih-128:0:0,pad=iw:ih+128:0:0:black")

    def test_build_video_filter_with_watermark_filters(self):
        """测试水印清理滤镜会拼接到裁切滤镜前面"""
        filter_text = self.remover.build_video_filter(
            96,
            pre_filters=["removelogo=f='/tmp/watermark_mask.png'"]
        )
        self.assertEqual(
            filter_text,
            (
                "removelogo=f='/tmp/watermark_mask.png',"
                "crop=iw:ih-96:0:0,pad=iw:ih+96:0:0:black"
            )
        )

    def test_build_watermark_cleanup_filters(self):
        """测试默认水印滤镜参数按 1920x1080 基准计算"""
        filters = self.remover.build_watermark_cleanup_filters(
            "/tmp/watermark_mask.png",
            1920,
            1080
        )
        self.assertEqual(
            filters,
            ["removelogo=f='/tmp/watermark_mask.png'"]
        )

    def test_select_best_watermark_cluster_filters_out_stray_points(self):
        """测试连通组件聚类会保留主水印簇并剔除孤立误检点"""
        mask = np.zeros((80, 200), dtype=np.uint8)
        mask[48:58, 88:98] = 255
        mask[50:62, 99:112] = 255
        mask[54:60, 113:120] = 255
        mask[4:6, 180:182] = 255
        mask[10:12, 185:187] = 255

        selected = self.remover._select_best_watermark_cluster(mask, 200, 80)

        self.assertGreater(int(selected[54:60, 92:116].sum()), 0)
        self.assertEqual(int(selected[4:12, 176:190].sum()), 0)


if __name__ == "__main__":
    unittest.main()
