<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# 音频、TTS 与课堂质量验收

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.3.0`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. 配音音效音乐计划 (`audio.plan.generate`)

**做什么：** 在正式clips选定后规划旁白、对白、音效、音乐和字幕，绑定shot或明确时间线区间。

**逻辑模型能力：** `text.structured.audio_plan`  **视觉预设：** 无固定视觉预设

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 旁白风格 (`audio_voice_style`) | 教师填写 | 是 | 默认：亲切、清晰、自然，不幼稚化 |
| 语速 (`audio_speech_rate`) | 教师填写 | 是 | 默认：0.95 |
| 音乐偏好 (`audio_music_preference`) | 教师填写 | 否 | 按字段合同填写 |
| 音频补充要求 (`audio_plan_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 批准母版剧本 (`audio_master_script_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 正式视频片段 (`approved_video_clips_ref`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `intro_selection.snapshot` | 是 | 完整快照 |
| `video.master_script.approved_version` | 是 | 完整快照 |
| `video.clips.approved_versions` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是儿童友好课堂短片的音频与字幕导演。

**任务（教师可修改）**

> 在正式clips已经选定后，依据已选方案和批准母版剧本规划旁白、对白、音效、音乐和字幕。每项绑定shot或明确时间线区间，并为后续TTS和FFmpeg合成提供固定目标槽位。

**方法（平台固定）**

> 以母版剧本旁白对白为事实源，不临时改写故事或课程交接。检查每段文本按设定语速能在clip时长内读完；数学读法和单位准确；字幕停留时间可读。音乐和音效服务动作，不遮盖旁白；使用ducking规则控制音量。图片/视频模型产生的原始声音不承担准确对白。

**质量门禁（平台固定）**

> 所有正式clip均在时间线中覆盖；旁白、字幕、音效与动作对齐；文本不越过handoff_moment、不解释must_not_preteach；语速、时长、音量和字幕可读性合法；不包含TTS Provider、密钥、私有参数或实际文件路径。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 音频计划键 (`audio_plan_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源母版剧本键 (`audio_source_master_script_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 音频轨道项 (`audio_tracks`) | `repeatable` | 是 | 是 | 子字段：音频键、类型、关联shot、时间线区间、文本或声音说明、声音档案、语速、预计时长、音量意图、避让规则、字幕文本、目标槽位 |
| 混音与字幕计划 (`audio_mix_plan`) | `timeline` | 是 | 是 | 按结构化合同生成 |
| 音频计划质量 (`audio_plan_quality`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.audio_plan.markdown.v1`
- 教师可见：是

```markdown
# 视频配音、音效、音乐与字幕计划

{{audio_tracks}}

## 混音与字幕时间线
{{audio_mix_plan}}

## 质量检查
{{audio_plan_quality}}
```

## 2. TTS配音生成 (`audio.tts.generate`)

**做什么：** 为后续音频Provider保留的执行合同：逐条执行旁白或对白计划并产生可审计音轨候选；当前阶段不实现适配器或真实冒烟。

**逻辑模型能力：** `audio.tts.child_friendly_zh`  **视觉预设：** 无固定视觉预设

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 候选数量 (`tts_candidate_count`) | 教师填写 | 是 | 默认：1 |
| 逻辑质量档位 (`tts_generation_quality`) | 教师填写 | 是 | 默认：均衡 (`balanced`)；可选：快速、均衡、高质量 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| TTS计划项 (`tts_audio_plan_item_ref`) | 系统设置 | 是 | 按字段合同填写 |
| 声音参考 (`tts_voice_reference`) | 系统设置 | 否 | 按字段合同填写 |

- 无上游业务 Context；生成所需任务包或参考资产由系统字段带入。

### 实际提示词

**角色（平台固定）**

> 你是服务端儿童友好中文TTS执行器。

**任务（教师可修改）**

> 严格执行一个已冻结的旁白或对白计划项，保持文本、声音档案、语速、时长意图和目标槽位，返回音频候选文件事实。

**方法（平台固定）**

> 通过模型网关选择满足audio.tts.child_friendly_zh能力的路由；可选voice_reference只按节点声明传入。记录候选键、实际时长、采样率、声道、媒体类型和SHA-256。Provider名称、密钥和私有参数不写入业务结果。

**质量门禁（平台固定）**

> 语音清晰自然、发音和数学读法准确、时长适配计划、无爆音截断或危险内容；失败不冒充候选；候选采用和保存到项目音轨槽位保持独立。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| TTS请求键 (`tts_generation_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 音频计划键 (`tts_audio_track_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 目标槽位 (`tts_target_slot`) | `text` | 是 | 否 | 按结构化合同生成 |
| 配音候选 (`tts_candidates`) | `repeatable` | 是 | 否 | 子字段：候选键、实际时长、采样率、声道数、媒体类型、文件摘要、质量标记 |

### 教师可读投影模板

- 渲染器：`shanhai.audio_candidates.markdown.v1`
- 教师可见：是

```markdown
# TTS配音候选

目标槽位：{{tts_target_slot}}

{{tts_candidates}}
```

## 3. 视频课堂质量评估 (`video.classroom_quality.evaluate`)

**做什么：** 以最终视频和已选导入快照评估课程驱动创意、交接、不得提前讲授、连续性和课堂可用性。

**逻辑模型能力：** `vision.evaluate.classroom_video`  **视觉预设：** 无固定视觉预设

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 评估补充要求 (`quality_evaluation_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 最终视频 (`final_video_asset`) | 系统设置 | 是 | 按字段合同填写 |
| 通过阈值 (`classroom_quality_threshold`) | 系统设置 | 是 | 默认：80 |
| 已选导入方案 (`quality_selected_intro_ref`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `intro_selection.snapshot` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是课堂导入视频质量评估员，按已选导入方案快照检查最终视频。

**任务（教师可修改）**

> 观看最终视频并评估课程驱动创意是否完整、是否准确继承钩子和课程关联、是否在唯一handoff_moment交接、是否没有提前讲授、视觉动作是否连续、是否适合真实课堂。所有问题给出时间区间和受影响shot。

**方法（平台固定）**

> 以intro_selection.snapshot为唯一课程语义基准，不读取教案、教材或PPT。逐段比较creative_concept、hook、course_anchor、classroom_first_question、handoff_moment和must_not_preteach；同时检查画面可读性、节奏、儿童安全、连续性、字幕音频同步和课堂暂停点。分项评分并按阈值给出通过结论。

**质量门禁（平台固定）**

> 不得因个人审美改写上游创意；所有失败有可定位证据；任何提前讲授、越过交接、严重安全问题或不可播放都必须阻塞通过；发现只指向受影响shot，不要求无关镜头重做；报告不包含Provider、密钥或原始敏感模型响应。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 质量报告键 (`classroom_quality_report_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源视频版本 (`quality_source_video_ref`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 已选方案键 (`quality_intro_option_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 课程驱动创意完整度 (`course_grounded_creative_score`) | `number` | 是 | 否 | 按结构化合同生成 |
| 课堂交接准确度 (`handoff_accuracy_score`) | `number` | 是 | 否 | 按结构化合同生成 |
| 未提前讲授 (`no_preteach_score`) | `number` | 是 | 否 | 按结构化合同生成 |
| 视觉与动作连续性 (`continuity_score`) | `number` | 是 | 否 | 按结构化合同生成 |
| 课堂可用性 (`classroom_usability_score`) | `number` | 是 | 否 | 按结构化合同生成 |
| 评估发现 (`classroom_quality_findings`) | `repeatable` | 是 | 否 | 子字段：发现键、严重度、时间区间、观察、预期、受影响镜头 |
| 是否通过 (`classroom_quality_passed`) | `boolean` | 是 | 否 | 按结构化合同生成 |
| 评估总结 (`classroom_quality_summary`) | `rich_text` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.video_classroom_quality.markdown.v1`
- 教师可见：是

```markdown
# 视频课堂质量报告

课程驱动创意：{{course_grounded_creative_score}}

课堂交接：{{handoff_accuracy_score}}

未提前讲授：{{no_preteach_score}}

连续性：{{continuity_score}}

课堂可用性：{{classroom_usability_score}}

## 发现
{{classroom_quality_findings}}

通过：{{classroom_quality_passed}}

{{classroom_quality_summary}}
```
