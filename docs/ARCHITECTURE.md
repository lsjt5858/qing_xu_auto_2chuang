# 项目架构文档

## 项目结构

```
video-analyzer/
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
│   │   ├── scene_detector.py  # 场景检测
│   │   ├── audio_extractor.py # 音频提取
│   │   └── transcriber.py     # 语音转文字
│   │
│   └── utils/                  # 工具函数
│       ├── __init__.py
│       ├── file_utils.py      # 文件处理工具
│       └── batch_processor.py # 批量处理器
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

- [ ] 视频下载功能（支持抖音、YouTube 等）
- [ ] 字幕生成和嵌入
- [ ] 视频摘要和关键帧提取
- [ ] Web UI 界面
- [ ] 云端处理支持
- [ ] 多语言支持
- [ ] 视频质量分析
- [ ] 自动标签和分类
