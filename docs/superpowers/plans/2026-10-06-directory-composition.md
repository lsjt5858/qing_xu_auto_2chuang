# Directory Composition CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将多个素材目录按顺序组装成 MP4，通过 `run.sh compose` 使用；默认完整使用镜头，支持照片、配乐与可选剪映草稿，并删除重复的独立方案。

**Architecture:** 新命令将目录和选片规则转换成现有 `TimelineClip`，FFmpeg 导出模块按同一时间线渲染视频和音频。剪映复用仓库内 `export_to_jianying_draft`，使用相同标准化片段及最终音轨，避免预览和草稿各自编排。旧分析/镜头池流程保留；内部随机截取改为显式选择。

**Tech Stack:** Python / unittest / FFmpeg / FFprobe / 现有剪映模板，无新增第三方 Python 依赖。

---

用户已批准方案并要求执行；在当前工作区实施，不自动 commit，不重新请求审批。初始暂存仅 `.gitignore`；`design/` 和未跟踪产品提案不纳入提交。初始 104 个测试通过。原独立源码的暂存快照在已忽略的 `output/git_staging_review_20261006/staged_before.patch`。

## 对外行为

```bash
./run.sh compose --head-dir A --body-dir B --tail-dir C \
  --head-count 1 --body-count 3 --tail-count 1 \
  --seed 42 -o output/result.mp4

./run.sh compose --part A 1 --part B 3 --part C all \
  --seed 42 -o output/result.mp4 --execute
```

- 命名目录和 `--part DIR COUNT` 两种输入方式互斥；后者支持任意数量目录、严格保持参数顺序。
- 命名目录按 head/body/tail 排列，可省略任意段但至少提供一个目录；数量默认 1，`all` 表示全部。
- `--selection random|ordered` 默认 random；提供或自动生成并打印 `--seed`，同素材池和种子结果稳定。
- 目录递归扫描，忽略隐藏文件和隐藏子目录；素材不足、非目录、损坏素材明确失败。
- 视频默认 source_start=0、使用全长，总时长随所选素材累计，不套用原视频字幕槽。
- `--clip-start`（默认 0）和 `--clip-duration`（默认不限制）为显式裁剪；起点超过素材长度报错。
- 照片默认展示 2 秒，`--photo-duration` 可调，照片不应用视频裁剪起点。
- `--width/--height/--fps` 默认 1920/1080/30；正整数、画布宽高为偶数。
- `--bgm FILE` 使用本地配乐，循环补足总时长；`--bgm-volume` 默认 0.35，范围 0–1；默认保留素材原声，`--mute-source` 可关闭原声。
- 不加 `--execute` 只输出计划，不创建输出目录、不生成音视频、不写剪映目录、不保存本机剪映配置。
- execute 生成 MP4 和同名 JSON 清单；默认输出名带唯一标识，显式输出已存在时拒绝覆盖，输入素材不可被覆盖。
- `--export-jianying` 可同时生成草稿；复用 `--draft-root/--draft-name/--template-dir`，使用 basic 模板和唯一草稿目录。
- 成片和草稿复用标准化视频片段及最终完整混音；临时片段在草稿复制素材之后清理。
- 使用错误返回 2；执行/FFmpeg 失败返回 1；成功和 dry-run 返回 0。
- 旧 `--compose-with-pool` 仍按字幕槽裁剪，但默认从素材开头取；新增 `--pool-clip-start start|random`，只有显式 random 才随机选择内部起点。

## 文件边界

- `src/composition/directory_composer.py`：目录选片和完整镜头时间线，复用 `TimelineClip` / `probe_media`。
- `src/exporters/video.py`：标准化视频/照片，统一音频、拼接、BGM 混音；输出复用的标准化时间线与音轨。
- `src/commands/compose.py`、`src/commands/__init__.py`：compose 参数、dry-run、执行编排、清单。
- `src/cli.py` / `run.sh`：新子命令分发；旧参数、默认去字幕行为继续用于旧分析模式。
- `src/composition/head_tail_composer.py` / `src/utils/batch_processor.py` / `src/utils/jianying_draft_exporter.py`：显式旧模式截取策略。
- `README.md`：两种模式、完整镜头默认、命令示例、配乐/草稿/裁剪/错误行为。
- 删除 `compose_random_template.sh`、`create_jianying_montage.py`、`src/utils/random_template_composer.py`，旧两个测试文件迁移到对应模块测试。

## Task 1: 目录编排与截取策略

**Files:** 新建 `src/composition/directory_composer.py`、`tests/test_directory_composer.py`；修改旧 composer 及其测试。

接口按现有项目风格实现：

