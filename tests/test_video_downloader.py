from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.video_downloader import VideoDownloader


class TestVideoDownloader(unittest.TestCase):
    def test_check_yt_dlp_uses_current_python_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = VideoDownloader(tmp)
            completed = MagicMock(returncode=0)

            with patch(
                "src.core.video_downloader.subprocess.run",
                return_value=completed,
            ) as run:
                available = downloader.check_yt_dlp()

        self.assertTrue(available)
        self.assertEqual(
            run.call_args.args[0],
            [sys.executable, "-m", "yt_dlp", "--version"],
        )

    def test_missing_yt_dlp_does_not_install_at_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = VideoDownloader(tmp)

            with (
                patch.object(downloader, "check_yt_dlp", return_value=False),
                patch("src.core.video_downloader.subprocess.run") as run,
            ):
                result = downloader.download("https://example.com/video")

        self.assertIsNone(result)
        run.assert_not_called()

    def test_download_returns_path_reported_by_yt_dlp(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            expected = output_dir / "expected.mp4"
            expected.write_bytes(b"downloaded")
            unrelated = output_dir / "newer-but-unrelated.mp4"
            unrelated.write_bytes(b"old")

            downloader = VideoDownloader(output_dir)
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"{expected}\n",
                stderr="",
            )

            with (
                patch.object(downloader, "check_yt_dlp", return_value=True),
                patch(
                    "src.core.video_downloader.subprocess.run",
                    return_value=completed,
                ) as run,
            ):
                result = downloader.download("https://example.com/video")

        self.assertEqual(result, str(expected.resolve()))
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, "-m", "yt_dlp"])
        self.assertIn("--no-simulate", command)
        self.assertIn("--print", command)
        self.assertIn("after_move:filepath", command)

    def test_download_fails_when_reported_path_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "unrelated.mp4").write_bytes(b"old")
            downloader = VideoDownloader(output_dir)
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"{output_dir / 'missing.mp4'}\n",
                stderr="",
            )

            with (
                patch.object(downloader, "check_yt_dlp", return_value=True),
                patch(
                    "src.core.video_downloader.subprocess.run",
                    return_value=completed,
                ),
            ):
                result = downloader.download("https://example.com/video")

        self.assertIsNone(result)

    def test_custom_filename_preserves_douyin_cookie_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            expected = output_dir / "custom.mp4"
            expected.write_bytes(b"downloaded")
            downloader = VideoDownloader(output_dir)
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"{expected}\n",
                stderr="",
            )

            with (
                patch.object(downloader, "check_yt_dlp", return_value=True),
                patch(
                    "src.core.video_downloader.subprocess.run",
                    return_value=completed,
                ) as run,
            ):
                downloader.download(
                    "https://www.douyin.com/video/123",
                    filename="custom.mp4",
                )

        command = run.call_args.args[0]
        cookie_index = command.index("--cookies-from-browser")
        output_index = command.index("-o")
        self.assertEqual(command[cookie_index + 1], "chrome")
        self.assertEqual(command[output_index + 1], str(expected.resolve()))

    def test_douyin_text_in_query_does_not_enable_browser_cookies(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            expected = output_dir / "expected.mp4"
            expected.write_bytes(b"downloaded")
            downloader = VideoDownloader(output_dir)
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"{expected}\n",
                stderr="",
            )

            with (
                patch.object(downloader, "check_yt_dlp", return_value=True),
                patch(
                    "src.core.video_downloader.subprocess.run",
                    return_value=completed,
                ) as run,
            ):
                downloader.download(
                    "https://example.com/watch?next=douyin.com",
                )

        self.assertNotIn("--cookies-from-browser", run.call_args.args[0])

    def test_www_douyin_url_enables_browser_cookies(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            expected = output_dir / "expected.mp4"
            expected.write_bytes(b"downloaded")
            downloader = VideoDownloader(output_dir)
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"{expected}\n",
                stderr="",
            )

            with (
                patch.object(downloader, "check_yt_dlp", return_value=True),
                patch(
                    "src.core.video_downloader.subprocess.run",
                    return_value=completed,
                ) as run,
            ):
                downloader.download("www.douyin.com/video/123")

        self.assertIn("--cookies-from-browser", run.call_args.args[0])

    def test_douyin_search_url_is_rejected_with_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = VideoDownloader(tmp)
            output = StringIO()

            with (
                patch.object(downloader, "check_yt_dlp") as check_yt_dlp,
                patch("src.core.video_downloader.subprocess.run") as run,
                redirect_stdout(output),
            ):
                result = downloader.download(
                    r"https://www.douyin.com/search/demo\?type\=general"
                )

        self.assertIsNone(result)
        self.assertIn("抖音搜索页", output.getvalue())
        self.assertIn("单个视频链接", output.getvalue())
        check_yt_dlp.assert_not_called()
        run.assert_not_called()

    def test_download_batch_reports_failure_when_nothing_downloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = VideoDownloader(tmp)
            output = StringIO()

            with (
                patch.object(downloader, "download", return_value=None),
                redirect_stdout(output),
            ):
                result = downloader.download_batch(["https://example.com/video"])

        self.assertEqual(result, [])
        self.assertIn("下载失败！", output.getvalue())
        self.assertNotIn("下载完成！", output.getvalue())

    def test_douyin_fresh_cookie_error_reports_http_403(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = VideoDownloader(tmp)
            output = StringIO()
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr=(
                    "Extracted 966 cookies from chrome\n"
                    "WARNING: Failed to download web detail JSON: HTTP Error 403: Forbidden\n"
                    "ERROR: Fresh cookies (not necessarily logged in) are needed"
                ),
            )

            with (
                patch.object(downloader, "check_yt_dlp", return_value=True),
                patch(
                    "src.core.video_downloader.subprocess.run",
                    return_value=completed,
                ),
                redirect_stdout(output),
            ):
                result = downloader.download("https://v.douyin.com/example/")

        self.assertIsNone(result)
        self.assertIn("HTTP 403", output.getvalue())
        self.assertIn("Chrome Cookie 已读取", output.getvalue())
        self.assertIn("风控或签名校验", output.getvalue())
        self.assertNotIn("Cookie 已读取但已失效", output.getvalue())


if __name__ == "__main__":
    unittest.main()
