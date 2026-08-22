"""
场景检测器测试
"""
import unittest
from unittest.mock import MagicMock, PropertyMock, patch


class TestSceneDetector(unittest.TestCase):
    """场景检测器测试用例"""

    def test_init_defaults_load_config_values(self):
        """测试初始化时默认值从配置加载"""
        from src.core.scene_detector import SceneDetector
        from config.settings import SCENE_DETECTION

        detector = SceneDetector()
        self.assertEqual(detector.content_threshold, SCENE_DETECTION["threshold"])
        self.assertEqual(detector.adaptive_threshold, SCENE_DETECTION["adaptive_threshold"])
        self.assertEqual(detector.min_scene_length, SCENE_DETECTION["min_scene_length"])

    def test_init_accepts_explicit_parameters(self):
        """测试初始化时可显式指定参数"""
        from src.core.scene_detector import SceneDetector

        detector = SceneDetector(
            threshold=15.0,
            adaptive_threshold=2.5,
            min_scene_length=1.0,
        )
        self.assertEqual(detector.content_threshold, 15.0)
        self.assertEqual(detector.adaptive_threshold, 2.5)
        self.assertEqual(detector.min_scene_length, 1.0)

    def test_detection_config_returns_readonly_snapshot(self):
        """测试 detection_config 返回只读配置快照"""
        from src.core.scene_detector import SceneDetector

        detector = SceneDetector(threshold=20.0, adaptive_threshold=3.0, min_scene_length=0.5)
        config = detector.detection_config

        self.assertEqual(config["detector_type"], "adaptive")
        self.assertEqual(config["content_threshold"], 20.0)
        self.assertEqual(config["adaptive_threshold"], 3.0)
        self.assertEqual(config["min_scene_length"], 0.5)

        with self.assertRaises(TypeError):
            config["detector_type"] = "content"


if __name__ == '__main__':
    unittest.main()
