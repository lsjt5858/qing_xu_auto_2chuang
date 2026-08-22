# Adaptive Scene Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed ContentDetector with AdaptiveDetector, add min scene length filtering to suppress false cuts, preserve long shots, and expose detection metadata in reports without breaking existing CLI/API compatibility.

**Architecture:** We will update `config/settings.py` to add adaptive threshold defaults, refactor `SceneDetector` to use `AdaptiveDetector` with frame-accurate min scene length, add a `detection_config` property for metadata capture, then wire that metadata through `VideoAnalyzer` into `report.json`. Tests will use dependency injection/mocking to verify detector construction and result transformation without requiring scenedetect/cv2 to be installed in the test environment.

**Tech Stack:** Python 3.12+, PySceneDetect (AdaptiveDetector), unittest (existing test framework), mock/patch for dependency injection

---

### Task 1: Update Scene Detection Config in settings.py

**Files:**
- Modify: [config/settings.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/config/settings.py)
- Test: None (config only)

- [ ] **Step 1: Add adaptive threshold default to SCENE_DETECTION config**

Update `SCENE_DETECTION` dict to include `adaptive_threshold` key with default value `3.0`:

```python
SCENE_DETECTION = {
    "threshold": DEFAULT_THRESHOLD,
    "adaptive_threshold": 3.0,
    "min_scene_length": 0.5,
}
```

- [ ] **Step 2: Verify config syntax**

Run: `python3 -c "from config.settings import SCENE_DETECTION; print(SCENE_DETECTION)"`
Expected: Config prints without error, showing `threshold`, `adaptive_threshold`, and `min_scene_length` keys.

- [ ] **Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat(scene): add adaptive threshold config"
```

---

### Task 2: Write Failing Tests for SceneDetector Constructor and Config Snapshot

**Files:**
- Create: None
- Modify: [tests/test_scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_scene_detector.py)
- Test: [tests/test_scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_scene_detector.py)

- [ ] **Step 1: Replace existing test file with failing tests**

Completely replace the current `tests/test_scene_detector.py` content with:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scene_detector.py -v 2>&1 || python3 -m unittest tests.test_scene_detector -v`
Expected: FAIL with `AttributeError: 'SceneDetector' object has no attribute 'content_threshold'`

- [ ] **Step 3: Commit failing test**

```bash
git add tests/test_scene_detector.py
git commit -m "test(scene): add detector constructor and config snapshot tests"
```

---

### Task 3: Implement SceneDetector Constructor and Config Snapshot

**Files:**
- Modify: [src/core/scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/src/core/scene_detector.py)
- Test: [tests/test_scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_scene_detector.py)

- [ ] **Step 1: Update imports and constructor in scene_detector.py**

Replace the first 21 lines (up through `__init__` docstring close) with:

```python
"""
场景检测模块 - 负责视频分镜检测和分割
"""
import os
from types import MappingProxyType
from scenedetect import open_video, SceneManager
from scenedetect.detectors import AdaptiveDetector
from scenedetect.frame_timecode import FrameTimecode
from scenedetect.video_splitter import split_video_ffmpeg
from config.settings import SCENE_DETECTION


class SceneDetector:
    """视频场景检测器 - 使用自适应阈值检测真实画面切换"""

    def __init__(
        self,
        threshold: float | None = None,
        adaptive_threshold: float | None = None,
        min_scene_length: float | None = None,
    ):
        """
        初始化场景检测器

        Args:
            threshold: 内容变化最低阈值 (0-255)，值越小越敏感
            adaptive_threshold: 自适应变化倍率，默认 3.0
            min_scene_length: 最短镜头时长（秒），小于此时长的误检片段会被合并
        """
        self.content_threshold = (
            float(threshold) if threshold is not None else float(SCENE_DETECTION["threshold"])
        )
        self.adaptive_threshold = (
            float(adaptive_threshold)
            if adaptive_threshold is not None
            else float(SCENE_DETECTION["adaptive_threshold"])
        )
        self.min_scene_length = (
            float(min_scene_length)
            if min_scene_length is not None
            else float(SCENE_DETECTION["min_scene_length"])
        )

    @property
    def detection_config(self) -> MappingProxyType:
        """返回检测配置的只读快照，用于写入报告"""
        return MappingProxyType(
            {
                "detector_type": "adaptive",
                "content_threshold": self.content_threshold,
                "adaptive_threshold": self.adaptive_threshold,
                "min_scene_length": self.min_scene_length,
            }
        )

    @property
    def threshold(self) -> float:
        """向后兼容：旧代码访问 threshold 时返回 content_threshold"""
        return self.content_threshold
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scene_detector.py::TestSceneDetector::test_init_defaults_load_config_values -v 2>&1 || python3 -m unittest tests.test_scene_detector.TestSceneDetector.test_init_defaults_load_config_values -v`
Expected: PASS for the constructor tests.

