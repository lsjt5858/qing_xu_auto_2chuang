"""Focused tests for workbench media probing failures."""
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from src.services import workbench_api


class ProbeTest(unittest.TestCase):
    def test_timeout_is_mapped_to_unprocessable_entity(self):
        timeout = subprocess.TimeoutExpired(["ffprobe"], 30)

        with patch.object(workbench_api.subprocess, "run", side_effect=timeout):
            with self.assertRaises(workbench_api.HTTPException) as raised:
                workbench_api.probe(Path("slow.mp4"))

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("ffprobe", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
