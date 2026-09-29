from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.cli import create_parser, main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestCliExitCodes(unittest.TestCase):
    def _call_main(self, args):
        with patch.object(sys, "argv", ["main.py", *args]):
            return main()

    def test_main_returns_usage_error_without_inputs(self):
        self.assertEqual(self._call_main([]), 2)

    def test_default_semantic_config_is_independent_of_working_directory(self):
        config_path = Path(create_parser().parse_args([]).semantic_scenes_config)

        self.assertTrue(config_path.is_absolute())
        self.assertTrue(config_path.is_file())

    def test_download_only_implies_download(self):
        url = "https://example.com/video"
        with (
            patch("src.cli.VideoDownloader") as downloader_class,
            patch("src.cli.BatchProcessor") as processor_class,
        ):
            downloader_class.return_value.download_batch.return_value = [
                "/tmp/downloaded.mp4"
            ]

            return_code = self._call_main([url, "--download-only"])

        self.assertEqual(return_code, 0)
        downloader_class.return_value.download_batch.assert_called_once_with([url])
        processor_class.assert_not_called()

    def test_download_only_returns_failure_when_download_fails(self):
        url = "https://example.com/video"
        with patch("src.cli.VideoDownloader") as downloader_class:
            downloader_class.return_value.download_batch.return_value = []

            return_code = self._call_main([url, "--download-only"])

        self.assertEqual(return_code, 1)

    def test_main_returns_failure_when_batch_contains_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"video")
            with patch("src.cli.BatchProcessor") as processor_class:
                processor_class.return_value.process_batch.return_value = {
                    "total": 1,
                    "success": 0,
                    "failed": 1,
                    "failed_videos": [str(video)],
                    "elapsed_time": 0,
                }

                return_code = self._call_main([str(video)])

        self.assertEqual(return_code, 1)

    def test_main_entrypoint_returns_failure_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.mp4"
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "main.py"), str(missing)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=15,
            )

        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
