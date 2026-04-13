"""
Feature flag registry tests.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from config.feature_flags import FeatureFlag, FeatureFlagRegistry, feature_flags


class TestFeatureFlags(unittest.TestCase):
    def test_registry_uses_default_value(self):
        registry = FeatureFlagRegistry(
            [
                FeatureFlag("cool_feature", default=False),
            ]
        )

        self.assertFalse(registry.is_enabled("cool_feature"))

    def test_registry_reads_environment_override(self):
        registry = FeatureFlagRegistry(
            [
                FeatureFlag("cool_feature", default=False),
            ]
        )

        with patch.dict(os.environ, {"CHAI_FLAG_COOL_FEATURE": "true"}, clear=False):
            self.assertTrue(registry.is_enabled("cool_feature"))

    def test_override_context_is_scoped(self):
        registry = FeatureFlagRegistry(
            [
                FeatureFlag("cool_feature", default=False),
            ]
        )

        self.assertFalse(registry.is_enabled("cool_feature"))
        with registry.override(cool_feature=True):
            self.assertTrue(registry.is_enabled("cool_feature"))
        self.assertFalse(registry.is_enabled("cool_feature"))

    def test_unknown_flag_raises_key_error(self):
        with self.assertRaises(KeyError):
            feature_flags.is_enabled("missing_flag")


if __name__ == "__main__":
    unittest.main()
