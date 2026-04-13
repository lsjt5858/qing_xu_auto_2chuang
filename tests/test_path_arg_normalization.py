"""
Path-like CLI inputs should tolerate accidental surrounding whitespace.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.composition.shot_pool import ShotPoolIndex
from src.models import load_analysis_artifacts


class TestPathArgNormalization(unittest.TestCase):
    def test_load_analysis_artifacts_strips_surrounding_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "report.json").write_text(
                json.dumps({"video_name": "demo"}, ensure_ascii=False),
                encoding="utf-8",
            )

            artifacts = load_analysis_artifacts(f"  {output_dir}  ")
            self.assertEqual(artifacts.output_dir, output_dir.resolve())

    def test_shot_pool_index_strips_surrounding_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool_dir = Path(tmp)
            with self.assertRaisesRegex(ValueError, "No usable video shots found"):
                ShotPoolIndex.from_directory(f"  {pool_dir}  ")


if __name__ == "__main__":
    unittest.main()
