"""
Emotion style Jianying exports should merge bilingual subtitles onto one text track.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.exporters.jianying import DEFAULT_TEMPLATE_DIR, export_to_jianying_draft
from src.models import AnalysisArtifacts, MediaMetadata, TimelineClip, TranscriptSegment


class TestJianyingEmotionTemplate(unittest.TestCase):
    def test_emotion_template_exports_bilingual_text_on_single_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            draft_root = tmp_path / "drafts"
            draft_root.mkdir()

            video_path = tmp_path / "scene.mp4"
            audio_path = tmp_path / "audio.mp3"
            video_path.write_bytes(b"video")
            audio_path.write_bytes(b"audio")

            artifacts = AnalysisArtifacts(
                output_dir=tmp_path,
                video_name="emotion_demo",
                original_video_path=None,
                processed_video_path=video_path,
                report_path=None,
                audio_path=audio_path,
                audio_metadata=MediaMetadata(
                    path=audio_path,
                    duration_us=5_000_000,
                    width=0,
                    height=0,
                    has_audio=True,
                ),
                scenes=(),
                transcript_segments=(
                    TranscriptSegment(0, 2_000_000, "我们都没有上帝视角"),
                    TranscriptSegment(2_000_000, 5_000_000, "但你可以继续往前走"),
                ),
                english_transcript_segments=(
                    TranscriptSegment(0, 800_000, "We do not"),
                    TranscriptSegment(800_000, 2_000_000, "have God's perspective."),
                    TranscriptSegment(2_000_000, 3_500_000, "But you can"),
                    TranscriptSegment(3_500_000, 5_000_000, "keep moving forward."),
                ),
            )
            timeline = [
                TimelineClip(
                    source_path=video_path,
                    timeline_start_us=0,
                    timeline_duration_us=5_000_000,
                    source_duration_us=5_000_000,
                )
            ]

            with patch("src.exporters.jianying.probe_media") as mock_probe, patch(
                "src.exporters.jianying._try_generate_cover"
            ):
                mock_probe.return_value = MediaMetadata(
                    path=video_path,
                    duration_us=5_000_000,
                    width=1080,
                    height=1920,
                    has_audio=False,
                )
                draft_dir = export_to_jianying_draft(
                    artifacts,
                    timeline_clips=timeline,
                    draft_root=draft_root,
                    template_dir=DEFAULT_TEMPLATE_DIR,
                    draft_name="emotion_demo",
                    style_template="emotion",
                )

            draft_info = json.loads((draft_dir / "draft_info.json").read_text(encoding="utf-8"))
            track_types = [track["type"] for track in draft_info["tracks"]]
            self.assertEqual(track_types, ["video", "audio", "text"])

            subtitle_materials = draft_info["materials"]["texts"]
            self.assertEqual(len(subtitle_materials), 2)
            self.assertTrue(all(item["type"] == "text" for item in subtitle_materials))
            self.assertEqual(draft_info["materials"]["material_animations"], [])

            video_segment = draft_info["tracks"][0]["segments"][0]
            audio_segment = draft_info["tracks"][1]["segments"][0]
            subtitle_segment = draft_info["tracks"][2]["segments"][0]

            self.assertEqual(len(video_segment["extra_material_refs"]), 1)
            self.assertEqual(len(audio_segment["extra_material_refs"]), 1)
            self.assertAlmostEqual(subtitle_segment["clip"]["transform"]["y"], -0.79)

            first_content = json.loads(subtitle_materials[0]["content"])
            second_content = json.loads(subtitle_materials[1]["content"])
            self.assertEqual(
                first_content["text"],
                "我们都没有上帝视角\nWe do not have God's perspective.",
            )
            self.assertEqual(
                second_content["text"],
                "但你可以继续往前走\nBut you can keep moving forward.",
            )
            self.assertEqual(len(first_content["styles"]), 2)
            self.assertGreater(first_content["styles"][0]["size"], first_content["styles"][1]["size"])
            self.assertEqual(subtitle_materials[0]["font_name"], "PingFang SC")
            self.assertEqual(subtitle_materials[0]["text_color"], "#FFFFFF")


if __name__ == "__main__":
    unittest.main()
