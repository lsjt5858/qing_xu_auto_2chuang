from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestDependencyContract(unittest.TestCase):
    def test_moviepy_version_matches_import_api(self):
        requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("moviepy>=2.0,<3", requirements.splitlines())

    def test_yt_dlp_is_declared(self):
        requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertTrue(
            any(line.startswith("yt-dlp>=") for line in requirements.splitlines())
        )


if __name__ == "__main__":
    unittest.main()
