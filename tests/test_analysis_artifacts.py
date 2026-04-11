"""
Analysis artifact loading tests.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.models import load_analysis_artifacts


class TestAnalysisArtifacts(unittest.TestCase):
    def test_load_artifacts_from_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            scenes_dir = output_dir / "scenes"
            scenes_dir.mkdir()

            processed_video = output_dir / "video_no_subtitles.mp4"
            processed_video.write_bytes(b"")
            (scenes_dir / "Scene-001.mp4").write_bytes(b"")
            (scenes_dir / "Scene-002.mp4").write_bytes(b"")

            report = {
                "video_name": "demo",
                "processed_video_path": str(processed_video),
                "scenes": [
                    {"start_time": 0.0, "end_time": 1.5},
                    {"start_time": 1.5, "end_time": 4.0},
                ],
                "transcript_segments": [
                    {"start": 0.0, "end": 1.0, "text": "hello"},
                    {"start": 1.2, "end": 3.5, "text": "world"},
                ],
            }
            (output_dir / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            artifacts = load_analysis_artifacts(output_dir)

            self.assertEqual(artifacts.video_name, "demo")
            self.assertEqual(len(artifacts.scenes), 2)
            self.assertEqual(artifacts.scenes[0].duration_us, 1_500_000)
            self.assertEqual(artifacts.scenes[1].duration_us, 2_500_000)
            self.assertEqual(len(artifacts.transcript_segments), 2)
            self.assertEqual(artifacts.total_duration_us, 4_000_000)

    def test_loads_optional_english_transcript_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "report.json").write_text(
                json.dumps(
                    {
                        "video_name": "demo",
                        "transcript_segments": [
                            {"start": 0.0, "end": 1.0, "text": "我们都没有上帝视角"},
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (output_dir / "transcript_english_detailed.json").write_text(
                json.dumps(
                    [
                        {"start": 0.0, "end": 1.0, "text": "We do not have God's perspective."},
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            artifacts = load_analysis_artifacts(output_dir)

            self.assertEqual(len(artifacts.english_transcript_segments), 1)
            self.assertEqual(
                artifacts.english_transcript_segments[0].text,
                "We do not have God's perspective.",
            )


if __name__ == "__main__":
    unittest.main()
