# 使用指南

## 快速开始

### 1. 分析单个视频（推荐）
一次性完成所有分析：分镜、音频、文案

```bash
./run.sh your_video.mp4
```

输出结构（每个视频独立文件夹）：
```
output/
└── your_video_20260406_143022/
    ├── scenes/              # 所有分镜视频
    │   ├── Scene-001.mp4
    │   ├── Scene-002.mp4
    │   └── ...
    ├── audio.mp3            # 音频文件
    ├── transcript.txt       # 完整文案
    ├── transcript_detailed.json  # 带时间戳的文案
    └── report.json          # 完整分析报告
```

### 2. 批量处理多个视频

#### 方式 A: 命令行直接指定
```bash
./run.sh video1.mp4 video2.mp4 video3.mp4
```

#### 方式 B: 使用视频列表文件（推荐）
1. 创建 `videos.txt` 文件：
```txt
video1.mp4
video2.mp4
video3.mp4
```

2. 运行批量处理：
```bash
./run.sh --list videos.txt
```

输出结构：
```
output/
├── video1_20260406_143022/
│   ├── scenes/
│   ├── audio.mp3
│   └── ...
├── video2_20260406_143045/
│   ├── scenes/
│   ├── audio.mp3
│   └── ...
└── video3_20260406_143108/
    ├── scenes/
    ├── audio.mp3
    └── ...
```

### 3. 只分割场景

```bash
./run.sh your_video.mp4 --scenes-only
```

### 4. 只提取音频和文案

```bash
./run.sh your_video.mp4 --audio-only
```

## 高级用法

### 批量处理 + 自定义参数

```bash
# 批量处理，使用更精确的语音识别
./run.sh --list videos.txt --whisper-model medium

# 批量处理，只提取音频和文案
./run.sh video1.mp4 video2.mp4 --audio-only

# 批量处理，调整场景检测灵敏度
./run.sh --list videos.txt -t 20
```

### 调整场景检测灵敏度

```bash
# 更敏感（分割更多场景）
./run.sh your_video.mp4 -t 15

# 不太敏感（只分割明显的场景变化）
./run.sh your_video.mp4 -t 35
```

### 使用更精确的语音识别模型

```bash
# 使用 small 模型（更准确）
./run.sh your_video.mp4 --whisper-model small

# 使用 medium 模型（很准确，但较慢）
./run.sh your_video.mp4 --whisper-model medium
```

模型对比：
- `tiny`: 最快，准确度约 80%
- `base`: 平衡，准确度约 85%（默认）
- `small`: 较准确，准确度约 90%
- `medium`: 很准确，准确度约 95%
- `large`: 最准确，准确度约 98%，但很慢

### 指定输出目录

```bash
./run.sh your_video.mp4 -o my_output
```

## 输出文件说明

每个视频都会创建独立的文件夹，文件夹名称格式：`视频名_时间戳`

### 1. 分镜视频 (`scenes/`)
每个场景的独立视频文件，按顺序编号：`Scene-001.mp4`, `Scene-002.mp4`...

### 2. 音频文件 (`audio.mp3`)
从视频中提取的完整音频

### 3. 完整文案 (`transcript.txt`)
纯文本格式的完整语音转录

### 4. 详细文案 (`transcript_detailed.json`)
JSON 格式，包含每句话的时间戳：
```json
[
  {
    "start": 0.0,
    "end": 3.5,
    "text": "大家好，欢迎来到我的频道"
  },
  {
    "start": 3.5,
    "end": 7.2,
    "text": "今天我们来聊聊..."
  }
]
```

### 5. 分析报告 (`report.json`)
完整的视频分析报告，包含：
- 视频信息
- 场景信息（时间、时长）
- 完整文案
- 带时间戳的文案片段

## 常见问题

### Q: 第一次运行很慢？
A: Whisper 模型首次使用时需要下载（约 150MB），之后会缓存到本地

### Q: 如何提高语音识别准确度？
A: 使用更大的模型，如 `--whisper-model medium`

### Q: 视频没有音频怎么办？
A: 工具会自动检测，如果没有音频会跳过音频处理步骤

### Q: 分镜太多或太少？
A: 调整 `-t` 参数，值越小分镜越多，值越大分镜越少

## 视频列表文件格式

创建 `videos.txt` 文件，每行一个视频路径（参考 `videos.txt.example`）：

```txt
# 这是注释，会被忽略
video1.mp4
video2.mp4
/path/to/video3.mp4
```

## 实际应用场景

1. **短视频创作**：快速提取分镜和文案，用于二次创作
2. **批量视频分析**：一次性处理多个视频，分析结构和内容
3. **字幕制作**：使用带时间戳的文案制作字幕
4. **内容审核**：快速了解视频内容
5. **学习笔记**：从教学视频中提取文字内容
6. **视频素材管理**：自动分类和整理视频片段
