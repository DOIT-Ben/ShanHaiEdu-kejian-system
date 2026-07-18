<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# 视频剧本、粗分镜与视觉母图

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.0.0`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. 视频母版剧本生成 (`video.master_script.generate`)

**做什么：** 只从已选导入方案不可变快照扩写完整独立短片剧本，并准确停在课堂交接时刻。

**逻辑模型能力：** `text.structured.creative_video`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 时长方式 (`video_duration_mode`) | 教师填写 | 是 | 默认：系统按故事与价格推荐 (`system_recommended`)；可选：系统按故事与价格推荐、教师指定 |
| 目标总时长（可选） (`video_target_duration_seconds`) | 教师填写 | 否 | 按字段合同填写 |
| 费用偏好 (`video_cost_preference`) | 教师填写 | 是 | 默认：平衡 (`balanced`)；可选：节省费用、平衡、优先质量 |
| 视频画幅 (`video_aspect_ratio`) | 教师填写 | 是 | 默认：横屏16:9 (`16:9`)；可选：横屏16:9、竖屏9:16 |
| 语言 (`video_language`) | 教师填写 | 是 | 默认：普通话 (`zh-CN`)；可选：普通话 |
| 剧本补充要求 (`master_script_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 已选导入方案 (`selected_intro_snapshot_ref`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `intro_selection.snapshot` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是独立创意课堂导入短片的母版编剧，负责把已选方案扩写为完整可生产故事。

**任务（教师可修改）**

> 严格继承已选方案的标题、独立概念、钩子、课程锚点、课堂第一问、交接时刻和不得提前讲授内容，生成完整故事与场次，并给出60至180秒内的时长建议。不得重新选择创意，不得读取或推测教案、教材、PPT。此阶段不要写shot级提示词或臆造价格。

**方法（平台固定）**

> 先让脱离课程仍成立的故事具有清楚的开始状态、目标或未知、可见变化和结局推进，再只在最后按上游唯一锚点回接。每个场次写明目的、地点、人物或主体、动作、旁白、对白、声音意图、开始和结束状态及预计时长。根据故事场次、可见节拍、预计镜头数、节奏和交接点推荐60至180秒内的精确总时长；teacher_fixed时尊重教师目标，system_recommended时使用建议值。价格由服务端当前路由和版本化价格档案另行估算，模型只声明需要报价，不输出金额。

**质量门禁（平台固定）**

> 上游独立创意与锚点字段不得改写；完整故事不是梗概或shot列表；结尾准确停在handoff_moment；不得解释must_not_preteach；建议时长和最终目标均在60至180秒，场次时长总和等于目标时长；建议理由与预计镜头数可复核；不包含Provider、模型、参考图位置、虚构费用、自动批准或下一工具。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 母版剧本键 (`master_script_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 已选方案键 (`master_selected_intro_option_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 短片标题 (`master_title`) | `text` | 是 | 是 | 按结构化合同生成 |
| 叙事目的 (`narrative_purpose`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 完整故事 (`complete_story`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 场次 (`master_scenes`) | `repeatable` | 是 | 是 | 子字段：场次键、顺序、场次目的、地点、人物或主体、可见变化、动作、旁白、对白、声音意图、开始状态、结束状态、预计时长 |
| 课堂交接 (`master_handoff`) | `group` | 是 | 否 | 子字段：唯一课程锚点、课堂第一问、交接时刻、不得提前讲授 |
| 时长建议 (`master_duration_recommendation`) | `group` | 是 | 否 | 子字段：时长方式、系统建议时长、建议理由、预计镜头数、进入分镜前需要服务端报价 |
| 目标总时长 (`master_target_duration_seconds`) | `number` | 是 | 是 | 按结构化合同生成 |
| 剧本质量检查 (`master_script_quality`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.video_master_script.v1`
- 教师可见：是

```markdown
# {{master_title}}

## 叙事目的
{{narrative_purpose}}

## 完整故事
{{complete_story}}

## 场次
{{master_scenes}}

## 课堂交接
{{master_handoff}}
```

## 2. 视频粗分镜生成 (`video.rough_storyboard.generate`)

**做什么：** 把批准母版剧本拆成场次节拍、预计时长和资产需求，不产生逐镜Provider提示词。

**逻辑模型能力：** `text.structured.creative_video`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 节奏偏好 (`rough_pacing_preference`) | 教师填写 | 是 | 默认：均衡 (`balanced`)；可选：舒缓、均衡、活泼 |
| 粗分镜补充要求 (`rough_storyboard_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 批准母版剧本 (`rough_master_script_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 已选导入方案 (`rough_selected_intro_ref`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `intro_selection.snapshot` | 是 | 摘要 |
| `video.master_script.approved_version` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是创意短片粗分镜设计师，负责验证故事节奏、时长和可制作性。

**任务（教师可修改）**

> 把批准母版剧本按场次和故事节拍拆成粗分镜。每个beat只说明发生什么、学生看到什么变化、预计多长、需要哪些资产和怎样衔接；不要写逐秒运镜、参考图序号或视频模型提示词。

**方法（平台固定）**

> 保持母版剧本场次、开始结束状态和唯一课堂交接不变。按可见变化拆分2个以上节拍，每个节拍只有一个主要事件，稳定引用来源scene_key。预计时长总和等于母版目标时长，并为后续人物、场景、道具、生物资产清单提供明确需求。

**质量门禁（平台固定）**

> 不改写已选方案或母版剧本；节拍顺序连续、来源有效、单节拍单事件；总时长一致；最后节拍才到达handoff_moment；不包含Provider提示词、参考图位置、shot时长硬切、资产文件或模型参数。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 粗分镜键 (`rough_storyboard_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源母版剧本键 (`rough_master_script_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 故事节拍 (`rough_beats`) | `repeatable` | 是 | 是 | 子字段：节拍键、来源场次键、顺序、唯一主要事件、开始状态、结束状态、预计时长、资产需求、衔接 |
| 总时长 (`rough_total_duration_seconds`) | `number` | 是 | 否 | 按结构化合同生成 |
| 粗分镜质量 (`rough_storyboard_quality`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.video_rough_storyboard.markdown.v1`
- 教师可见：是

```markdown
# 视频粗分镜

{{rough_beats}}

总时长：{{rough_total_duration_seconds}}秒

## 质量检查
{{rough_storyboard_quality}}
```

## 3. 视频视觉母图提示词 (`video.style_master.prompt.generate`)

**做什么：** 从已选方案、母版剧本和粗分镜中编译视频视觉母图请求，用于锁定视觉语言而非替代全部资产。

**逻辑模型能力：** `text.structured.image_prompt`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 视觉母图候选数 (`video_style_candidate_count`) | 教师填写 | 是 | 默认：3 |
| 视频视觉方向 (`video_style_preset`) | 教师填写 | 是 | 按字段合同填写 |
| 视觉补充要求 (`video_style_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 母版剧本 (`style_master_script_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 粗分镜 (`style_rough_storyboard_ref`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `intro_selection.snapshot` | 是 | 摘要 |
| `video.master_script.approved_version` | 是 | 完整快照 |
| `video.rough_storyboard.approved_version` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是创意短片视觉开发师，负责用一张视觉母图锁定整片视觉语言。

**任务（教师可修改）**

> 依据已选方案、批准母版剧本和粗分镜，生成视觉母图的完整图片请求，覆盖代表主体、场景、媒介、造型比例、材质、配色、光线、背景密度、摄影机和运动语言。母图只锁风格，不替代人物设定、场景空镜、道具单体或镜头关键帧。

**方法（平台固定）**

> 选择能同时展示主要主体、代表环境和关键材质关系的非剧情高潮构图；说明16:9或项目画幅、纸艺黏土媒介、主体尺度、接触阴影、背景密度、机位、镜头运动倾向和候选数。风格约束必须能被后续图片和视频提示词逐字复用。

**质量门禁（平台固定）**

> 不得改写故事或课程交接；不得把准确文字、字幕、公式、水印或Logo画入母图；禁止恐怖、成人化和风格漂移；母图不作为全部镜头唯一垫图；候选数、目标槽位、画幅和负面约束完整。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 请求键 (`style_master_request_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 代表主体与场景 (`style_master_subjects`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 媒介与写实程度 (`style_master_medium`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 造型材质与线条 (`style_master_design_rules`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 配色光线质感 (`style_master_palette_lighting`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 摄影机与运动语言 (`style_master_camera_motion`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 画幅 (`style_master_aspect_ratio`) | `text` | 是 | 否 | 按结构化合同生成 |
| 禁止项 (`style_master_negative_constraints`) | `list` | 是 | 否 | 按结构化合同生成 |
| 候选数 (`style_master_candidate_count`) | `number` | 是 | 是 | 按结构化合同生成 |
| 目标槽位 (`style_master_target_slot`) | `text` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.image_prompt.v1`
- 教师可见：是

```markdown
代表主体与场景：{{style_master_subjects}}。媒介：{{style_master_medium}}。造型材质：{{style_master_design_rules}}。配色光线：{{style_master_palette_lighting}}。摄影机与运动语言：{{style_master_camera_motion}}。画幅：{{style_master_aspect_ratio}}。禁止：{{style_master_negative_constraints}}。
```

## 4. 视频视觉母图生成 (`video.style_master.image.generate`)

**做什么：** 执行视觉母图图片请求，产生用于批准风格合同的可审计候选。

**逻辑模型能力：** `image.generate.education_16x9`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 视觉母图完整指令 (`style_master_prompt_text`) | 教师填写 | 是 | 按字段合同填写 |
| 候选数 (`style_master_generation_count`) | 教师填写 | 是 | 默认：3 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 目标槽位 (`style_master_generation_slot`) | 系统设置 | 是 | 按字段合同填写 |
| 风格参考 (`style_master_reference_assets`) | 系统设置 | 否 | 按字段合同填写 |

- 无上游业务 Context；生成所需任务包或参考资产由系统字段带入。

### 实际提示词

**角色（平台固定）**

> 你是服务端视频视觉母图生成执行器。

**任务（教师可修改）**

> 通过图片模型网关执行已冻结视觉母图指令，生成指定数量候选并返回文件事实。

**方法（平台固定）**

> 按style_reference角色传入可选参考资产；对每个候选记录稳定键、尺寸、媒体类型和SHA-256。Provider路由与私有参数停留在适配层，不进入业务结果。

**质量门禁（平台固定）**

> 候选可解码、画幅正确、视觉语言清楚、儿童安全且无文字水印Logo；失败结果不冒充候选；候选采用和项目写回保持独立。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 生成请求键 (`style_master_generation_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 目标槽位 (`style_master_generation_target`) | `text` | 是 | 否 | 按结构化合同生成 |
| 视觉母图候选 (`style_master_candidates`) | `repeatable` | 是 | 否 | 子字段：候选键、宽度、高度、媒体类型、文件摘要、质量标记 |

### 教师可读投影模板

- 渲染器：`shanhai.image_candidates.markdown.v1`
- 教师可见：是

```markdown
# 视频视觉母图候选

目标槽位：{{style_master_generation_target}}

{{style_master_candidates}}
```
