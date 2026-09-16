"""
场景检测器测试
"""
import sys
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


class _MockFrameTimecode:
    """Mock for scenedetect FrameTimecode"""

    def __init__(self, seconds: float, fps: float = 30.0):
        self._seconds = seconds
        self._fps = fps

    def get_seconds(self) -> float:
        return self._seconds

    def get_timecode(self) -> str:
        total_seconds = self._seconds
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


class TestSceneDetectScenes(unittest.TestCase):
    """detect_scenes 方法测试"""

    def _make_scene_list(self, boundaries):
        """Create mock scene list from (start, end) second tuples"""
        return [(_MockFrameTimecode(s), _MockFrameTimecode(e)) for s, e in boundaries]

    def _install_scenedetect_mocks(self, mock_scene_list, mock_video):
        """Install mocks for scenedetect modules in sys.modules"""
        mock_open_video = MagicMock(return_value=mock_video)
        mock_scene_manager_cls = MagicMock()
        mock_manager = MagicMock()
        mock_scene_manager_cls.return_value = mock_manager
        mock_manager.get_scene_list.return_value = mock_scene_list

        mock_adaptive_detector_cls = MagicMock()
        mock_content_detector_cls = MagicMock()
        mock_split_video_ffmpeg = MagicMock()

        mock_scenedetect = MagicMock()
        mock_scenedetect.open_video = mock_open_video
        mock_scenedetect.SceneManager = mock_scene_manager_cls
        mock_scenedetect.frame_timecode = MagicMock()

        mock_detectors = MagicMock()
        mock_detectors.AdaptiveDetector = mock_adaptive_detector_cls
        mock_detectors.ContentDetector = mock_content_detector_cls

        mock_video_splitter = MagicMock()
        mock_video_splitter.split_video_ffmpeg = mock_split_video_ffmpeg

        sys.modules["scenedetect"] = mock_scenedetect
        sys.modules["scenedetect.detectors"] = mock_detectors
        sys.modules["scenedetect.video_splitter"] = mock_video_splitter

        return {
            "open_video": mock_open_video,
            "scene_manager_cls": mock_scene_manager_cls,
            "manager": mock_manager,
            "adaptive_detector_cls": mock_adaptive_detector_cls,
            "content_detector_cls": mock_content_detector_cls,
            "split_video_ffmpeg": mock_split_video_ffmpeg,
        }

    def _remove_scenedetect_mocks(self):
        """Remove scenedetect mocks from sys.modules"""
        for key in ["scenedetect", "scenedetect.detectors", "scenedetect.video_splitter", "scenedetect.frame_timecode"]:
            sys.modules.pop(key, None)

    def tearDown(self):
        self._remove_scenedetect_mocks()

    def test_detect_scenes_creates_adaptive_detector_with_correct_params(self):
        """测试 detect_scenes 使用正确参数创建 AdaptiveDetector"""
        from src.core.scene_detector import SceneDetector

        mock_video = MagicMock()
        mock_video.frame_rate = 30.0
        mock_video.base_timecode = _MockFrameTimecode(0.0)
        mocks = self._install_scenedetect_mocks(
            self._make_scene_list([(0.0, 5.0), (5.0, 10.0)]),
            mock_video,
        )

        detector = SceneDetector(threshold=27.0, adaptive_threshold=3.0, min_scene_length=0.5)
        scenes_info, scene_list = detector.detect_scenes("/fake/video.mp4")

        mocks["adaptive_detector_cls"].assert_called_once_with(
            adaptive_threshold=3.0,
            min_content_val=27.0,
            min_scene_len=15,
        )
        self.assertEqual(len(scenes_info), 2)
        self.assertEqual(scenes_info[0]["scene_number"], 1)
        self.assertAlmostEqual(scenes_info[0]["duration"], 5.0)
        self.assertAlmostEqual(scenes_info[1]["duration"], 5.0)

    def test_detect_scenes_returns_full_video_as_single_scene_when_no_cuts(self):
        """测试无切点时整段视频作为一个场景返回"""
        from src.core.scene_detector import SceneDetector

        mock_video = MagicMock()
        mock_video.frame_rate = 30.0
        mock_video.base_timecode = _MockFrameTimecode(0.0)
        mock_duration = MagicMock()
        mock_duration.get_seconds.return_value = 60.0
        mock_video.duration = mock_duration

        mocks = self._install_scenedetect_mocks([], mock_video)

        mock_ft_cls = MagicMock(return_value=_MockFrameTimecode(60.0))
        sys.modules["scenedetect.frame_timecode"] = MagicMock()
        sys.modules["scenedetect.frame_timecode"].FrameTimecode = mock_ft_cls

        detector = SceneDetector()
        scenes_info, scene_list = detector.detect_scenes("/fake/long_video.mp4")

        self.assertEqual(len(scenes_info), 1)
        self.assertEqual(scenes_info[0]["scene_number"], 1)
        self.assertAlmostEqual(scenes_info[0]["duration"], 60.0)

    def test_split_video_creates_output_dir_and_calls_ffmpeg(self):
        """测试 split_video 创建目录并调用 ffmpeg"""
        from src.core.scene_detector import SceneDetector
        import tempfile
        import os

        mocks = self._install_scenedetect_mocks([], MagicMock())
        detector = SceneDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "scenes")
            scene_list = self._make_scene_list([(0.0, 5.0)])
            detector.split_video("/fake/video.mp4", scene_list, output_dir)

            self.assertTrue(os.path.isdir(output_dir))
            mocks["split_video_ffmpeg"].assert_called_once()
            call_kwargs = mocks["split_video_ffmpeg"].call_args[1]
            self.assertIn("Scene-$SCENE_NUMBER.mp4", call_kwargs["output_file_template"])


if __name__ == '__main__':
    unittest.main()
