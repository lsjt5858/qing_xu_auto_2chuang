import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

_video_analyzer_module = ModuleType("src.core.video_analyzer")
_video_analyzer_module.VideoAnalyzer = MagicMock()
with patch.dict(
    sys.modules,
    {"src.core.video_analyzer": _video_analyzer_module},
):
    batch_processor_module = importlib.import_module(
        "src.utils.batch_processor"
    )
    BatchProcessor = batch_processor_module.BatchProcessor

_core_package = sys.modules.get("src.core")
if (
    _core_package is not None
    and _core_package.__dict__.get("video_analyzer") is _video_analyzer_module
):
    delattr(_core_package, "video_analyzer")


class TestBatchProcessorExistingOutput(unittest.TestCase):
    def test_finds_target_in_exact_timestamped_video_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            target = (
                output_root
                / "example_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"video")

            processor = BatchProcessor(output_dir=str(output_root))

            self.assertEqual(
                processor._find_existing_target_video("/videos/example.mp4"),
                target,
            )

    def test_ignores_other_video_with_matching_name_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            target = (
                output_root
                / "example_extra_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"video")

            processor = BatchProcessor(output_dir=str(output_root))

            self.assertIsNone(
                processor._find_existing_target_video("/videos/example.mp4")
            )

    def test_returns_none_when_output_root_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            processor = BatchProcessor(output_dir=str(Path(tmp) / "missing"))

            self.assertIsNone(
                processor._find_existing_target_video("/videos/example.mp4")
            )

    def test_existing_target_skips_analyzer_initialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_video = Path(tmp) / "example.mp4"
            input_video.write_bytes(b"source")
            output_root = Path(tmp) / "output"
            target = (
                output_root
                / "example_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"video")
            args = SimpleNamespace(
                remove_subtitles=False,
                audio_only=True,
                scenes_only=True,
            )
            processor = BatchProcessor(output_dir=str(output_root))

            with patch.object(
                batch_processor_module,
                "VideoAnalyzer",
            ) as analyzer_class:
                result = processor.process_video(str(input_video), args)

            self.assertTrue(result)
            analyzer_class.assert_not_called()

    def test_missing_target_continues_normal_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_video = Path(tmp) / "example.mp4"
            input_video.write_bytes(b"source")
            output_root = Path(tmp) / "output"
            (output_root / "example_20260916_134659").mkdir(parents=True)
            args = SimpleNamespace(
                remove_subtitles=False,
                audio_only=True,
                scenes_only=True,
            )
            processor = BatchProcessor(output_dir=str(output_root))

            with patch.object(
                batch_processor_module,
                "VideoAnalyzer",
            ) as analyzer_class:
                result = processor.process_video(str(input_video), args)

            self.assertTrue(result)
            analyzer_class.assert_called_once_with(
                str(input_video),
                str(output_root),
            )

    def test_missing_source_fails_even_when_target_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_video = Path(tmp) / "example.mp4"
            output_root = Path(tmp) / "output"
            target = (
                output_root
                / "example_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"video")
            processor = BatchProcessor(output_dir=str(output_root))

            with patch.object(
                batch_processor_module,
                "VideoAnalyzer",
            ) as analyzer_class:
                result = processor.process_video(
                    str(input_video),
                    SimpleNamespace(),
                )

            self.assertFalse(result)
            analyzer_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
