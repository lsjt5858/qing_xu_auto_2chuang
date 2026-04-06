# API 文档

## 核心模块

### VideoAnalyzer

主要的视频分析类，整合所有功能。

```python
from src.core import VideoAnalyzer

analyzer = VideoAnalyzer("video.mp4", output_dir="output")

# 分析场景
scenes = analyzer.analyze_scenes(threshold=27.0)

# 提取音频
audio_path = analyzer.extract_audio()

# 转录音频
transcript = analyzer.transcribe_audio(audio_path, model_size="base")

# 生成报告
report = analyzer.generate_report(scenes, transcript)
```

### SceneDetector

场景检测和分割。

```python
from src.core import SceneDetector

detector = SceneDetector(threshold=27.0)
scenes_info, scene_list = detector.detect_scenes("video.mp4")
detector.split_video("video.mp4", scene_list, "output/scenes")
```

### AudioExtractor

音频提取。

```python
from src.core import AudioExtractor

extractor = AudioExtractor()
audio_path = extractor.extract("video.mp4", "output/audio.mp3")
```

### Transcriber

语音转文字。

```python
from src.core import Transcriber

transcriber = Transcriber(model_size="base")
result = transcriber.transcribe("audio.mp3", language="zh")
```

## 工具模块

### BatchProcessor

批量处理多个视频。

```python
from src.utils import BatchProcessor

processor = BatchProcessor(output_dir="output")
result = processor.process_batch(video_list, args)
processor.print_summary(result)
```

### 文件工具

```python
from src.utils import read_video_list, ensure_dir

# 读取视频列表
videos = read_video_list("videos.txt")

# 确保目录存在
ensure_dir("output/scenes")
```
