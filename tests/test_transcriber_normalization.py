"""
Transcriber should normalize Chinese output to simplified Chinese.
"""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from src.core.transcriber import SIMPLIFIED_CHINESE_PROMPT, Transcriber


class TestTranscriberNormalization(unittest.TestCase):
    @patch("src.core.transcriber.importlib.import_module")
    def test_transcribe_normalizes_result_and_segments(self, mock_import_module):
        fake_model = Mock()
        fake_model.transcribe.return_value = {
            "text": "我們都沒有上帝視角",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "愛和委屈都要大聲說出來"},
            ],
        }
        fake_whisper = Mock()
        fake_whisper.load_model.return_value = fake_model
        mock_import_module.return_value = fake_whisper

        transcriber = Transcriber(model_size="base")
        result = transcriber.transcribe("/tmp/fake.mp3", language="zh")

        self.assertEqual(result["text"], "我们都没有上帝视角")
        self.assertEqual(result["segments"][0]["text"], "爱和委屈都要大声说出来")
        _, kwargs = fake_model.transcribe.call_args
        self.assertEqual(kwargs["language"], "zh")
        self.assertEqual(kwargs["initial_prompt"], SIMPLIFIED_CHINESE_PROMPT)
        self.assertEqual(kwargs["task"], "transcribe")
        self.assertEqual(kwargs["temperature"], 0)

    @patch("src.core.transcriber.importlib.import_module")
    def test_translate_to_english_uses_translate_task(self, mock_import_module):
        fake_model = Mock()
        fake_model.transcribe.return_value = {
            "text": "Stay in the water and you will drown.",
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "text": "Stay in the water and you will drown.",
                },
            ],
        }
        fake_whisper = Mock()
        fake_whisper.load_model.return_value = fake_model
        mock_import_module.return_value = fake_whisper

        transcriber = Transcriber(model_size="base")
        result = transcriber.translate_to_english("/tmp/fake.mp3")

        self.assertEqual(result["text"], "Stay in the water and you will drown.")
        _, kwargs = fake_model.transcribe.call_args
        self.assertEqual(kwargs["language"], "zh")
        self.assertEqual(kwargs["task"], "translate")
        self.assertEqual(kwargs["temperature"], 0)
        self.assertNotIn("initial_prompt", kwargs)

    @patch("src.core.transcriber.importlib.import_module")
    def test_translate_to_english_retries_when_first_result_is_empty(self, mock_import_module):
        fake_model = Mock()
        fake_model.transcribe.side_effect = [
            {"text": "", "segments": []},
            {
                "text": "Fear of failure is what is truly frightening.",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 1.0,
                        "text": "Fear of failure is what is truly frightening.",
                    },
                ],
            },
        ]
        fake_whisper = Mock()
        fake_whisper.load_model.return_value = fake_model
        mock_import_module.return_value = fake_whisper

        transcriber = Transcriber(model_size="base")
        result = transcriber.translate_to_english("/tmp/fake.mp3")

        self.assertEqual(
            result["text"],
            "Fear of failure is what is truly frightening.",
        )
        self.assertEqual(fake_model.transcribe.call_count, 2)
        _, retry_kwargs = fake_model.transcribe.call_args
        self.assertEqual(retry_kwargs["task"], "translate")
        self.assertEqual(retry_kwargs["temperature"], 0)
        self.assertNotIn("language", retry_kwargs)


if __name__ == "__main__":
    unittest.main()
