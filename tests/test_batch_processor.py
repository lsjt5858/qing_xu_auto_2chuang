import importlib
import json
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

    def test_existing_target_skips_semantic_grouping(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_video = Path(tmp) / "example.mp4"
            input_video.write_bytes(b"source")
            output_root = Path(tmp) / "output"
            output_dir = output_root / "example_20260916_134659"
            target = output_dir / "video_no_subtitles.mp4"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"processed")
            report_path = output_dir / "report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "scenes": [
                            {
                                "scene_number": 1,
                                "start_time": 0.0,
                                "end_time": 2.0,
                            },
                            {
                                "scene_number": 2,
                                "start_time": 2.0,
                                "end_time": 4.0,
                            },
                        ],
                        "transcript_segments": [
                            {"start": 0.0, "end": 4.0, "text": "连续剧情"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                semantic_scenes=True,
                semantic_scenes_config="config/semantic_scenes.json",
            )
            processor = BatchProcessor(output_dir=str(output_root))
            grouper = MagicMock()
            semantic_module = ModuleType("src.core.semantic_scene_grouper")
            semantic_module.SemanticSceneGrouper = MagicMock()
            semantic_module.SemanticSceneGrouper.from_config.return_value = grouper

            with (
                patch.object(batch_processor_module, "VideoAnalyzer") as analyzer_class,
                patch.dict(
                    sys.modules,
                    {"src.core.semantic_scene_grouper": semantic_module},
                ),
            ):
                result = processor.process_video(str(input_video), args)

            self.assertTrue(result)
            analyzer_class.assert_not_called()
            grouper.group_and_export.assert_not_called()
            updated_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertNotIn("semantic_scene_count", updated_report)
            self.assertNotIn("semantic_scenes", updated_report)

    def test_existing_semantic_result_skips_all_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_video = Path(tmp) / "example.mp4"
            input_video.write_bytes(b"source")
            output_root = Path(tmp) / "output"
            output_dir = output_root / "example_20260916_134659"
            target = output_dir / "video_no_subtitles.mp4"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"processed")
            (output_dir / "semantic_scenes.json").write_text("[]", encoding="utf-8")
            args = SimpleNamespace(semantic_scenes=True)
            processor = BatchProcessor(output_dir=str(output_root))

            with patch.object(
                batch_processor_module,
                "VideoAnalyzer",
            ) as analyzer_class:
                result = processor.process_video(str(input_video), args)

            self.assertTrue(result)
            analyzer_class.assert_not_called()

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
