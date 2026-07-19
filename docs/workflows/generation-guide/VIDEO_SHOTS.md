<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# 视频细分镜与逐镜头生成

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.0.0`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. 视频细分镜与生成指令 (`video.fine_storyboard.generate`)

**做什么：** 在母版、粗分镜、风格和已批准图片资产齐备后生成6至30秒逐shot合同。

**逻辑模型能力：** `text.structured.creative_video`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 期望镜头数 (`fine_preferred_shot_count`) | 教师填写 | 否 | 按字段合同填写 |
| 细分镜补充要求 (`fine_storyboard_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 批准母版剧本 (`fine_master_script_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 批准粗分镜 (`fine_rough_storyboard_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 批准视频风格 (`fine_video_style_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 已批准图片资产 (`fine_approved_assets_ref`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `intro_selection.snapshot` | 是 | 完整快照 |
| `video.master_script.approved_version` | 是 | 完整快照 |
| `video.rough_storyboard.approved_version` | 是 | 完整快照 |
| `video.style.approved_version` | 是 | 完整快照 |
| `video.assets.approved_versions` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是创意短片细分镜导演，负责把已批准节拍和图片资产变成6至30秒逐shot生产合同。

**任务（教师可修改）**

> 在母版剧本、粗分镜、视频风格和已批准图片资产全部齐备后，生成逐shot细分镜。每个shot只有一个主要可见节拍、一个明确终点和一次主要运镜，并输出可直接提交视频模型的完整提示词。

**方法（平台固定）**

> 每个shot必须可追溯已选课程驱动方案、来源scene和beat。按故事节拍和逻辑Provider能力为每个shot选择6至30秒的精确时长，使全部shot总和等于已确认母版目标时长。写明开始/结束状态、景别、角度、起止构图、一次主要运镜、主体动作时间顺序、旁白/对白/声音占位和连续性锁定。每张已批准垫图按连续image_index登记语义名、版本和用途，提示词中的垫图标记与结构一一对应。最后一个shot才到达课堂交接。

**质量门禁（平台固定）**

> shot顺序连续，每个时长为6至30秒且总和精确；每个shot单节拍单运镜；所有资产版本已批准且引用存在；人物、道具、光线、天气和动作状态无解释跳变；不把旁白字幕交给视频画面生成；结尾不越过handoff_moment、不解释must_not_preteach。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 细分镜键 (`fine_storyboard_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源母版剧本键 (`fine_source_master_script_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 目标总时长 (`fine_target_duration_seconds`) | `number` | 是 | 否 | 按结构化合同生成 |
| 逐镜头合同 (`fine_shots`) | `repeatable` | 是 | 是 | 子字段：镜头键、来源场次键、来源节拍键、顺序、时长（6至30秒）、唯一可见节拍、开始状态、结束状态、景别角度与唯一运镜、动作时间顺序、垫图使用、完整视频提示词、负面约束、旁白占位、对白占位、声音意图、连续性锁定 |
| 细分镜质量 (`fine_storyboard_quality`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.video_fine_storyboard.v1`
- 教师可见：是

```markdown
# 视频细分镜与生成指令

目标时长：{{fine_target_duration_seconds}}秒

{{fine_shots}}

## 质量检查
{{fine_storyboard_quality}}
```

## 2. 逐镜头候选视频生成 (`video.shots.generate`)

**做什么：** 按细分镜逐shot生成候选视频，候选通过校验、采用并保存后才形成正式clip。

**逻辑模型能力：** `video.image_to_video.6s_30s`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 候选数量 (`shot_candidate_count`) | 教师填写 | 是 | 默认：2 |
| 逻辑质量档位 (`shot_generation_quality`) | 教师填写 | 是 | 默认：均衡 (`balanced`)；可选：快速、均衡、高质量 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 细分镜shot (`shot_spec_ref`) | 系统设置 | 是 | 按字段合同填写 |
| 关键帧与连续性参考 (`shot_reference_assets`) | 系统设置 | 是 | 按字段合同填写 |
| 视频风格合同 (`shot_style_contract_ref`) | 系统设置 | 是 | 按字段合同填写 |

- 无上游业务 Context；生成所需任务包或参考资产由系统字段带入。

### 实际提示词

**角色（平台固定）**

> 你是服务端逐shot视频生成执行器。

**任务（教师可修改）**

> 严格按一个已冻结shot合同生成指定数量候选，按image_index顺序传入shot_keyframe和continuity_reference，不改写故事、时长、动作或固定槽位。

**方法（平台固定）**

> 通过模型网关选择满足video.image_to_video.6s_30s能力的路由；只传节点允许的参考资产与业务提示词。记录候选键、实际时长、分辨率、帧率、媒体类型、SHA-256和质量标记。候选阶段不创建clip_id；只有校验通过、被采用并原子保存到shot槽位后才形成正式clip。

**质量门禁（平台固定）**

> 输出可播放且时长匹配6至30秒shot合同；首尾状态、主体身份、资产、动作、光线和镜头连续；无文字字幕水印Logo和儿童安全问题；失败只影响当前shot；Provider私有参数和临时URL不进入业务产物。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 生成请求键 (`shot_generation_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 镜头键 (`generated_shot_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 镜头目标槽位 (`generated_shot_target_slot`) | `text` | 是 | 否 | 按结构化合同生成 |
| 镜头候选 (`shot_candidates`) | `repeatable` | 是 | 否 | 子字段：候选键、实际时长、宽度、高度、帧率、媒体类型、文件摘要、质量标记 |

### 教师可读投影模板

- 渲染器：`shanhai.video_clip_candidates.markdown.v1`
- 教师可见：是

```markdown
# {{generated_shot_key}} 候选视频

目标槽位：{{generated_shot_target_slot}}

{{shot_candidates}}
```
