from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestRunScript(unittest.TestCase):
    def test_run_script_works_outside_project_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [str(PROJECT_ROOT / "run.sh"), "--help"],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=15,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_workbench_module_default_data_directory_is_project_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(PROJECT_ROOT)
            result = subprocess.run(
                [
                    str(PROJECT_ROOT / "venv/bin/python"),
                    "-m",
                    "src.services.workbench",
                ],
                cwd=tmp,
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"本地数据：{PROJECT_ROOT / 'data/workbench'}",
            result.stdout,
        )


class TestCollectScenesScript(unittest.TestCase):
    def _copy_script(self, root: Path) -> Path:
        source = (PROJECT_ROOT / "collect_scenes.sh").read_text(encoding="utf-8")
        source = source.replace(
            '# HEAD_DIR="/Volumes/xiong_home/哼哼猫下载/情绪/视频头"',
            f'HEAD_DIR="{root / "legacy-head"}"',
        )
        source = source.replace(
            'BODY_DIR="/Users/bytedance/Downloads/douyin_videos/视频身"',
            f'BODY_DIR="{root / "legacy-body"}"',
        )
        script = root / "collect_scenes.sh"
        script.write_text(source, encoding="utf-8")
        return script

    def _make_scenes(self, root: Path) -> Path:
        output_dir = root / "source output"
        scenes_dir = output_dir / "demo project" / "scenes"
        scenes_dir.mkdir(parents=True)
        (scenes_dir / "Scene-001.mp4").write_bytes(b"head")
        (scenes_dir / "Scene-002.mp4").write_bytes(b"body")
        return output_dir

    def test_collect_scenes_requires_destination_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self._copy_script(root)
            result = subprocess.run(
                ["bash", str(script)],
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 2)

    def test_collect_scenes_is_dry_run_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self._copy_script(root)
            output_dir = self._make_scenes(root)
            head_dir = root / "head clips"
            body_dir = root / "body clips"

            result = subprocess.run(
                [
                    "bash",
                    str(script),
                    "--output-dir",
                    str(output_dir),
                    "--head-dir",
                    str(head_dir),
                    "--body-dir",
                    str(body_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DRY-RUN", result.stdout)
            self.assertFalse(head_dir.exists())
            self.assertFalse(body_dir.exists())

    def test_collect_scenes_copies_only_with_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self._copy_script(root)
            output_dir = self._make_scenes(root)
            head_dir = root / "head clips"
            body_dir = root / "body clips"

            result = subprocess.run(
                [
                    "bash",
                    str(script),
                    "--output-dir",
                    str(output_dir),
                    "--head-dir",
                    str(head_dir),
                    "--body-dir",
                    str(body_dir),
                    "--execute",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (head_dir / "demo project_Scene-001.mp4").read_bytes(),
                b"head",
            )
            self.assertEqual(
                (body_dir / "demo project_Scene-002.mp4").read_bytes(),
                b"body",
            )

    def test_collect_scenes_reports_copy_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = self._copy_script(root)
            output_dir = self._make_scenes(root)
            head_dir = root / "head clips"
            body_dir = root / "body clips"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_cp = fake_bin / "cp"
            fake_cp.write_text(
                "#!/usr/bin/env bash\n"
                '[[ "$1" == *"Scene-002.mp4" ]] && exit 1\n'
                'exec /bin/cp "$@"\n',
                encoding="utf-8",
            )
            fake_cp.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin}:{env['PATH']}"

            result = subprocess.run(
                [
                    "bash",
                    str(script),
                    "--output-dir",
                    str(output_dir),
                    "--head-dir",
                    str(head_dir),
                    "--body-dir",
                    str(body_dir),
                    "--execute",
                ],
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 1)
            self.assertTrue((head_dir / "demo project_Scene-001.mp4").is_file())
            self.assertFalse((body_dir / "demo project_Scene-002.mp4").exists())
            self.assertIn("已复制: 1", result.stdout)
            self.assertIn("失败: 1", result.stdout)


if __name__ == "__main__":
    unittest.main()
