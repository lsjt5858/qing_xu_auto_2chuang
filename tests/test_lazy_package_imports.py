"""
Package-level imports should stay light and avoid importing heavy pipeline modules.
"""
from __future__ import annotations

import subprocess
import sys
import unittest


class TestLazyPackageImports(unittest.TestCase):
    def test_utils_and_core_packages_do_not_import_pipeline_eagerly(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import src.utils; import src.core; "
                    "print('src.utils.batch_processor' in sys.modules); "
                    "print('src.core.scene_detector' in sys.modules)"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip().splitlines(), ["False", "False"])


if __name__ == "__main__":
    unittest.main()
