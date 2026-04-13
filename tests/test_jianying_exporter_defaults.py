"""
Jianying exporter defaults should stay self-contained in this repository.
"""
from __future__ import annotations

import unittest

from src.exporters.jianying import DEFAULT_TEMPLATE_DIR


class TestJianyingExporterDefaults(unittest.TestCase):
    def test_default_template_dir_exists_inside_repo(self):
        self.assertTrue(DEFAULT_TEMPLATE_DIR.exists())
        self.assertEqual(DEFAULT_TEMPLATE_DIR.name, "jianying")
        self.assertEqual(DEFAULT_TEMPLATE_DIR.parent.name, "templates")


if __name__ == "__main__":
    unittest.main()
