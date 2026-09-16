# Skip Existing Target Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skip a source video's entire processing flow when a matching historical output directory already contains `video_no_subtitles.mp4`.

**Architecture:** Add a focused lookup method to `BatchProcessor` that recognizes the existing `<video-name>_YYYYMMDD_HHMMSS/video_no_subtitles.mp4` contract. Call it after validating the source exists but before constructing `VideoAnalyzer`, preserving all existing processing behavior when no target is found.

**Tech Stack:** Python standard library (`pathlib`, `re`), `unittest`, `unittest.mock`

---

## File Structure

- Create `tests/test_batch_processor.py`: isolated tests for historical target matching and processing short-circuit behavior.
- Modify `src/utils/batch_processor.py`: target lookup and early return before analyzer creation.
- Modify `README.md`: document automatic skip behavior for repeated runs.

### Task 1: Historical Target Lookup

**Files:**
- Create: `tests/test_batch_processor.py`
- Modify: `src/utils/batch_processor.py:1-28`

- [ ] **Step 1: Write failing lookup tests**

Create `tests/test_batch_processor.py`:

```python
import tempfile
import unittest
from pathlib import Path

from src.utils.batch_processor import BatchProcessor


class TestBatchProcessorExistingOutput(unittest.TestCase):
    def test_finds_target_in_exact_timestamped_video_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            target = (
                output_root
                / "example_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"video")

            processor = BatchProcessor(output_dir=str(output_root))

            self.assertEqual(
                processor._find_existing_target_video("/videos/example.mp4"),
                target,
            )

    def test_ignores_other_video_with_matching_name_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            target = (
                output_root
                / "example_extra_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"video")

            processor = BatchProcessor(output_dir=str(output_root))

            self.assertIsNone(
                processor._find_existing_target_video("/videos/example.mp4")
            )

    def test_returns_none_when_output_root_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            processor = BatchProcessor(output_dir=str(Path(tmp) / "missing"))

            self.assertIsNone(
                processor._find_existing_target_video("/videos/example.mp4")
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run lookup tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_batch_processor.TestBatchProcessorExistingOutput -v
```

Expected: all three tests fail with `AttributeError` because `_find_existing_target_video` does not exist.

- [ ] **Step 3: Implement the minimal lookup**

Update the imports and add the method to `BatchProcessor`:

```python
import os
import re
import time
from pathlib import Path


class BatchProcessor:
    """批量视频处理器"""

    TARGET_VIDEO_FILENAME = "video_no_subtitles.mp4"

    def _find_existing_target_video(self, video_path):
        output_root = Path(self.output_dir)
        if not output_root.is_dir():
            return None

        video_name = Path(video_path).stem
        output_name_pattern = re.compile(
            rf"{re.escape(video_name)}_\d{{8}}_\d{{6}}"
        )

        for candidate_dir in sorted(output_root.iterdir(), reverse=True):
            if (
                candidate_dir.is_dir()
                and output_name_pattern.fullmatch(candidate_dir.name)
            ):
                target_video = candidate_dir / self.TARGET_VIDEO_FILENAME
                if target_video.is_file():
                    return target_video

        return None
```

- [ ] **Step 4: Run lookup tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_batch_processor.TestBatchProcessorExistingOutput -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit the lookup**

```bash
git add src/utils/batch_processor.py tests/test_batch_processor.py
git commit -m "feat(batch): detect existing target videos"
```

### Task 2: Skip the Entire Processing Flow

**Files:**
- Modify: `tests/test_batch_processor.py`
- Modify: `src/utils/batch_processor.py:70-90`

- [ ] **Step 1: Write the failing short-circuit test**

Add these imports:

```python
from types import SimpleNamespace
from unittest.mock import patch
```

Add this test to `TestBatchProcessorExistingOutput`:

```python
    def test_existing_target_skips_analyzer_initialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_video = Path(tmp) / "example.mp4"
            input_video.write_bytes(b"source")
            output_root = Path(tmp) / "output"
            target = (
                output_root
                / "example_20260916_134659"
                / "video_no_subtitles.mp4"
            )
            target.parent.mkdir(parents=True)
            target.write_bytes(b"video")
            args = SimpleNamespace(
                remove_subtitles=False,
                audio_only=True,
                scenes_only=True,
            )
            processor = BatchProcessor(output_dir=str(output_root))

            with patch(
                "src.utils.batch_processor.VideoAnalyzer"
            ) as analyzer_class:
                result = processor.process_video(str(input_video), args)

            self.assertTrue(result)
            analyzer_class.assert_not_called()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_batch_processor.TestBatchProcessorExistingOutput.test_existing_target_skips_analyzer_initialization -v
```

Expected: FAIL because `VideoAnalyzer` is initialized.

- [ ] **Step 3: Add the processing short circuit**

In `BatchProcessor.process_video()`, immediately after the source existence check, add:

```python
        existing_target = self._find_existing_target_video(video_path)
        if existing_target is not None:
            print(
                f"✓ 跳过 '{Path(video_path).name}': "
                f"目标视频已存在于 {existing_target}"
            )
            return True
```

- [ ] **Step 4: Run all batch processor tests**

Run:

```bash
python3 -m unittest tests.test_batch_processor -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit the short circuit**

```bash
git add src/utils/batch_processor.py tests/test_batch_processor.py
git commit -m "feat(batch): skip videos with existing targets"
```

### Task 3: Documentation and Regression Verification

**Files:**
- Modify: `README.md:75-91`

- [ ] **Step 1: Document repeated-run behavior**

After the batch directory example in `README.md`, add:

```markdown
重复运行时，如果 `output/<视频名>_时间戳/video_no_subtitles.mp4`
已经存在，该源视频会被直接跳过，不再创建新目录或执行后续处理。
```

- [ ] **Step 2: Run focused and full test suites**

Run:

```bash
python3 -m unittest tests.test_batch_processor -v
python3 -m pytest tests/ -q
```

Expected: batch processor tests and the complete test suite pass without errors.

- [ ] **Step 3: Check the final diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only the intended source, test, and README changes remain.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md
git commit -m "docs: explain existing video skip behavior"
```
