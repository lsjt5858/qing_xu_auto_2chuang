# 完整剧本与万物生交接模板

创作或改写完整剧本时读取。交给 `wanwusheng-ai-film-director` 时必须填写末尾的 `WANWUSHENG_HANDOFF_V1`，不得让交接包新增剧本中没有的事实。

## 目录

1. 创作判断
2. 故事卡
3. 人物表
4. 七步证据链
5. 分时节拍
6. 完整可拍剧本
7. 自媒体包装
8. 立项与风险
9. WANWUSHENG_HANDOFF_V1
10. 交接一致性检查

## 1. 创作判断

```text
【输入类型】故事种子 / 真实改编 / 网友故事 / 现实议题虚构 / 现有剧本改稿 / 爆款机制二创
【来源状态】REAL_VERIFIED / REAL_CLAIMED_UNVERIFIED / NETIZEN_STORY_UNVERIFIED / REALITY_INSPIRED / FICTION_EXPLICIT / FICTION_LIKELY / TUTORIAL_EXAMPLE
【平台与时长】
【目标受众】
【必须保留】
【允许改动】
【禁止使用】
【合理假设】
```

## 2. 故事卡

```text
【暂定片名】
【一句话故事】主角 + 当下困境 + 发现 + 高成本选择
【核心命题】一条可由行动证明的判断
【共同经验】观众会在哪个具体生活经验中看见自己
【主发动机】
【只复用的机制】
【重做后的因果链】
【开场观众问题】
【结尾回答】
```

## 3. 人物表

| ID | 人物 | 年龄/阶段 | 与主角关系 | 表层目标 | 深层需要 | 防御方式 | 真相后选择 | 不得漂移 |
|---|---|---|---|---|---|---|---|---|
| C01 |  |  |  |  |  |  |  |  |

年龄、职业、伤病、家庭关系和年代不确定时标记 `待核验`，不要猜成事实。

## 4. 七步证据链

| 步骤 | 剧情信息 | 可见/可听证据 | 来源类型 | 重解释哪个前文细节 |
|---|---|---|---|---|
| 表层事实 |  |  |  |  |
| 表层判断 |  |  |  |  |
| 第一异常 |  |  |  |  |
| 第二异常 |  |  |  |  |
| 核心证据 |  |  |  |  |
| 真相重构 |  |  |  |  |
| 当下行动 |  |  |  |  |

## 5. 分时节拍

| Beat | 时间 | 压/扬/爆/收 | 事件 | 观众新知道什么 | 人物选择 | 核心物件状态 | 版本标记 |
|---|---:|---|---|---|---|---|---|
| B01 | 0-3s | 压 |  |  |  |  | 核心保留 |

版本标记只用：`核心保留`、`可压缩`、`扩展版专用`。

## 6. 完整可拍剧本

```text
SC01  内/外·地点·时间
预计时长：__ 秒
出场：C01、C02
本场功能：只写一个主要情绪/叙事任务
画面与动作：只写可见、可执行行为；包含入场状态和结束状态
对白：
C01：（动作/停顿）“……”
旁白：仅在画面无法表达时使用
环境声：
动作声：
音乐/静音：注明进入、撤出和无旁白停顿
道具状态：P01 由谁持有、完好/打开/损坏、画面位置
关键文字：内容或“后期合成”；无则写无
版本标记：核心保留 / 可压缩 / 扩展版专用
```

每场必须以一个可剪辑状态结束。不要在一个场中安排多个复杂地点跳转或多阶段动作。

## 7. 自媒体包装

```text
【结果前置钩子】画面/声音；承诺的问题
【强情绪画面钩子】画面/声音；承诺的问题
【扎心反问钩子】文案；承诺的问题
【标题候选】3-5 条
【封面短句】6-12 字
【发布文案】不泄露核心真相
【互动问题】与主题有关，不索取创伤隐私
```

## 8. 立项与风险

```text
【评分】总分 / 100；列出十个分项
【硬否决】无 / 有：____
【生产难度】S / A / B / C；依据
【事实待核验】
【隐私/授权】
【医疗/法律】
【相似度风险】
【最小修订】
```

## 9. WANWUSHENG_HANDOFF_V1

把以下 YAML 作为独立代码块输出。值不确定时用 `null` 或 `待核验`，不要补写。

```yaml
handoff_version: WANWUSHENG_HANDOFF_V1
source_skill: write-emotional-microdrama
target_skill: wanwusheng-ai-film-director
script:
  title: ""
  version: "v1.0"
  status: "draft|locked"
  source_status: ""
  premise: ""
  core_theme: ""
production_brief:
  platform: ""
  master_duration_seconds: 0
  delivery_versions_seconds: []
  aspect_ratio: null
  visual_tone: ""
  dialogue_sync_strategy: "director_decides|visible-dialogue|voiceover|mixed"
  pov_rule: "none|first-person|mixed"
locked_facts:
  source_facts: []
  user_locked: []
  fictionalized: []
  production_inferences: []
  pending_verification: []
characters:
  - id: C01
    name: ""
    age_stage: ""
    relationship: ""
    identity_anchors: []
    wardrobe_states: []
    performance_rule: ""
props:
  - id: P01
    name: ""
    story_function: ""
    state_timeline: []
locations:
  - id: E01
    name: ""
    time_weather: ""
    layout_anchors: []
scenes:
  - id: SC01
    duration_seconds: 0
    location_id: E01
    characters: [C01]
    story_function: ""
    visible_action: ""
    start_state: ""
    end_state: ""
    prop_states: []
    dialogue: []
    voiceover: []
    sound_cues: []
    critical_text: []
    version_tag: "核心保留|可压缩|扩展版专用"
emotion_design:
  opening_question: ""
  first_15s_information_gap: ""
  reveal: ""
  post_reveal_action: ""
  ending_aftertaste: ""
sound_handoff:
  opening_identifier: ""
  recurring_prop_sound: ""
  pre_reveal_silence: ""
  choice_confirming_sound: ""
  ending_ambience: ""
critical_readable_text:
  post_composite_only: []
do_not_change: []
director_may_design:
  - "镜头景别与运镜"
  - "灯光、色卡与美术细节"
  - "在不改变因果链前提下的场内调度"
production_risks: []
next_step: "请先执行连续性审计，再做场次与镜头规划；不要直接跳到视频提示词。"
```

## 10. 交接一致性检查

- 人物 ID、关系、年龄和场景与最终剧本一致。
- 道具状态时间线没有跳变。
- 每场开始/结束状态可供导演继续拆镜。
- `do_not_change` 只放故事事实和关键表达，不限制导演正常设计。
- 关键文字全部列入 `post_composite_only`。
- 声音分为环境声、动作声、对白、旁白、音乐和静音，不混写。
- 交接包没有擅自增加病历、日期、地点、品牌或授权状态。
- 用户未提供的画幅和同步方案没有被静默锁定；候选值位于 `production_inferences`。
- 剧本未锁定时使用 `draft`；评分通过并获用户接受后才使用 `locked`。
