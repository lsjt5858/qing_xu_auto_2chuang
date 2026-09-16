# 镜流工坊

原名：`柴视频`。这是一个面向短视频二创的本地处理流水线，用来把原始视频整理成可复用素材，并直接生成剪映草稿。

它现在能做的事情很明确：

- 清洗源视频：去底部烧录字幕、去固定半透明水印
- 拆分镜头：把视频切成 `Scene-001 / Scene-002 / ...`
- 提取音频与文案：输出 `audio.mp3`、完整文案、带时间戳文案
- 组合混剪：保留原视频头部，再按字幕节奏从视频池补尾
- 导出剪映草稿：直接写入剪映草稿箱，可继续在剪映里调整和导出

当前仓库目录仍然是 `chai_shi_pin`，这里只先完成文档层的命名调整，避免影响现有脚本和环境。

## 适合什么场景

这套工具适合这种工作流：

1. 从抖音/快手/小红书保存原视频到本地
2. 批量清洗并拆分镜头
3. 收集可复用的“视频头 / 视频身”镜头池
4. 用某条文案和音频为基准，自动组合一版混剪时间线
5. 直接进剪映草稿箱继续精修

## 核心流程

```text
原始视频
  -> 去字幕 / 去水印
  -> 分镜拆分
  -> 提取音频 / 转录文案
  -> 保留视频头 + 视频池补尾
  -> 导出剪映草稿
```

## 安装

```bash
git clone https://github.com/lsjt5858/chai_shi_pin.git
cd chai_shi_pin

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
brew install ffmpeg
```

## 两个入口

你只需要记住两个入口：

1. `./run.sh ...`
   从原始视频开始跑完整流程
2. `python3 src/utils/jianying_draft_exporter.py ...`
   从已经生成好的 `output/` 目录直接导出剪映草稿

`run.sh` 默认会自动带上 `--remove-subtitles`。

## 常用命令

### 1. 单个视频分析

```bash
./run.sh "/path/to/video.mp4"
```

输出目录类似：

```text
output/视频名_时间戳/
```

### 2. 批量处理整个目录

```bash
./run.sh "/path/to/video_dir"
```

重复运行时，如果 `output/<视频名>_时间戳/video_no_subtitles.mp4`
已经存在，该源视频会被直接跳过，不再创建新目录或执行后续处理。

### 3. 批量处理多个文件

```bash
./run.sh "/path/to/a.mp4" "/path/to/b.mp4" "/path/to/c.mp4"
```

### 4. 只做部分步骤

```bash
./run.sh "/path/to/video.mp4" --remove-subtitles-only
./run.sh "/path/to/video.mp4" --scenes-only
./run.sh "/path/to/video.mp4" --audio-only
```

### 5. 生成 AI 剧情语义分镜（同时保留原始切镜）

默认配置支持智谱和火山方舟。真实 API Key 不写入配置文件，只在运行时通过环境变量传入。

使用智谱：

```bash
ZAI_API_KEY="你的智谱 API Key" \
  ./run.sh "/path/to/video.mp4" --semantic-scenes
```

使用火山方舟，其中 `ARK_MODEL` 是视觉模型名或推理接入点 ID：

```bash
SEMANTIC_SCENE_PROVIDER="volcengine" \
ARK_API_KEY="你的火山方舟 API Key" \
ARK_MODEL="ep-xxxxxxxx" \
  ./run.sh "/path/to/video.mp4" --semantic-scenes
```

未指定 `SEMANTIC_SCENE_PROVIDER` 时，脚本会优先选择当前环境中已设置 API Key
的厂商；都未设置时使用 `default_provider`（默认 `zhipu`）。同时配置多个 Key
时，可将 `SEMANTIC_SCENE_PROVIDER` 设置为 `zhipu` 或 `volcengine`。

处理逻辑：

- `scenes/` 保留按画面切换检测到的原始切镜
- AI 综合每个切镜的代表帧、时间范围和对应台词
- 同一人物、地点、事件、动作目标或表达目的连续时，即使发生正反打、景别或机位变化，也会聚合成同一个剧情语义分镜
- `semantic_scenes/` 输出最终聚合视频，`semantic_scenes.json` 保存分组依据与原始切镜映射
- 输入源视频或源视频目录时，只要已有 `video_no_subtitles.mp4`，即使指定
  `--semantic-scenes` 也会跳过该视频的全部处理
- 如需对已有结果补做 AI 聚合，请直接输入对应的结果目录：
  `./run.sh "output/视频名_时间戳" --semantic-scenes`

模型地址、模型名、超时和环境变量名统一配置在：

```text
config/semantic_scenes.json
```

### 6. 分析完直接导入剪映

```bash
./run.sh "/path/to/video.mp4" --export-jianying
```

默认会套用 `emotion` 模版，也就是“情绪类视频模版”：

- 以 `output/transcript_detailed.json` 的中文分段为准，统一生成一条字幕轨
- 双语时会把英文折叠到同一条文本轨里，按“中文在上、英文在下”的样式输出
- 字号、描边、位置沿用参考草稿 `0406-03` 的情绪类风格

### 7. 用视频池自动组合后导入剪映

```bash
./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool"
```

当前组合逻辑是：

- 总时长以 `audio.mp3` 为准
- 默认保留原视频第一个分镜作为视频头
- 后半段按字幕时间段，从视频池选择时长最接近的镜头
- 选片会优先避开刚用过的素材组和素材集合，提升画面多样性
- 视频池目录会递归扫描子目录
- 导出结果是剪映草稿，不是直接渲染好的最终 mp4

### 8. 指定视频头规则

固定保留前 3 秒：

```bash
./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool" \
  --head-mode fixed-seconds \
  --head-duration 3
```

不保留原视频头部：

