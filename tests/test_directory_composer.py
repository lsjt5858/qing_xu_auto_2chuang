from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.composition.directory_composer import DirectoryStage, compose_directories
from src.models import MediaMetadata


class TestDirectoryComposer(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def pool(self, name, files):
        directory = self.root / name
        directory.mkdir()
        for file in files:
            path = directory / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        return directory

    @staticmethod
    def probe(path):
        return MediaMetadata(path, 8_000_000, 320, 180, False)

    def compose(self, stages, **kwargs):
        return compose_directories(stages, seed=42, probe=self.probe, **kwargs)

    def test_stage_order_full_lengths_and_continuous_timeline(self):
        stages = [
            DirectoryStage(self.pool(role, ["0.mp4", "1.mov"]), count, role)
            for role, count in [("head", 1), ("body", 2), ("tail", 1)]
        ]
        clips = self.compose(stages)
        self.assertEqual([clip.role for clip in clips], ["head", "body", "body", "tail"])
        self.assertEqual([clip.source_start_us for clip in clips], [0] * 4)
        self.assertEqual([clip.timeline_duration_us for clip in clips], [8_000_000] * 4)
        self.assertEqual([clip.timeline_start_us for clip in clips],
                         [0, 8_000_000, 16_000_000, 24_000_000])

    def test_seed_is_reproducible_and_selection_does_not_repeat(self):
        stage = DirectoryStage(self.pool("pool", [f"{i}.mp4" for i in range(10)]), 5)
        first = self.compose([stage])
        self.assertEqual(first, self.compose([stage]))
        self.assertEqual(len({c.source_path for c in first}), 5)
        self.assertNotEqual(first, compose_directories([stage], seed=1, probe=self.probe))

    def test_all_recursive_ordered_and_hidden_paths(self):
        directory = self.pool("pool", [
            "b.mp4", "a/a.mov", "c.PNG", ".hidden.mp4", ".hidden/z.mp4", "notes.txt",
        ])
        clips = self.compose([DirectoryStage(directory, None)], selection="ordered")
        self.assertEqual([c.source_path.relative_to(directory).as_posix() for c in clips],
                         ["a/a.mov", "b.mp4", "c.PNG"])
        self.assertEqual(clips[-1].timeline_duration_us, 2_000_000)

    def test_rejects_insufficient_empty_or_missing_directory(self):
        directory = self.pool("one", ["a.mp4"])
        for stage in [DirectoryStage(directory, 2),
                      DirectoryStage(self.pool("empty", []), None),
                      DirectoryStage(self.root / "missing")]:
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                self.compose([stage])

    def test_explicit_trim_and_short_video_clamp(self):
        directory = self.pool("one", ["a.mp4"])
        clips = self.compose([DirectoryStage(directory)], clip_start=3, clip_duration=20)
        self.assertEqual(clips[0].source_start_us, 3_000_000)
        self.assertEqual(clips[0].timeline_duration_us, 5_000_000)
        limited = self.compose([DirectoryStage(directory)], clip_duration=1.25)
        self.assertEqual(limited[0].timeline_duration_us, 1_250_000)
        with self.assertRaisesRegex(ValueError, "a.mp4"):
            self.compose([DirectoryStage(directory)], clip_start=8)

    def test_photos_use_configured_duration_and_ignore_video_trimming(self):
        directory = self.pool("one", ["a.jpg"])
        clip = self.compose([DirectoryStage(directory)], photo_duration=3.5,
                            clip_start=20, clip_duration=1)[0]
        self.assertEqual(clip.source_start_us, 0)
        self.assertEqual(clip.timeline_duration_us, 3_500_000)

    def test_rejects_invalid_options_before_scanning(self):
        stage = DirectoryStage(self.root / "missing")
        for kwargs in [{"selection": "other"}, {"photo_duration": 0},
                       {"photo_duration": float("nan")}, {"clip_start": -1},
                       {"clip_start": float("inf")}, {"clip_duration": 0},
                       {"clip_duration": 0.0000001}, {"clip_duration": float("nan")},
                       {"clip_start": 1e308}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.compose([stage], **kwargs)
        for count in [0, -1, 1.5]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.compose([DirectoryStage(stage.directory, count)])
        with self.assertRaises(ValueError):
            self.compose([])

    def test_rejects_unusable_video_or_image(self):
        directory = self.pool("one", ["a.mp4"])
        for metadata in [MediaMetadata(directory / "a.mp4", 0, 320, 180, False),
                         MediaMetadata(directory / "a.mp4", 8_000_000, 0, 0, True)]:
            with self.subTest(metadata=metadata), self.assertRaisesRegex(ValueError, "a.mp4"):
                compose_directories([DirectoryStage(directory)], seed=0,
                                    probe=lambda path: metadata)
