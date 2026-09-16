import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.semantic_scene_grouper import (
    SemanticSceneConfig,
    SemanticSceneGrouper,
)


class TestSemanticSceneConfig(unittest.TestCase):
    def _write_multi_provider_config(self, root):
        config_path = root / "semantic.json"
        config_path.write_text(
            json.dumps(
                {
                    "default_provider": "zhipu",
                    "provider_env": "SEMANTIC_SCENE_PROVIDER",
                    "providers": {
                        "zhipu": {
                            "provider": "zhipu-openai-compatible",
                            "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                            "model": "glm-4.6v",
                            "api_key_env": "ZAI_API_KEY",
                        },
                        "volcengine": {
                            "provider": "volcengine-ark-openai-compatible",
                            "base_url": "https://ark.cn-beijing.volces.com/api/v3/",
                            "model_env": "ARK_MODEL",
                            "api_key_env": "ARK_API_KEY",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        return config_path

    def test_loads_config_without_api_key_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "semantic.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "test",
                        "base_url": "https://example.com/v1/",
                        "model": "vision-model",
                        "api_key_env": "TEST_VISION_API_KEY",
                    }
                ),
                encoding="utf-8",
            )

            config = SemanticSceneConfig.load(config_path)

            self.assertEqual(config.endpoint, "https://example.com/v1/chat/completions")
            self.assertEqual(config.api_key_env, "TEST_VISION_API_KEY")

    def test_multi_provider_config_uses_explicit_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_multi_provider_config(Path(tmp))

            with patch.dict(
                os.environ,
                {
                    "SEMANTIC_SCENE_PROVIDER": "volcengine",
                    "ARK_MODEL": "ep-explicit",
                },
                clear=True,
            ):
                config = SemanticSceneConfig.load(config_path)

            self.assertEqual(config.provider, "volcengine-ark-openai-compatible")
            self.assertEqual(config.api_key_env, "ARK_API_KEY")
            self.assertEqual(config.model, "ep-explicit")
            self.assertEqual(
                config.endpoint,
                "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            )

    def test_multi_provider_config_auto_selects_available_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self._write_multi_provider_config(Path(tmp))

            with patch.dict(
                os.environ,
                {
                    "ARK_API_KEY": "test-key",
                    "ARK_MODEL": "ep-auto",
                },
                clear=True,
            ):
                config = SemanticSceneConfig.load(config_path)

            self.assertEqual(config.provider, "volcengine-ark-openai-compatible")
            self.assertEqual(config.api_key_env, "ARK_API_KEY")
            self.assertEqual(config.model, "ep-auto")

    def test_rejects_real_key_in_api_key_env_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "semantic.json"
            config_path.write_text(
                json.dumps(
                    {
                        "provider": "test",
                        "base_url": "https://example.com/v1/",
                        "model": "vision-model",
                        "api_key_env": "actual.key.value",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "环境变量名"):
                SemanticSceneConfig.load(config_path)

    def test_grouping_requires_configured_environment_variable(self):
        config = SemanticSceneConfig(
            provider="test",
            base_url="https://example.com/v1/",
            model="vision-model",
            api_key_env="MISSING_TEST_VISION_API_KEY",
        )
        grouper = SemanticSceneGrouper(config)
        scenes = [
            {
                "scene_number": 1,
                "start_time": 0.0,
                "end_time": 1.0,
            }
        ]

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MISSING_TEST_VISION_API_KEY"):
                grouper.group_and_export("video.mp4", scenes, [], "output")


class TestSemanticSceneNormalization(unittest.TestCase):
    def setUp(self):
        self.scenes = [
            {"scene_number": 1, "start_time": 0.0, "end_time": 1.0},
            {"scene_number": 2, "start_time": 1.0, "end_time": 2.5},
            {"scene_number": 3, "start_time": 2.5, "end_time": 4.0},
            {"scene_number": 4, "start_time": 4.0, "end_time": 6.0},
            {"scene_number": 5, "start_time": 6.0, "end_time": 8.0},
            {"scene_number": 6, "start_time": 8.0, "end_time": 10.0},
        ]

    def test_normalizes_six_cuts_into_two_semantic_scenes(self):
        groups = SemanticSceneGrouper.normalize_groups(
            [
                {
                    "start_scene": 1,
                    "end_scene": 3,
                    "reason": "同一事件连续正反打",
                    "summary": "人物交谈",
                },
                {
                    "start_scene": 4,
                    "end_scene": 6,
                    "reason": "进入新的动作事件",
                    "summary": "人物离开",
                },
            ],
            self.scenes,
        )

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["source_scenes"], [1, 2, 3])
        self.assertEqual(groups[0]["start_time"], 0.0)
        self.assertEqual(groups[0]["end_time"], 4.0)
        self.assertEqual(groups[1]["source_scenes"], [4, 5, 6])
        self.assertEqual(groups[1]["start_time"], 4.0)
        self.assertEqual(groups[1]["end_time"], 10.0)

    def test_rejects_gap_between_groups(self):
        with self.assertRaisesRegex(ValueError, "漏段"):
            SemanticSceneGrouper.normalize_groups(
                [
                    {"start_scene": 1, "end_scene": 2},
                    {"start_scene": 4, "end_scene": 6},
                ],
                self.scenes,
            )

    def test_rejects_overlap_between_groups(self):
        with self.assertRaisesRegex(ValueError, "重叠"):
            SemanticSceneGrouper.normalize_groups(
                [
                    {"start_scene": 1, "end_scene": 3},
                    {"start_scene": 3, "end_scene": 6},
                ],
                self.scenes,
            )

    def test_rejects_incomplete_coverage(self):
        with self.assertRaisesRegex(ValueError, "没有覆盖全部"):
            SemanticSceneGrouper.normalize_groups(
                [{"start_scene": 1, "end_scene": 3}],
                self.scenes,
            )

    def test_parses_fenced_json_response(self):
        parsed = SemanticSceneGrouper._parse_json_content(
            '```json\n{"groups":[{"start_scene":1,"end_scene":2}]}\n```'
        )
        self.assertEqual(parsed["groups"][0]["end_scene"], 2)


if __name__ == "__main__":
    unittest.main()