```bash
./run.sh "/path/to/video.mp4" \
  --compose-with-pool "/path/to/shot_pool" \
  --head-mode none
```

### 9. 已有 output 目录，直接导出剪映

```bash
python3 src/utils/jianying_draft_exporter.py \
  "output/某个分析结果目录"
```

### 10. 已有 output 目录，直接组合并导出剪映

```bash
python3 src/utils/jianying_draft_exporter.py \
  "output/某个分析结果目录" \
  --compose-with-pool "/path/to/shot_pool"
```

### 11. 收集分镜素材

```bash
./collect_scenes.sh
```

这个脚本会把分镜整理出来，方便你做“视频头 / 视频身”镜头池。

## 常用参数

| 参数                      | 说明                                     |
| ----------------------- | -------------------------------------- |
| `-o, --output`          | 输出根目录，默认 `output`                      |
| `-t, --threshold`       | 分镜阈值，越小切得越碎                            |
| `--whisper-model`       | `tiny / base / small / medium / large` |
| `--subtitle-bar-height` | 手动指定底部字幕区域高度                           |
| `--semantic-scenes`     | 调用视觉模型生成剧情语义分镜，同时保留原始切镜                  |
| `--semantic-scenes-config` | 语义分镜模型配置文件，默认 `config/semantic_scenes.json` |
| `--export-jianying`     | 分析完成后直接导出剪映草稿                          |
| `--compose-with-pool`   | 使用视频池自动补尾并导出剪映                         |
| `--head-mode`           | `first-scene / fixed-seconds / none`   |
| `--head-duration`       | `fixed-seconds` 模式下保留的秒数               |
| `--style-template`      | `emotion / basic`，默认 `emotion`         |
| `--draft-name`          | 导出的剪映草稿名                               |
| `--draft-root`          | 剪映草稿箱目录，默认使用本机目录                       |

## 输出结构

```text
output/{视频名}_{时间戳}/
├── video_no_subtitles.mp4
├── scenes/
│   ├── Scene-001.mp4
│   ├── Scene-002.mp4
│   └── ...
├── semantic_scenes/             # 启用 --semantic-scenes 时生成
│   ├── SemanticScene-001.mp4
│   └── ...
├── semantic_scene_contact_sheet.jpg
├── semantic_scenes.json
├── audio.mp3
├── transcript.txt
├── transcript_detailed.json
├── report.json
└── composition_plan.json      # 仅在组合模式下生成
```

字段职责：

- `video_no_subtitles.mp4`：清洗后的源视频
- `scenes/`：按画面切换拆出的原始切镜素材
- `semantic_scenes/`：按剧情语义聚合后的分镜视频
- `semantic_scene_contact_sheet.jpg`：提交给视觉模型的切镜代表帧联系表
- `semantic_scenes.json`：语义分镜时间范围、分组理由及原始切镜映射
- `audio.mp3`：音频基准
- `transcript_detailed.json`：字幕时序基准
- `report.json`：整个输出目录的总报告
- `composition_plan.json`：组合模式下的镜头时间线计划

## 剪映导出说明

导出后的草稿会写入剪映草稿箱目录，并自动登记到草稿索引里。\
如果剪映正在运行，建议导入后完全退出再重新打开一次。

模板已经内置在当前项目中：

```text
templates/jianying/
```

不再依赖外部 `CapCutAPI` 项目。

## 项目结构

```text
main.py
run.sh
collect_scenes.sh
templates/
└── jianying/                  # 剪映草稿模板
src/
├── cli.py                     # CLI 入口与参数解析
├── composition/
│   ├── shot_pool.py           # 视频池扫描与选片
│   └── head_tail_composer.py  # 保留视频头 + 补尾组合
├── core/
│   ├── video_analyzer.py      # 主流程编排
│   ├── subtitle_remover.py    # 去字幕 / 去水印
│   ├── scene_detector.py      # 分镜检测与分割
│   ├── audio_extractor.py     # 音频提取
│   ├── transcriber.py         # Whisper 转录
│   └── video_downloader.py    # 下载入口
├── exporters/
│   └── jianying.py            # 剪映草稿导出
├── models/
│   └── artifacts.py           # output 目录产物模型
└── utils/
    ├── batch_processor.py
    ├── file_utils.py
    └── jianying_draft_exporter.py
tests/
├── test_analysis_artifacts.py
├── test_head_tail_composer.py
├── test_jianying_exporter_defaults.py
├── test_lazy_package_imports.py
└── test_root_meta_update.py
```

## 设计约束

这套工程现在的边界是：

- `output/` 目录是统一产物契约
- 组合逻辑只消费产物，不直接依赖前面流程内部细节
- 剪映导出器只负责把时间线和素材写成草稿
- 包级导入保持惰性，避免轻量脚本被重依赖拖死

## Feature Flag

项目现在提供统一的 feature flag 模块，后续新功能可以通过它做灰度或开关控制：

```python
from config.feature_flags import feature_flags

feature_flags.register(
    "my_new_feature",
    default=False,
    description="Example feature switch.",
)

if feature_flags.is_enabled("my_new_feature"):
    ...
```

也可以通过环境变量覆盖，例如：

```bash
export CHAI_FLAG_MY_NEW_FEATURE=true
```

## 测试

跑全部测试：

```bash
python3 -m unittest discover tests
```

## 已知限制

- 当前输出的是剪映草稿，不是直接渲染成最终视频文件
- 视频池目前按时长优先匹配，还没有做更复杂的画幅/内容语义筛选
- 如果路径里有空格，请用双引号包住完整路径

## 后续建议

接下来最值得继续做的事：

1. 视频池增加画幅过滤、重复素材抑制、最小时长过滤
2. 剪映字幕样式做成可配置
3. 增加“直接渲染成 mp4”的离线导出链路
