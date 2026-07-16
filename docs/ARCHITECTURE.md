# 项目架构文档

## 项目结构

```
qing_xu_auto_2chuang/
├── main.py                      # 主入口文件
├── run.sh                       # 便捷运行脚本
├── requirements.txt             # 依赖列表
├── README.md                    # 项目说明
├── QUICK_START.md              # 快速开始指南
├── USAGE.md                    # 详细使用文档
├── videos.txt.example          # 视频列表示例
│
├── src/                        # 源代码目录
│   ├── __init__.py
│   ├── cli.py                  # 命令行接口
│   │
│   ├── core/                   # 核心功能模块
│   │   ├── __init__.py
│   │   ├── video_analyzer.py  # 视频分析器（主类）
│   │   ├── scene_detector.py  # 场景检测 ✅
│   │   ├── audio_extractor.py # 音频提取 ✅
│   │   ├── transcriber.py     # 语音转文字 ✅
│   │   ├── subtitle_remover.py # 字幕去除 ✅
│   │   ├── video_downloader.py # 视频下载 ✅
│   │   │
│   │   # 新功能模块（已预留接口）
│   │   ├── subtitle_generator.py   # 字幕生成 🔜
│   │   ├── subtitle_translator.py  # 字幕翻译 🔜
│   │   ├── video_compressor.py     # 视频压缩 🔜
│   │   ├── format_converter.py     # 格式转换 🔜
│   │   ├── video_enhancer.py       # 视频增强 🔜
│   │   ├── audio_processor.py      # 音频处理 🔜
│   │   ├── content_analyzer.py     # 内容分析 🔜
│   │   └── smart_editor.py         # 智能剪辑 🔜
│   │
│   └── utils/                  # 工具函数
│       ├── __init__.py
│       ├── file_utils.py      # 文件处理工具 ✅
│       ├── batch_processor.py # 批量处理器 ✅
│       │
│       # 新工具模块（已预留接口）
│       ├── platform_adapter.py # 平台适配 🔜
│       ├── export_utils.py     # 导出工具 🔜
│       └── stats_generator.py  # 统计报告 🔜
│
├── config/                     # 配置文件
│   ├── __init__.py
│   └── settings.py            # 全局配置
│
├── tests/                      # 测试文件
│   ├── __init__.py
│   └── test_scene_detector.py
│
├── docs/                       # 文档
│   ├── ARCHITECTURE.md        # 架构文档（本文件）
│   └── API.md                 # API 文档
│
├── output/                     # 输出目录（自动生成）
│   └── video_name_timestamp/
│       ├── scenes/
│       ├── audio.mp3
│       ├── transcript.txt
│       ├── transcript_detailed.json
│       └── report.json
│
└── venv/                       # 虚拟环境（自动生成）
```

## 模块说明

### 核心模块 (src/core/)

#### VideoAnalyzer
- 主要的视频分析类
- 整合所有功能：场景检测、音频提取、语音转文字
- 管理输出目录和文件
- 生成分析报告

#### SceneDetector
- 负责视频场景检测
- 使用 PySceneDetect 库
- 支持自定义检测阈值
- 分割视频为独立场景文件

#### AudioExtractor
- 从视频中提取音频
- 使用 MoviePy 库
- 支持多种音频格式

#### Transcriber
- 语音转文字功能
- 使用 OpenAI Whisper 模型
- 支持多种语言和模型大小
- 生成带时间戳的文案

### 工具模块 (src/utils/)

#### BatchProcessor
- 批量处理多个视频
- 进度跟踪和错误处理
- 生成处理统计报告

#### file_utils
- 文件读写工具函数
- 目录管理
- 视频列表解析

### 配置模块 (config/)

#### settings.py
- 全局配置参数
- 默认值设置
- 可扩展的配置系统

## 数据流

```
输入视频
    ↓
VideoAnalyzer (主控制器)
    ↓
    ├─→ SceneDetector → 场景分割 → scenes/*.mp4
    ├─→ AudioExtractor → 音频提取 → audio.mp3
    └─→ Transcriber → 语音转文字 → transcript.txt + transcript_detailed.json
    ↓
生成报告 → report.json
```

## 扩展指南

### 添加新功能

1. **添加新的处理器**
   - 在 `src/core/` 创建新模块
   - 实现处理逻辑
   - 在 `VideoAnalyzer` 中集成

2. **添加新的工具函数**
   - 在 `src/utils/` 创建新模块
   - 实现工具函数
   - 在 `__init__.py` 中导出

3. **添加新的配置**
   - 在 `config/settings.py` 添加配置项
   - 在相关模块中使用配置

### 示例：添加视频下载功能

```python
# src/core/video_downloader.py
class VideoDownloader:
    def download(self, url, output_path):
        # 实现下载逻辑
        pass

# 在 VideoAnalyzer 中集成
from .video_downloader import VideoDownloader

class VideoAnalyzer:
    def download_video(self, url):
        downloader = VideoDownloader()
        return downloader.download(url, self.output_dir)
```

## 测试

运行测试：
```bash
python -m unittest discover tests
```

## 依赖管理

主要依赖：
- scenedetect: 场景检测
- opencv-python: 视频处理
- moviepy: 音频提取
- openai-whisper: 语音识别
- torch: Whisper 模型后端

## 性能优化建议

1. **批量处理**：使用 `--list` 参数批量处理多个视频
2. **模型选择**：根据需求选择合适的 Whisper 模型大小
3. **阈值调整**：调整场景检测阈值以平衡精度和性能
4. **并行处理**：未来可以添加多进程支持

## 未来扩展方向

### 已预留功能接口 ✅

所有 TODO 中的功能都已在 `VideoAnalyzer` 中预留了接口：

#### 字幕相关
- `generate_subtitles()` - 生成 SRT/ASS 字幕
- `translate_subtitles()` - 字幕翻译

#### 视频处理
- `compress_video()` - 视频压缩
- `convert_format()` - 格式转换
- `enhance_video()` - 视频增强（亮度/对比度/降噪/稳定）

#### 音频处理
- `process_audio()` - 音频处理（人声分离/降噪/标准化）

#### AI 分析
- `analyze_content()` - 内容分析（人脸/物体/OCR）

#### 智能编辑
- `smart_edit()` - 智能编辑（去静音/去重复/关键帧）

### 使用示例

```python
from src.core import VideoAnalyzer

analyzer = VideoAnalyzer("video.mp4")

# 现有功能
analyzer.remove_subtitles()
analyzer.analyze_scenes()
audio = analyzer.extract_audio()
transcript = analyzer.transcribe_audio(audio)

# 新功能（待实现）
analyzer.generate_subtitles(transcript["segments"], format="srt")
analyzer.compress_video(quality="high")
analyzer.enhance_video(auto=True)
analyzer.analyze_content(detect_faces=True, extract_text=True)
analyzer.smart_edit(remove_silence=True, extract_keyframes=True)
```

### 待实现功能清单

- [ ] Web UI 界面（Flask/FastAPI）
- [ ] 云存储集成
- [ ] 自动化工作流
- [ ] 视频对比功能
- [ ] 更多平台支持
