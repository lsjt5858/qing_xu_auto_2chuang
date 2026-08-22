"""
VideoAnalyzer 场景检测元数据报告测试
"""
import sys
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Mock heavy optional dependencies before importing src.core.video_analyzer
_sys_mock = MagicMock()
sys.modules.setdefault("moviepy", _sys_mock)
sys.modules.setdefault("cv2", _sys_mock)
sys.modules.setdefault("numpy", _sys_mock)

# Pre-import video_analyzer module so @patch can resolve its attributes
import src.core.video_analyzer  # noqa: E402


class TestVideoAnalyzerSceneMetadata(unittest.TestCase):
    """测试场景检测配置元数据写入报告"""

    @patch("src.core.video_analyzer.Transcriber")
    @patch("src.core.video_analyzer.AudioExtractor")
    @patch("src.core.video_analyzer.SceneDetector")
    def test_analyze_scenes_passes_threshold_to_detector_and_saves_config(
        self,
        mock_detector_cls,
        mock_audio_cls,
        mock_transcriber_cls,
    ):
        """测试 analyze_scenes 传递阈值并保存检测配置"""
        from src.core.video_analyzer import VideoAnalyzer

        mock_detector = MagicMock()
        mock_detector.detection_config = {
            "detector_type": "adaptive",
            "content_threshold": 20.0,
            "adaptive_threshold": 3.0,
            "min_scene_length": 0.5,
        }
        mock_detector.detect_scenes.return_value = (
            [{"scene_number": 1, "start_time": 0.0, "end_time": 10.0, "duration": 10.0,
              "start_timecode": "00:00:00.000", "end_timecode": "00:00:10.000"}],
            [],
        )
        mock_detector_cls.return_value = mock_detector

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = VideoAnalyzer("/fake/input.mp4", base_output_dir=tmpdir)
            scenes_info = analyzer.analyze_scenes(threshold=20.0)

            mock_detector_cls.assert_called_once_with(threshold=20.0)
            self.assertEqual(len(scenes_info), 1)
            self.assertEqual(
                analyzer.scene_detection_config["detector_type"], "adaptive"
            )
            self.assertAlmostEqual(
                analyzer.scene_detection_config["content_threshold"], 20.0
            )

    @patch("src.core.video_analyzer.Transcriber")
    @patch("src.core.video_analyzer.AudioExtractor")
    @patch("src.core.video_analyzer.SceneDetector")
    def test_generate_report_includes_scene_detection_metadata(
        self,
        mock_detector_cls,
        mock_audio_cls,
        mock_transcriber_cls,
    ):
        """测试 generate_report 包含场景检测元数据"""
        from src.core.video_analyzer import VideoAnalyzer

        mock_detector = MagicMock()
        mock_detector.detection_config = {
            "detector_type": "adaptive",
            "content_threshold": 27.0,
            "adaptive_threshold": 3.0,
            "min_scene_length": 0.5,
        }
        mock_detector.detect_scenes.return_value = (
            [{"scene_number": 1, "start_time": 0.0, "end_time": 10.0, "duration": 10.0,
              "start_timecode": "00:00:00.000", "end_timecode": "00:00:10.000"}],
            [],
        )
        mock_detector_cls.return_value = mock_detector

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = VideoAnalyzer("/fake/input.mp4", base_output_dir=tmpdir)
            scenes_info = analyzer.analyze_scenes(threshold=27.0)
            report = analyzer.generate_report(scenes_info, None)

            self.assertIn("scene_detection", report)
            self.assertEqual(report["scene_detection"]["detector_type"], "adaptive")
            self.assertAlmostEqual(report["scene_detection"]["content_threshold"], 27.0)
            self.assertAlmostEqual(report["scene_detection"]["adaptive_threshold"], 3.0)
            self.assertAlmostEqual(report["scene_detection"]["min_scene_length"], 0.5)

            report_path = os.path.join(analyzer.output_dir, "report.json")
            with open(report_path, "r", encoding="utf-8") as f:
                saved_report = json.load(f)
            self.assertIn("scene_detection", saved_report)
            self.assertEqual(saved_report["scene_detection"]["detector_type"], "adaptive")

    def test_generate_report_without_scene_detection_sets_empty_metadata(self):
        """测试未调用 analyze_scenes 时 report 中 scene_detection 为空"""
        from src.core.video_analyzer import VideoAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = VideoAnalyzer("/fake/input.mp4", base_output_dir=tmpdir)
            report = analyzer.generate_report(None, None)

            self.assertIn("scene_detection", report)
            self.assertIsNone(report["scene_detection"])


if __name__ == "__main__":
    unittest.main()