- [ ] **Step 3: Run all detector tests**

Run: `python3 -m pytest tests/test_scene_detector.py -v 2>&1 || python3 -m unittest tests.test_scene_detector -v`
Expected: All three tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/core/scene_detector.py tests/test_scene_detector.py
git commit -m "feat(scene): add adaptive detector constructor and config snapshot"
```

---

### Task 4: Write Failing Tests for detect_scenes Method

**Files:**
- Modify: [tests/test_scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_scene_detector.py)
- Test: [tests/test_scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_scene_detector.py)

- [ ] **Step 1: Add mock FrameTimecode and detect_scenes tests**

Append the following test class to `tests/test_scene_detector.py` (before `if __name__ == '__main__'`):

```python
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

    def _make_scene_list(self, boundaries: list[tuple[float, float]]) -> list:
        """Create mock scene list from (start, end) second tuples"""
        return [(_MockFrameTimecode(s), _MockFrameTimecode(e)) for s, e in boundaries]

    @patch("src.core.scene_detector.split_video_ffmpeg")
    @patch("src.core.scene_detector.AdaptiveDetector")
    @patch("src.core.scene_detector.SceneManager")
    @patch("src.core.scene_detector.open_video")
    def test_detect_scenes_creates_adaptive_detector_with_correct_params(
        self,
        mock_open_video,
        mock_scene_manager_cls,
        mock_adaptive_detector_cls,
        mock_split,
    ):
        """测试 detect_scenes 使用正确参数创建 AdaptiveDetector"""
        from src.core.scene_detector import SceneDetector

        mock_video = MagicMock()
        mock_video.frame_rate = 30.0
        mock_open_video.return_value = mock_video

        mock_manager = MagicMock()
        mock_scene_manager_cls.return_value = mock_manager
        mock_manager.get_scene_list.return_value = self._make_scene_list([(0.0, 5.0), (5.0, 10.0)])

        detector = SceneDetector(threshold=27.0, adaptive_threshold=3.0, min_scene_length=0.5)
        scenes_info, scene_list = detector.detect_scenes("/fake/video.mp4")

        mock_adaptive_detector_cls.assert_called_once_with(
            adaptive_threshold=3.0,
            min_content_val=27.0,
            min_scene_len=15,
        )
        self.assertEqual(len(scenes_info), 2)
        self.assertEqual(scenes_info[0]["scene_number"], 1)
        self.assertAlmostEqual(scenes_info[0]["duration"], 5.0)
        self.assertAlmostEqual(scenes_info[1]["duration"], 5.0)

    @patch("src.core.scene_detector.split_video_ffmpeg")
    @patch("src.core.scene_detector.AdaptiveDetector")
    @patch("src.core.scene_detector.SceneManager")
    @patch("src.core.scene_detector.open_video")
    def test_detect_scenes_returns_full_video_as_single_scene_when_no_cuts(
        self,
        mock_open_video,
        mock_scene_manager_cls,
        mock_adaptive_detector_cls,
        mock_split,
    ):
        """测试无切点时整段视频作为一个场景返回"""
        from src.core.scene_detector import SceneDetector

        mock_video = MagicMock()
        mock_video.frame_rate = 30.0
        mock_video.duration.get_seconds.return_value = 60.0
        mock_open_video.return_value = mock_video

        mock_manager = MagicMock()
        mock_scene_manager_cls.return_value = mock_manager
        mock_manager.get_scene_list.return_value = []

        mock_base_timecode = MagicMock()
        mock_base_timecode.get_seconds.return_value = 0.0
        mock_base_timecode.get_timecode.return_value = "00:00:00.000"
        mock_end_timecode = MagicMock()
        mock_end_timecode.get_seconds.return_value = 60.0
        mock_end_timecode.get_timecode.return_value = "00:01:00.000"
        type(mock_video).base_timecode = PropertyMock(return_value=mock_base_timecode)

        with patch("src.core.scene_detector.FrameTimecode", return_value=mock_end_timecode):
            detector = SceneDetector()
            scenes_info, scene_list = detector.detect_scenes("/fake/long_video.mp4")

        self.assertEqual(len(scenes_info), 1)
        self.assertEqual(scenes_info[0]["scene_number"], 1)
        self.assertAlmostEqual(scenes_info[0]["duration"], 60.0)

    @patch("src.core.scene_detector.split_video_ffmpeg")
    def test_split_video_creates_output_dir_and_calls_ffmpeg(
        self,
        mock_split,
    ):
        """测试 split_video 创建目录并调用 ffmpeg"""
        from src.core.scene_detector import SceneDetector
        import tempfile
        import os

        detector = SceneDetector()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "scenes")
            scene_list = self._make_scene_list([(0.0, 5.0)])
            detector.split_video("/fake/video.mp4", scene_list, output_dir)

            self.assertTrue(os.path.isdir(output_dir))
            mock_split.assert_called_once()
            call_kwargs = mock_split.call_args[1]
            self.assertIn("Scene-$SCENE_NUMBER.mp4", call_kwargs["output_file_template"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_scene_detector.py -v 2>&1 || python3 -m unittest tests.test_scene_detector -v`
Expected: FAIL because `detect_scenes` still uses ContentDetector and doesn't handle empty scene list.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_scene_detector.py
git commit -m "test(scene): add detect_scenes behavior tests"
```

---

### Task 5: Implement detect_scenes with AdaptiveDetector

**Files:**
- Modify: [src/core/scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/src/core/scene_detector.py)
- Test: [tests/test_scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_scene_detector.py)

- [ ] **Step 1: Update detect_scenes method**

Replace the `detect_scenes` method (lines 22-58 in the original file, now approximately lines 60-100) with:

```python
    def detect_scenes(self, video_path):
        """
        检测视频中的真实画面切换点

        Args:
            video_path: 视频文件路径

        Returns:
            tuple: (scenes_info, scene_list) 场景信息列表和 PySceneDetect 场景列表
        """
        video = open_video(str(video_path))
        scene_manager = SceneManager()

        fps = video.frame_rate or 30.0
        min_scene_len_frames = max(1, int(round(self.min_scene_length * fps)))

        scene_manager.add_detector(
            AdaptiveDetector(
                adaptive_threshold=self.adaptive_threshold,
                min_content_val=self.content_threshold,
                min_scene_len=min_scene_len_frames,
            )
        )

        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            end_timecode = FrameTimecode(
                timecode=video.duration.get_seconds(),
                fps=video.frame_rate,
            )
            scene_list = [(video.base_timecode, end_timecode)]

        scenes_info = []
        for i, scene in enumerate(scene_list, start=1):
            start_time = scene[0].get_seconds()
            end_time = scene[1].get_seconds()
            duration = end_time - start_time

            scene_data = {
                "scene_number": i,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "start_timecode": scene[0].get_timecode(),
                "end_timecode": scene[1].get_timecode(),
            }
            scenes_info.append(scene_data)

        return scenes_info, scene_list
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_scene_detector.py -v 2>&1 || python3 -m unittest tests.test_scene_detector -v`
Expected: All tests PASS. Note: tests that patch `open_video`/`SceneManager`/`AdaptiveDetector` will pass with mocks even if scenedetect is not installed.

- [ ] **Step 3: Run all existing non-scene-dependent tests to verify no breakage**

Run: `python3 -m pytest tests/ -v --ignore=tests/test_scene_detector.py --ignore=tests/test_subtitle_remover.py -k "not scene_detector and not subtitle_remover" 2>&1 || python3 -m unittest tests.test_feature_flags tests.test_text_normalizer tests.test_subtitle_segmentation tests.test_audio_aligned_segmentation tests.test_shot_pool_selection tests.test_head_tail_composer tests.test_path_arg_normalization tests.test_analysis_artifacts tests.test_lazy_package_imports tests.test_transcriber_normalization tests.test_root_meta_update -v`
Expected: All previously passing tests still PASS.

- [ ] **Step 4: Commit**

```bash
git add src/core/scene_detector.py tests/test_scene_detector.py
git commit -m "feat(scene): implement adaptive detector with min scene length filtering"
```

---

### Task 6: Write Failing Tests for VideoAnalyzer Report Metadata

**Files:**
- Modify: [tests/test_scene_detector.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_scene_detector.py) (no new file needed; we'll test VideoAnalyzer separately if existing tests cover it, but we need a new test file)
- Create: [tests/test_video_analyzer_report.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_video_analyzer_report.py)

- [ ] **Step 1: Create test file for VideoAnalyzer scene detection metadata**

Create `tests/test_video_analyzer_report.py`:

```python
"""
VideoAnalyzer 场景检测元数据报告测试
"""
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_video_analyzer_report.py -v 2>&1 || python3 -m unittest tests.test_video_analyzer_report -v`
Expected: FAIL because `VideoAnalyzer` does not have `scene_detection_config` attribute and does not pass it to report.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_video_analyzer_report.py
git commit -m "test(scene): add video analyzer report metadata tests"
```

---

### Task 7: Implement VideoAnalyzer Metadata Wiring

**Files:**
- Modify: [src/core/video_analyzer.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/src/core/video_analyzer.py)
- Test: [tests/test_video_analyzer_report.py](file:///Users/bytedance/Desktop/tools/qing_xu_auto_2chuang/tests/test_video_analyzer_report.py)

- [ ] **Step 1: Initialize scene_detection_config in __init__**

In `VideoAnalyzer.__init__`, after `self.output_dir` creation (around line 35), add:

```python
        self.scene_detection_config = None
```

- [ ] **Step 2: Capture config after detect_scenes in analyze_scenes**

In `analyze_scenes`, after `detector = SceneDetector(threshold=threshold)` and before calling `detect_scenes`, or after detection completes, add config capture. Update the analyze_scenes method body (lines 84-101) to:

```python
        print("\n=== 步骤 1: 分析视频场景 ===")

        detector = SceneDetector(threshold=threshold)
        scenes_info, scene_list = detector.detect_scenes(self.video_path)
        self.scene_detection_config = dict(detector.detection_config)

        print(f"✓ 检测到 {len(scenes_info)} 个场景")

        for scene in scenes_info:
            print(f"  场景 {scene['scene_number']}: {scene['start_timecode']} -> "
                  f"{scene['end_timecode']} (时长: {scene['duration']:.2f}秒)")

        if scene_list:
            scenes_dir = os.path.join(self.output_dir, OUTPUT["scenes_folder"])
            detector.split_video(self.video_path, scene_list, scenes_dir)
            print(f"✓ 场景视频已保存到: {scenes_dir}")

        return scenes_info
```

- [ ] **Step 3: Include scene_detection in generate_report**

In `generate_report`, add `"scene_detection"` key to the report dict (around line 183):

```python
        report = {
            "video_name": self.video_name,
            "original_video_path": self.original_video_path,
            "processed_video_path": self.video_path,
            "subtitle_removed": self.original_video_path != self.video_path,
            "output_directory": self.output_dir,
            "total_scenes": len(scenes_info) if scenes_info else 0,
            "scene_detection": self.scene_detection_config,
            "scenes": scenes_info or [],
            "transcript": transcript_result["text"] if transcript_result else None,
            "transcript_segments": transcript_result["segments"] if transcript_result else []
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_video_analyzer_report.py -v 2>&1 || python3 -m unittest tests.test_video_analyzer_report -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Run all existing tests to verify no breakage**

Run: `python3 -m pytest tests/ -v --ignore=tests/test_subtitle_remover.py 2>&1 || python3 -m unittest discover tests -v 2>&1 | head -100`
Expected: All tests PASS (except test_subtitle_remover which requires cv2 not installed locally).

- [ ] **Step 6: Commit**

```bash
git add src/core/video_analyzer.py tests/test_video_analyzer_report.py
git commit -m "feat(scene): wire detection metadata through analyzer into report"
```

---

### Task 8: Verify End-to-End Compatibility and Run Full Test Suite

**Files:**
- Modify: None (verification only)
- Verify: All files

- [ ] **Step 1: Run all unit tests (excluding cv2-dependent test)**

Run: `python3 -m unittest discover tests -v 2>&1`
Expected: All tests pass except `test_subtitle_remover` which requires `cv2` (pre-existing environment issue, not related to this change). Count: at least 31 tests.

- [ ] **Step 2: Verify no fixed-interval or max-duration logic was added**

Run: `grep -n "max_scene_length\|interval\|every.*second\|max_duration\|time_step\|chunk.*duration" src/core/scene_detector.py src/core/video_analyzer.py`
Expected: No matches that indicate time-based splitting logic.

- [ ] **Step 3: Verify backward compatibility of SceneDetector(threshold=...) API**

Run: `python3 -c "
from src.core.scene_detector import SceneDetector
d = SceneDetector(threshold=15.0)
assert d.threshold == 15.0
assert d.content_threshold == 15.0
print('Backward compatibility: OK')
print('Config:', dict(d.detection_config))
"`
Expected: Prints `Backward compatibility: OK` and shows config dict.

- [ ] **Step 4: Final commit (if any fixes were needed)**

```bash
git add -A
git status
# If there are changes:
# git commit -m "fix(scene): address review findings from verification"
```

---

## Verification Checklist (Pre-Completion)

- [ ] All new unit tests pass
- [ ] `AdaptiveDetector` is used instead of `ContentDetector`
- [ ] `min_scene_length` is converted from seconds to frames (min 1 frame)
- [ ] No `max_scene_length` exists; long shots are preserved
- [ ] Empty scene list (no cuts) returns full video as single scene
- [ ] `SceneDetector(threshold=N)` backward compatibility maintained
- [ ] `detection_config` returns read-only snapshot
- [ ] `report.json` includes `scene_detection` metadata
- [ ] CLI `-t/--threshold` continues to work through existing wiring
- [ ] Existing tests for composition/head-tail/shot-pool/artifacts still pass
