"""
Emotion style Jianying exports should merge bilingual subtitles onto one text track.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.feature_flags import feature_flags
from src.exporters.jianying import (
    DEFAULT_TEMPLATE_DIR,
    _load_or_generate_english_segments,
    export_to_jianying_draft,
)
from src.exporters.jianying_styles import resolve_style_template
from src.models import AnalysisArtifacts, MediaMetadata, TimelineClip, TranscriptSegment


class TestJianyingEmotionTemplate(unittest.TestCase):
    def _build_artifacts(self, tmp_path: Path, *, include_english: bool = True) -> tuple[AnalysisArtifacts, list[TimelineClip]]:
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
                (
                    TranscriptSegment(0, 800_000, "We do not"),
                    TranscriptSegment(800_000, 2_000_000, "have God's perspective."),
                    TranscriptSegment(2_000_000, 3_500_000, "But you can"),
                    TranscriptSegment(3_500_000, 5_000_000, "keep moving forward."),
                )
                if include_english
                else ()
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
        return artifacts, timeline

    def _export_emotion_draft(self, tmp_path: Path, artifacts: AnalysisArtifacts, timeline: list[TimelineClip]):
        draft_root = tmp_path / "drafts"
        draft_root.mkdir()
        with patch("src.exporters.jianying.probe_media") as mock_probe, patch(
            "src.exporters.jianying._try_generate_cover"
        ):
            mock_probe.return_value = MediaMetadata(
                path=artifacts.processed_video_path,
                duration_us=5_000_000,
                width=1080,
                height=1920,
                has_audio=False,
            )
            return export_to_jianying_draft(
                artifacts,
                timeline_clips=timeline,
                draft_root=draft_root,
                template_dir=DEFAULT_TEMPLATE_DIR,
                draft_name="emotion_demo",
                style_template="emotion",
            )

    def test_emotion_template_exports_bilingual_text_on_single_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts, timeline = self._build_artifacts(tmp_path)

            draft_dir = self._export_emotion_draft(tmp_path, artifacts, timeline)

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

    def test_emotion_template_can_export_separate_bilingual_tracks_when_flag_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts, timeline = self._build_artifacts(tmp_path)

            with feature_flags.override(single_track_bilingual_subtitles=False):
                draft_dir = self._export_emotion_draft(tmp_path, artifacts, timeline)

            draft_info = json.loads((draft_dir / "draft_info.json").read_text(encoding="utf-8"))
            track_types = [track["type"] for track in draft_info["tracks"]]

            self.assertEqual(track_types, ["video", "audio", "text", "text"])
            self.assertEqual(draft_info["tracks"][2]["name"], "双语字幕")
            self.assertEqual(draft_info["tracks"][3]["name"], "双语字幕")
            self.assertEqual(len(draft_info["materials"]["texts"]), 6)

    def test_segment_aligned_bilingual_translation_uses_source_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts, _ = self._build_artifacts(tmp_path, include_english=False)

            with patch("src.exporters.jianying._make_transcriber") as mock_make_transcriber:
                translator = mock_make_transcriber.return_value
                translator.translate_segments_to_english.return_value = {
                    "text": "We do not have God's perspective. But you can keep moving forward.",
                    "segments": [
                        {"start": 0.0, "end": 2.0, "text": "We do not have God's perspective."},
                        {"start": 2.0, "end": 5.0, "text": "But you can keep moving forward."},
                    ],
                }

                segments = _load_or_generate_english_segments(
                    artifacts,
                    style_template=resolve_style_template("emotion"),
                )

            self.assertEqual(len(segments), 2)
            translator.translate_segments_to_english.assert_called_once()
            translator.translate_to_english.assert_not_called()

    def test_segment_aligned_bilingual_translation_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts, _ = self._build_artifacts(tmp_path, include_english=False)

            with feature_flags.override(segment_aligned_bilingual_translation=False), patch(
                "src.exporters.jianying._make_transcriber"
            ) as mock_make_transcriber:
                translator = mock_make_transcriber.return_value
                translator.translate_to_english.return_value = {
                    "text": "We do not have God's perspective.",
                    "segments": [
                        {"start": 0.0, "end": 5.0, "text": "We do not have God's perspective."},
                    ],
                }

                segments = _load_or_generate_english_segments(
                    artifacts,
                    style_template=resolve_style_template("emotion"),
                )

            self.assertEqual(len(segments), 1)
            translator.translate_to_english.assert_called_once()
            translator.translate_segments_to_english.assert_not_called()


if __name__ == "__main__":
    unittest.main()
