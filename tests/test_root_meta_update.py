"""
Jianying root metadata registration tests.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.exporters.jianying import _update_root_meta


class TestRootMetaUpdate(unittest.TestCase):
    def test_update_root_meta_registers_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft_root = Path(tmp)
            draft_dir = draft_root / "draft_a"
            draft_dir.mkdir()
            (draft_dir / "draft_info.json").write_text("{}", encoding="utf-8")
            (draft_dir / "draft_meta_info.json").write_text(
                json.dumps(
                    {
                        "draft_id": "DRAFT-1",
                        "draft_name": "draft_a",
                        "draft_fold_path": str(draft_dir),
                        "draft_root_path": str(draft_root),
                        "draft_timeline_materials_size_": 123,
                        "tm_draft_create": 10,
                        "tm_draft_modified": 20,
                        "tm_draft_removed": 0,
                        "tm_duration": 30,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (draft_root / "root_meta_info.json").write_text(
                json.dumps(
                    {
                        "all_draft_store": [],
                        "draft_ids": 0,
                        "root_path": str(draft_root),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            _update_root_meta(draft_root, draft_dir)

            root_meta = json.loads((draft_root / "root_meta_info.json").read_text(encoding="utf-8"))
            self.assertEqual(len(root_meta["all_draft_store"]), 1)
            self.assertEqual(root_meta["all_draft_store"][0]["draft_id"], "DRAFT-1")
            self.assertEqual(root_meta["all_draft_store"][0]["draft_json_file"], str(draft_dir / "draft_info.json"))
            self.assertEqual(root_meta["all_draft_store"][0]["draft_timeline_materials_size"], 123)


if __name__ == "__main__":
    unittest.main()
