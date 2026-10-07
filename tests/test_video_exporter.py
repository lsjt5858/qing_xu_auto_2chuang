from __future__ import annotations

from array import array
import base64
from dataclasses import FrozenInstanceError, replace
import json
import math
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.models.artifacts import TimelineClip, probe_media


def load_renderer():
    try:
        from src.exporters.video import RenderedTimeline, render_timeline
    except ImportError as exc:
        raise AssertionError("The timeline renderer is not implemented") from exc
    return RenderedTimeline, render_timeline


def ffmpeg(*args):
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", *map(str, args)],
        check=True, capture_output=True, timeout=30,
    ).stdout


def streams(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    return {stream["codec_type"]: stream for stream in json.loads(result.stdout)["streams"]}


def audio_samples(path, start=0.0, duration=0.1):
    data = ffmpeg(
        "-i", path, "-ss", start, "-t", duration,
        "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-f", "s16le", "-",
    )
    samples = array("h")
    samples.frombytes(data)
    return samples


def rms(samples):
    return math.sqrt(sum(value * value for value in samples) / max(1, len(samples)))


def tone_amplitude(samples, frequency):
    angle = 2 * math.pi * frequency / 48_000
    real = sum(value * math.cos(angle * i) for i, value in enumerate(samples))
    imaginary = sum(value * math.sin(angle * i) for i, value in enumerate(samples))
    return 2 * math.hypot(real, imaginary) / max(1, len(samples))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class TestVideoExporter(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "\u7d20\u6750 space's"
        self.root.mkdir()
        self.work_dir = self.root / "\u4e34\u65f6 work's"
        self.output = self.root / "\u6210\u7247 preview's.mp4"

    def video(self, name="source.mov", *, color="red", size="96x48", fps=10,
              duration=0.8, audio_duration=None, sar="1"):
        path = self.root / name
        args = [
            "-f", "lavfi", "-i",
            f"color=c={color}:s={size}:r={fps}:d={duration},setsar={sar}",
        ]
        if audio_duration is not None:
            args += [
                "-f", "lavfi", "-i",
                f"sine=frequency=400:sample_rate=32000:duration={audio_duration}",
                "-map", "0:v:0", "-map", "1:a:0", "-c:a", "pcm_s16le",
            ]
        args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", path]
        ffmpeg(*args)
        return path

    def clip(self, path, duration=None, *, start=0, timeline_start=0, role="scene"):
        duration = probe_media(path).duration_us if duration is None else duration
        return TimelineClip(
            source_path=path, timeline_start_us=timeline_start,
            timeline_duration_us=duration, source_start_us=start,
            source_duration_us=duration, role=role, label=path.name,
        )

    def render(self, clips, **kwargs):
        _, render_timeline = load_renderer()
        options = dict(work_dir=self.work_dir, width=128, height=96, fps=10)
        options.update(kwargs)
        return render_timeline(clips, self.output, **options)

    def frame(self, path, time):
        data = ffmpeg(
            "-i", path, "-ss", time, "-frames:v", "1", "-an",
            "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
        )
        self.assertEqual(len(data), 128 * 96 * 3)
        return data

    @staticmethod
    def pixel(data, x, y):
        offset = (y * 128 + x) * 3
        return data[offset:offset + 3]

    def assert_timeline(self, rendered, originals):
        result_type, _ = load_renderer()
        self.assertIsInstance(rendered, result_type)
        self.assertIsInstance(rendered.clips, tuple)
        self.assertEqual(len(rendered.clips), len(originals))
        self.assertEqual(rendered.video_path, self.output)
        self.assertTrue(rendered.audio_path.is_relative_to(self.work_dir))
        self.assertTrue(rendered.audio_path.is_file())
        cursor = 0
        for normalized, original in zip(rendered.clips, originals):
            self.assertTrue(normalized.source_path.is_relative_to(self.work_dir))
            metadata = probe_media(normalized.source_path)
            self.assertEqual(normalized.timeline_start_us, cursor)
            self.assertEqual(normalized.source_start_us, 0)
            self.assertEqual(normalized.timeline_duration_us, metadata.duration_us)
            self.assertEqual(normalized.source_duration_us, metadata.duration_us)
            self.assertEqual((normalized.role, normalized.label), (original.role, original.label))
            cursor += normalized.timeline_duration_us
        self.assertAlmostEqual(probe_media(rendered.video_path).duration_us, cursor, delta=2)
        self.assertAlmostEqual(probe_media(rendered.audio_path).duration_us, cursor, delta=1000)
        with self.assertRaises(FrozenInstanceError):
            rendered.video_path = self.root / "changed.mp4"
        return cursor

    def test_normalizes_and_concatenates_full_silent_clips_with_special_paths(self):
        red = self.video("\u7ea2 red's.mov", duration=0.5, fps=12)
        blue = self.video("blue.mov", color="blue", size="32x64", duration=0.4, fps=20)
        clips = [self.clip(red, role="head"), self.clip(blue, timeline_start=9_000_000)]
        result = self.render(clips)

        self.assertEqual(self.assert_timeline(result, clips), 900_000)
        for path in [result.video_path, *(clip.source_path for clip in result.clips)]:
            info = streams(path)
            self.assertEqual((info["video"]["width"], info["video"]["height"]), (128, 96))
            self.assertEqual(info["video"]["sample_aspect_ratio"], "1:1")
            self.assertEqual(info["video"]["avg_frame_rate"], "10/1")
            self.assertEqual(info["audio"]["sample_rate"], "48000")
            self.assertEqual(info["audio"]["channels"], 2)
        self.assertGreater(self.pixel(self.frame(result.video_path, 0.1), 64, 48)[0], 220)
        self.assertGreater(self.pixel(self.frame(result.video_path, 0.7), 64, 48)[2], 220)
        self.assertLess(rms(audio_samples(result.audio_path, 0.65)), 1)
        ffmpeg("-i", result.video_path, "-f", "null", "-")

    def test_short_source_audio_is_preserved_then_padded_to_video_end(self):
        source = self.video(audio_duration=0.2)
        clips = [self.clip(source)]
        result = self.render(clips)

        self.assertEqual(self.assert_timeline(result, clips), 800_000)
        for path in [result.audio_path, result.video_path, result.clips[0].source_path]:
            self.assertGreater(rms(audio_samples(path, 0.03)), 1000)
            tail = audio_samples(path, 0.6)
            self.assertGreaterEqual(len(tail), 4790)
            self.assertLess(rms(tail), 2)

    def test_explicit_source_start_selects_later_frames(self):
        source = self.root / "red then blue.mov"
        ffmpeg(
            "-f", "lavfi", "-i",
            "color=red:s=96x48:r=10:d=0.4[r];"
            "color=blue:s=96x48:r=10:d=0.4[b];[r][b]concat=n=2:v=1:a=0",
            "-c:v", "libx264", "-preset", "ultrafast", source,
        )
        clips = [self.clip(source, 300_000, start=400_000)]
        result = self.render(clips)

        self.assertEqual(self.assert_timeline(result, clips), 300_000)
        self.assertGreater(self.pixel(self.frame(result.video_path, 0.1), 64, 48)[2], 220)

    def test_non_square_sar_preserves_display_aspect(self):
        for index, (sar, expected_width, expected_height) in enumerate(
            [("2", 128, 32), ("1/2", 96, 96)]
        ):
            with self.subTest(sar=sar):
                source = self.video(f"sar{index}.mov", color="white", sar=sar, duration=0.2)
                self.output = self.root / f"sar{index}.mp4"
                result = self.render([self.clip(source)])
                frame = self.frame(result.video_path, 0)
                content_width = sum(self.pixel(frame, x, 48)[0] > 200 for x in range(128))
                content_height = sum(self.pixel(frame, 64, y)[0] > 200 for y in range(96))
                self.assertAlmostEqual(content_width, expected_width, delta=2)
                self.assertAlmostEqual(content_height, expected_height, delta=2)

    def test_photo_is_held_for_requested_duration_rounded_to_frames(self):
        photo = self.root / "still.png"
        ffmpeg("-f", "lavfi", "-i", "color=lime:s=32x64", "-frames:v", "1", photo)
        clips = [self.clip(photo, 350_000, role="photo"), self.clip(photo, 240_000)]
        result = self.render(clips)

        self.assertEqual(self.assert_timeline(result, clips), 600_000)
        self.assertEqual([c.timeline_duration_us for c in result.clips], [400_000, 200_000])
        self.assertGreater(self.pixel(self.frame(result.video_path, 0.5), 64, 48)[1], 220)
        self.assertLess(rms(audio_samples(result.audio_path, 0.4)), 1)

    def bgm(self):
        path = self.root / "\u914d\u4e50 short's.wav"
        ffmpeg(
            "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=44100:duration=0.1",
            "-c:a", "pcm_s16le", path,
        )
        return path

    def test_short_bgm_loops_and_mixes_without_reducing_source_volume(self):
        source = self.video(audio_duration=0.8)
        clips = [self.clip(source, 400_000), self.clip(source, 400_000, start=400_000)]
        result = self.render(clips, bgm_path=self.bgm())

        self.assertEqual(self.assert_timeline(result, clips), 800_000)
        for start in (0.05, 0.35, 0.65):
            samples = audio_samples(result.audio_path, start)
            voice = tone_amplitude(samples, 400)
            music = tone_amplitude(samples, 1000)
            self.assertGreater(voice, 2500)
            self.assertAlmostEqual(music / voice, 0.35, delta=0.06)
        self.assertEqual(
            audio_samples(result.audio_path, 0, 0.8),
            audio_samples(result.video_path, 0, 0.8),
        )

    def test_mute_source_without_bgm_produces_full_silence(self):
        source = self.video(audio_duration=0.8)
        clips = [self.clip(source)]
        result = self.render(clips, mute_source=True)

        self.assertEqual(self.assert_timeline(result, clips), 800_000)
        self.assertLess(rms(audio_samples(result.audio_path, 0.1, 0.6)), 1)
        self.assertLess(rms(audio_samples(result.video_path, 0.1, 0.6)), 1)

    def test_mute_source_with_bgm_retains_only_looped_music(self):
        source = self.video(audio_duration=0.8)
        result = self.render([self.clip(source)], bgm_path=self.bgm(),
                             bgm_volume=0.5, mute_source=True)

        samples = audio_samples(result.audio_path, 0.65)
        self.assertGreater(tone_amplitude(samples, 1000), 1200)
        self.assertLess(tone_amplitude(samples, 400), 10)

    def test_zero_bgm_volume_preserves_source_audio(self):
        source = self.video(audio_duration=0.8)
        result = self.render([self.clip(source)], bgm_path=self.bgm(), bgm_volume=0)

        samples = audio_samples(result.audio_path, 0.65)
        self.assertGreater(tone_amplitude(samples, 400), 2500)
        self.assertLess(tone_amplitude(samples, 1000), 10)

    def test_all_photo_formats_produce_full_length_video(self):
        clips = []
        for suffix in (".jpg", ".jpeg", ".PNG", ".webp", ".bmp", ".tif", ".tiff"):
            photo = self.root / f"photo{suffix}"
            if suffix == ".webp":
                # A real 1x1 lossless WebP; libwebp encoding is optional in FFmpeg.
                photo.write_bytes(base64.b64decode(
                    "UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA=="
                ))
            else:
                ffmpeg("-f", "lavfi", "-i", "color=white:s=32x32",
                       "-frames:v", "1", photo)
            clips.append(self.clip(photo, 200_000, role="photo"))
        result = self.render(clips)
        self.assertEqual(self.assert_timeline(result, clips), 1_400_000)
        for index in range(len(clips)):
            self.frame(result.video_path, index * 0.2 + 0.1)

    def test_fractional_frame_durations_do_not_accumulate_container_gaps(self):
        source = self.video(fps=30, duration=0.1, audio_duration=0.1)
        clips = [self.clip(source, 33_333) for _ in range(9)]
        result = self.render(clips, fps=30)
        cursor = 0
        for clip in result.clips:
            self.assertEqual(clip.timeline_start_us, cursor)
            self.assertEqual(clip.timeline_duration_us, probe_media(clip.source_path).duration_us)
            cursor += clip.timeline_duration_us
        self.assertAlmostEqual(cursor, 300_000, delta=9)
        self.assertAlmostEqual(probe_media(result.video_path).duration_us, 300_000, delta=10)
        self.assertEqual(int(streams(result.video_path)["video"]["nb_frames"]), 9)
        self.assertAlmostEqual(probe_media(result.audio_path).duration_us, 300_000, delta=1000)

    def test_request_past_source_end_clamps_to_available_video(self):
        source = self.video(audio_duration=0.2)
        clips = [self.clip(source, 2_000_000, start=300_000), self.clip(source, 200_000)]
        result = self.render(clips)
        self.assertEqual(self.assert_timeline(result, clips), 700_000)
        self.assertEqual(result.clips[0].timeline_duration_us, 500_000)
        self.assertLess(rms(audio_samples(result.audio_path, 0.3)), 1)
        self.assertGreater(rms(audio_samples(result.audio_path, 0.55)), 1000)

    def test_short_video_is_held_to_at_least_one_output_frame(self):
        source = self.video(duration=0.2)
        clips = [self.clip(source)]
        result = self.render(clips, fps=1)
        self.assertEqual(self.assert_timeline(result, clips), 1_000_000)
        self.assertEqual(int(streams(result.video_path)["video"]["nb_frames"]), 1)

    def test_work_directory_can_be_the_output_parent(self):
        source = self.video(duration=0.2)
        self.work_dir = self.root
        clips = [self.clip(source)]
        result = self.render(clips)
        self.assertEqual(self.assert_timeline(result, clips), 200_000)

    def test_rejects_invalid_numeric_options_before_creating_work_files(self):
        source = self.video(duration=0.2)
        clips = [self.clip(source)]
        options = [
            *({"width": value} for value in (0, -2, 127, 128.5, math.nan, math.inf, True, "128")),
            *({"height": value} for value in (0, 95, math.inf)),
            *({"fps": value} for value in (0, -1, 2.5, math.nan, math.inf, True)),
            *({"bgm_volume": value} for value in (-0.1, 1.1, math.nan, math.inf, "0.5", True)),
        ]
        for index, option in enumerate(options):
            with self.subTest(option=option):
                self.work_dir = self.root / f"work{index}"
                self.output = self.root / f"output{index}.mp4"
                try:
                    self.render(clips, **option)
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                else:
                    self.fail("Invalid options were accepted")
                self.assertFalse(self.work_dir.exists())
                self.assertFalse(self.output.exists())

    def test_rejects_empty_or_invalid_clip_timing_before_writing(self):
        source = self.video(duration=0.2)
        clip = self.clip(source)
        cases = [[]]
        for field in ("timeline_start_us", "source_start_us",
                      "timeline_duration_us", "source_duration_us"):
            for value in (-1, math.nan, math.inf):
                cases.append([replace(clip, **{field: value})])
        cases += [[replace(clip, timeline_duration_us=0)], [replace(clip, source_duration_us=0)]]
        cases += [[replace(clip, source_start_us=200_000)]]
        for index, clips in enumerate(cases):
            with self.subTest(clips=clips):
                self.work_dir = self.root / f"work{index}"
                self.output = self.root / f"output{index}.mp4"
                try:
                    self.render(clips)
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                else:
                    self.fail("Invalid clip timing was accepted")
                self.assertFalse(self.work_dir.exists())
                self.assertFalse(self.output.exists())

    def test_existing_output_is_refused_before_rendering(self):
        source = self.video(duration=0.2)
        original = source.read_bytes()
        self.output = source
        with self.assertRaises(FileExistsError):
            self.render([self.clip(source)])
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(self.work_dir.exists())

    def test_dangling_output_symlink_is_not_followed(self):
        source = self.video(duration=0.2)
        target = self.root / "not-created.mp4"
        self.output.symlink_to(target)
        with self.assertRaises(FileExistsError):
            self.render([self.clip(source)])
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(target.exists())
        self.assertFalse(self.work_dir.exists())

    def test_output_created_during_rendering_is_not_overwritten(self):
        source = self.video(duration=0.2)
        clips = [self.clip(source)]
        original_run = subprocess.run
        competing_bytes = b"another process owns this output"

        def race(command, *args, **kwargs):
            if command[0] == "ffmpeg" and not self.output.exists():
                self.output.write_bytes(competing_bytes)
            return original_run(command, *args, **kwargs)

        with patch("src.exporters.video.subprocess.run", side_effect=race):
            with self.assertRaises((FileExistsError, RuntimeError)):
                self.render(clips)
        self.assertEqual(self.output.read_bytes(), competing_bytes)

    def test_missing_or_non_audio_bgm_is_rejected_before_rendering(self):
        source = self.video(duration=0.2)
        for bgm, error in [(self.root / "missing.wav", FileNotFoundError), (source, ValueError)]:
            with self.subTest(bgm=bgm), self.assertRaises(error):
                self.render([self.clip(source)], bgm_path=bgm)
            self.assertFalse(self.work_dir.exists())
            self.assertFalse(self.output.exists())

    def test_corrupt_input_reports_probe_and_filename(self):
        source = self.root / "broken.mov"
        source.write_bytes(b"not a movie")
        with self.assertRaisesRegex(RuntimeError, "ffprobe.*broken.mov"):
            self.render([self.clip(source, 200_000)])
        self.assertFalse(self.output.exists())

    def test_ffmpeg_error_reports_stage_source_and_stderr(self):
        source = self.video(duration=0.2)
        clips = [self.clip(source)]
        original_run = subprocess.run

        def failed_encoder(command, *args, **kwargs):
            if command[0] == "ffmpeg":
                raise subprocess.CalledProcessError(1, command, stderr="Unknown encoder 'libx264'")
            return original_run(command, *args, **kwargs)

        with patch("src.exporters.video.subprocess.run", side_effect=failed_encoder):
            with self.assertRaisesRegex(RuntimeError, "ffmpeg.*source.mov.*libx264"):
                self.render(clips)
        self.assertFalse(self.output.exists())

    def test_missing_ffmpeg_reports_installation_action(self):
        source = self.video(duration=0.2)
        clips = [self.clip(source)]
        original_run = subprocess.run

        def missing_tool(command, *args, **kwargs):
            if command[0] == "ffmpeg":
                raise FileNotFoundError("ffmpeg")
            return original_run(command, *args, **kwargs)

        with patch("src.exporters.video.subprocess.run", side_effect=missing_tool):
            with self.assertRaisesRegex(RuntimeError, "[Ii]nstall.*ffmpeg"):
                self.render(clips)


if __name__ == "__main__":
    unittest.main()