```python
@dataclass(frozen=True)
class DirectoryStage:
    directory: Path
    count: int | None = 1  # None means all
    role: str = "part"

def compose_directories(
    stages: list[DirectoryStage], *, seed: int,
    selection: str = "random", photo_duration: float = 2.0,
    clip_start: float = 0.0, clip_duration: float | None = None,
    probe=probe_media,
) -> list[TimelineClip]:
    ...
```

实现要点：先验证参数，按 stage 顺序扫描；ordered 取排序前 N，random 用局部 `random.Random(seed).sample`；选中视频的开始默认 0，默认时长为 metadata.duration_us，显式裁剪才改变；累加 `timeline_start_us`，图片使用 photo_duration。

- [x] 先写测试：A/B/C 顺序、完整时长与零偏移、固定种子、不重复抽取、all、递归/隐藏项、素材不足、明确裁剪、照片时长、非法数值。
- [x] 运行 `venv/bin/python -m unittest discover -s tests -p test_directory_composer.py -v`，确认新能力缺失造成失败。
- [x] 实现上述接口，使测试通过。
- [x] 为 `HeadTailComposer` 增加默认零起点和显式随机起点测试，再添加设置 `pool_clip_start="start"`，通过 CLI 和旧独立导出器传递。

## Task 2: 统一渲染、CLI 与草稿复用

**Files:** 新建 `src/exporters/video.py`、`src/commands/compose.py` 与对应测试；修改 `src/cli.py`、`run.sh`。

渲染接口：

```python
@dataclass(frozen=True)
class RenderedTimeline:
    video_path: Path
    clips: tuple[TimelineClip, ...]
    audio_path: Path

def render_timeline(
    clips: list[TimelineClip], output_path: Path, *, work_dir: Path,
    width: int = 1920, height: int = 1080, fps: int = 30,
    bgm_path: Path | None = None, bgm_volume: float = 0.35,
    mute_source: bool = False,
) -> RenderedTimeline:
    ...
```

`work_dir` 由命令持有到草稿导出结束。渲染器将片段转为统一画布/帧率和音频格式；SAR 在缩放前转为方形像素，不拉伸画面；concat 清单只写生成的安全相对文件名，兼容中文、空格、单引号目录。无音轨补静音，短音轨补足，BGM 循环并混入。最终音轨供草稿直接复用；标准化片段按实际输出视频时长建立连续 TimelineClip，照片也作为视频片段复制进草稿。

新命令分发：

```python
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "compose":
        from .commands.compose import main as compose_main
        return compose_main(argv[1:])
    # existing parser and processing continue unchanged
```

run.sh 对首参数 compose 直接透传，不自动加去字幕；其他用法保留原执行行为。

- [x] 先写渲染测试：无音轨、图片、混音、非方形像素、非零显式起点、特殊路径、已有输出保护。
- [x] 运行目标测试，确认失败，然后实现渲染器。
- [x] 先写 CLI 测试：外部 cwd 下 help、命名段与重复 part、dry-run 无副作用、参数互斥/错误、稳定种子、旧入口兼容。
- [x] 运行 CLI 测试确认失败；实现 parser 和执行编排，错误分类与帮助文字。
- [x] 用最终混音构造 `AnalysisArtifacts`（无字幕），调用现有 `export_to_jianying_draft(..., style_template="basic")`；复制之后再关闭临时目录。
- [x] 同一个种子下 dry-run 和 execute 采用同一选片/计划接口；清单记录 seed、输入目录/数量、源路径、起点、源时长、目标时间、输出参数和实际草稿路径。
- [x] 验证默认输出唯一、显式路径不覆盖，草稿复用现有唯一目录策略。

## Task 3: 清理、文档与回归

**Files:** 删除旧独立方案及旧测试；更新 `README.md`，测试报告放 ignored `output/cli_directory_composition/`。

- [x] 将旧两个测试覆盖的有效行为迁入新测试，然后删除独立脚本和旧测试；通过 `rg` 检查运行时代码无旧路径引用。
- [x] 更新 README，给出 A/B/C、任意目录段、dry-run/execute、配乐、可选草稿和显式裁剪示例。
- [x] 全量回归：`venv/bin/python -m unittest discover -s tests -q`。
- [x] 用 FFmpeg 在 ignored output 中生成几秒钟的红/绿/蓝视频（含有声、无声、不同尺寸/帧率）和照片、短配乐，执行真实 CLI。
- [x] 检查成片可完整解码、分段画面顺序/显示比例、总时长、音轨，以及短 BGM 覆盖全片；检查草稿中片段数量、时间线、完整音轨和持久化素材路径。
- [x] 测试特殊字符路径、重复执行拒绝覆盖且旧成片/草稿不受损，输入素材哈希不变。
- [ ] 先做方案符合性检查，再做代码质量检查；修复实际发现的问题并重跑相关验证。
- [ ] `git diff --check`、最终状态核验；代码准备好供用户审阅，不 commit，不暂存图片/设计产物。
