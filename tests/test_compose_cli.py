from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.cli import main
from src.commands.compose import build_parser
from src.models import MediaMetadata


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestComposeCli(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.pool = self.root / "pool"
        self.pool.mkdir()
        for name in ["a.mp4", "b.mp4", "c.mp4"]:
            (self.pool / name).touch()
        self.output = self.root / "new" / "out.mp4"

    def run_cli(self, *args):
        out, err = StringIO(), StringIO()
        with (
            redirect_stdout(out), redirect_stderr(err),
            patch("src.composition.directory_composer.probe_media",
                  side_effect=lambda path: MediaMetadata(path, 3_000_000, 320, 180, True)),
        ):
            code = main(["compose", *map(str, args)])
        return code, out.getvalue(), err.getvalue()

    def test_dry_run_seed_full_clips_and_no_side_effects(self):
        with patch("src.commands.compose.resolve_draft_root") as resolve:
            code, text, err = self.run_cli(
                "--head-dir", self.pool, "--head-count", 2, "--seed", 42,
                "-o", self.output, "--export-jianying",
                "--draft-root", self.root / "drafts",
            )
        self.assertEqual(code, 0, err)
        resolve.assert_not_called()
        self.assertFalse(self.output.parent.exists())
        self.assertFalse((self.root / "drafts").exists())
        plan = json.loads(text)
        self.assertEqual(plan["seed"], 42)
        self.assertEqual(plan["duration_us"], 6_000_000)
        self.assertEqual([c["source_start_us"] for c in plan["clips"]], [0, 0])
        self.assertFalse(plan["executed"])
        code2, text2, _ = self.run_cli("--head-dir", self.pool, "--head-count", 2,
                                     "--seed", 42, "-o", self.output)
        self.assertEqual(code2, 0)
        self.assertEqual(plan["clips"], json.loads(text2)["clips"])

    def test_part_order_and_all(self):
        code, text, err = self.run_cli(
            "--part", self.pool, 1, "--part", self.pool, "all", "--selection", "ordered",
        )
        self.assertEqual(code, 0, err)
        clips = json.loads(text)["clips"]
        self.assertEqual([c["role"] for c in clips], ["part-1", "part-2", "part-2", "part-2"])
        self.assertEqual([Path(c["source_path"]).name for c in clips],
                         ["a.mp4", "a.mp4", "b.mp4", "c.mp4"])

    def test_rejects_invalid_args_without_creating_output(self):
        cases = [
            [], ["--part", self.pool, 1, "--head-dir", self.pool],
            ["--part", self.pool, 1, "--head-dir", ""],
            ["--part", self.pool, 1, "--body-dir", ""],
            ["--part", self.pool, 1, "--tail-dir", ""],
            ["--head-dir", ""], ["--part", "", 1],
            ["--head-count", 2], ["--part", self.pool, 0],
            ["--part", self.pool, "garbage"], ["--head-dir", self.root / "absent"],
            ["--head-dir", self.pool, "--width", 301],
            ["--head-dir", self.pool, "--fps", 0],
            ["--head-dir", self.pool, "--bgm-volume", "nan"],
            ["--head-dir", self.pool, "--bgm-volume", 1.1],
            ["--head-dir", self.pool, "--clip-duration", 0],
            ["--head-dir", self.pool, "--photo-duration", "inf"],
            ["--head-dir", self.pool, "--body-count", 2],
            ["--head-dir", self.pool, "--bgm", self.root / "absent.wav"],
        ]
        for args in cases:
            with self.subTest(args=args):
                code, _, err = self.run_cli(*args, "-o", self.output)
                self.assertEqual(code, 2, err)
                self.assertFalse(self.output.parent.exists())

    def test_existing_video_or_manifest_and_source_cannot_be_overwritten(self):
        self.output.parent.mkdir()
        for path in [self.output, self.output.with_suffix(".json")]:
            path.write_text("preserve")
            code, _, _ = self.run_cli("--head-dir", self.pool, "-o", self.output, "--execute")
            self.assertEqual(code, 2)
            self.assertEqual(path.read_text(), "preserve")
            path.unlink()
        code, _, _ = self.run_cli("--head-dir", self.pool, "-o", self.pool / "a.mp4", "--execute")
        self.assertEqual(code, 2)

    def test_default_output_names_are_unique(self):
        a = json.loads(self.run_cli("--head-dir", self.pool)[1])["output_path"]
        b = json.loads(self.run_cli("--head-dir", self.pool)[1])["output_path"]
        self.assertNotEqual(a, b)

    def test_execution_errors_return_one(self):
        with patch("src.commands.compose.render_timeline", side_effect=RuntimeError("render failed")):
            code, _, err = self.run_cli("--head-dir", self.pool, "-o", self.output, "--execute")
        self.assertEqual(code, 1)
        self.assertIn("render failed", err)

    def test_execute_publishes_manifest_after_draft_copies_temporary_materials(self):
        from dataclasses import replace

        draft_root = self.root / "drafts"
        draft_path = draft_root / "demo"

        def render(clips, output, *, work_dir, **kwargs):
            normalized = work_dir / "clip.mov"
            normalized.write_bytes(b"normalized")
            audio = work_dir / "mix.m4a"
            audio.write_bytes(b"mixed")
            output.write_bytes(b"finished")
            return SimpleNamespace(
                video_path=output, clips=(replace(clips[0], source_path=normalized),),
                audio_path=audio,
            )

        def export(artifacts, *, timeline_clips, **kwargs):
            self.assertEqual(kwargs["style_template"], "basic")
            self.assertEqual(kwargs["fps"], 24)
            draft_path.mkdir()
            (draft_path / "video.mov").write_bytes(timeline_clips[0].source_path.read_bytes())
            (draft_path / "audio.m4a").write_bytes(artifacts.audio_path.read_bytes())
            return draft_path

        with (
            patch("src.commands.compose.render_timeline", side_effect=render),
            patch("src.commands.compose.export_to_jianying_draft", side_effect=export),
            patch("src.commands.compose.probe_media",
                  side_effect=lambda p: MediaMetadata(p, 3_000_000, 0, 0, True)),
        ):
            code, text, err = self.run_cli(
                "--head-dir", self.pool, "--seed", 42, "-o", self.output, "--execute",
                "--export-jianying", "--draft-root", draft_root, "--draft-name", "demo",
                "--fps", 24,
            )
        self.assertEqual(code, 0, err)
        plan = json.loads(text)
        self.assertTrue(plan["executed"])
        self.assertEqual(plan["draft_path"], str(draft_path))
        self.assertEqual(self.output.read_bytes(), b"finished")
        self.assertEqual(json.loads(self.output.with_suffix(".json").read_text()), plan)
        self.assertEqual((draft_path / "audio.m4a").read_bytes(), b"mixed")
        self.assertEqual((draft_path / "video.mov").read_bytes(), b"normalized")
        self.assertFalse(list(self.output.parent.glob(".compose-*")))

    def test_parser_exposes_draft_overrides(self):
        args = build_parser().parse_args(["--head-dir", "A", "--draft-root", "drafts",
                                         "--template-dir", "template", "--draft-name", "demo"])
        self.assertEqual(args.draft_root, "drafts")
        self.assertEqual(args.draft_name, "demo")

    def test_shell_help_works_from_external_directory(self):
        result = subprocess.run(
            [str(PROJECT_ROOT / "run.sh"), "compose", "--help"], cwd=self.root,
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--execute", result.stdout)
        self.assertIn("--part", result.stdout)

    def test_legacy_parser_keeps_existing_behavior_and_new_explicit_offset(self):
        from src.cli import create_parser
        from src.utils.jianying_draft_exporter import build_parser as exporter_parser

        args = create_parser().parse_args(["video.mp4", "--scenes-only"])
        self.assertTrue(args.scenes_only)
        self.assertEqual(args.pool_clip_start, "start")
        self.assertEqual(exporter_parser().parse_args(["out", "--pool-clip-start", "random"])
                         .pool_clip_start, "random")
