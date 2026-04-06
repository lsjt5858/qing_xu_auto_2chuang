"""
场景检测器测试
"""
import unittest
from src.core.scene_detector import SceneDetector


class TestSceneDetector(unittest.TestCase):
    """场景检测器测试用例"""
    
    def setUp(self):
        """测试前准备"""
        self.detector = SceneDetector(threshold=27.0)
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.detector.threshold, 27.0)
    
    def test_custom_threshold(self):
        """测试自定义阈值"""
        detector = SceneDetector(threshold=15.0)
        self.assertEqual(detector.threshold, 15.0)


if __name__ == '__main__':
    unittest.main()
