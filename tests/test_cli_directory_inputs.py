import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.cli import collect_directory_inputs, main


class TestCollectDirectoryInputs(unittest.TestCase):
    def _make_result_dir(self, root: Path, name: str) -> Path:
        result_dir = root / name
        result_dir.mkdir()
        (result_dir / "report.json").write_text("{}", encoding="utf-8")
        (result_dir / "video_no_subtitles.mp4").write_bytes(b"video")
        return result_dir

    def test_recognizes_single_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_dir = self._make_result_dir(Path(tmp), "demo_20260916_120000")

            videos, outputs = collect_directory_inputs(
                result_dir,
                include_existing_outputs=True,
            )

            self.assertEqual(videos, [])
            self.assertEqual(outputs, [str(result_dir)])

    def test_recognizes_existing_outputs_inside_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._make_result_dir(root, "a_20260916_120000")
            second = self._make_result_dir(root, "b_20260916_120000")
            (root / "unrelated").mkdir()

            videos, outputs = collect_directory_inputs(
                root,
                include_existing_outputs=True,
            )

            self.assertEqual(videos, [])
            self.assertEqual(outputs, sorted([str(first), str(second)]))

    def test_keeps_source_video_scan_and_supports_more_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.MP4"
            second = root / "b.m4v"
            third = root / "c.ts"
            for path in (first, second, third):
                path.write_bytes(b"video")

            videos, outputs = collect_directory_inputs(root)

            self.assertEqual(videos, sorted(map(str, (first, second, third))))
            self.assertEqual(outputs, [])

    def test_semantic_mode_skips_api_key_check_when_target_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "videos"
            input_dir.mkdir()
            source = input_dir / "example.mp4"
            source.write_bytes(b"source")

            output_root = root / "output"
            target = (
                output_root
                / "example_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"processed")

            argv = [
                "main.py",
                str(input_dir),
                "--semantic-scenes",
                "--output",
                str(output_root),
            ]
            with (
                patch.object(sys, "argv", argv),
                patch("src.cli.validate_semantic_scene_credentials") as validate,
            ):
                main()

            validate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
