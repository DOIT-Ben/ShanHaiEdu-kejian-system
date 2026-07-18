<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# PPT 封面与正文图片

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.0.0`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. PPT封面图片提示词 (`ppt.cover.prompt.generate`)

**做什么：** 基于批准大纲和页规格生成封面主视觉的完整图片请求，不把准确课题文字交给图片模型。

**逻辑模型能力：** `text.structured.image_prompt`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 封面候选数 (`cover_candidate_count`) | 教师填写 | 是 | 默认：3 |
| 封面风格 (`cover_style_preset`) | 教师填写 | 是 | 按字段合同填写 |
| 封面补充要求 (`cover_prompt_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 批准大纲 (`cover_outline_context`) | 上游自动带入 | 是 | 按字段合同填写 |
| 封面页规格 (`cover_page_context`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `ppt_outline.approved_version` | 是 | 摘要 |
| `ppt_page_spec.current_version` | 是 | 完整快照 |
| `project.teacher_preferences` | 否 | 摘要 |

### 实际提示词

**角色（平台固定）**

> 你是小学数学PPT封面主视觉提示词设计师。

**任务（教师可修改）**

> 根据批准PPT大纲、封面页规格和风格偏好，生成封面主视觉的结构化完整图片请求。封面表达课题核心和课堂吸引力，但准确课题文字由PPT可编辑层添加。

**方法（平台固定）**

> 写清主体、可见动作或关系、纸艺或黏土材质、承托面、接触阴影、光源、透视、16:9构图、标题安全区、配色和候选数量。封面可以是完整主视觉，不沿用正文白底组件布局；同时为标题和副标题保留稳定可读区域。

**质量门禁（平台固定）**

> 不得要求图片模型绘制课题文字、数字、公式、答案、Logo或水印；主视觉必须与教学主题有关但不提前讲解答案；候选数2至4；构图、材质、光线、留白、负面约束和固定目标槽位齐全。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 请求键 (`cover_request_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 主体与教学情境 (`cover_subject`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 构图与留白 (`cover_composition`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 材质与造型 (`cover_material_and_form`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 配色与光线 (`cover_palette_and_lighting`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 画幅 (`cover_aspect_ratio`) | `text` | 是 | 否 | 按结构化合同生成 |
| 标题安全区 (`cover_text_safe_area`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 负面约束 (`cover_negative_constraints`) | `list` | 是 | 否 | 按结构化合同生成 |
| 候选数 (`cover_candidate_count_output`) | `number` | 是 | 是 | 按结构化合同生成 |
| 目标槽位 (`cover_target_slot`) | `text` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.image_prompt.v1`
- 教师可见：是

```markdown
封面主体：{{cover_subject}}。构图与留白：{{cover_composition}}。材质造型：{{cover_material_and_form}}。配色与光线：{{cover_palette_and_lighting}}。画幅：{{cover_aspect_ratio}}。标题安全区：{{cover_text_safe_area}}。禁止：{{cover_negative_constraints}}。
```

## 2. PPT封面候选生成 (`ppt.cover.image.generate`)

**做什么：** 通过服务端图片网关执行封面业务请求并返回可审计候选，不在合同中固定Provider私有参数。

**逻辑模型能力：** `image.generate.education_16x9`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 完整封面生成指令 (`cover_prompt_text`) | 教师填写 | 是 | 按字段合同填写 |
| 候选数量 (`cover_generation_count`) | 教师填写 | 是 | 默认：3 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 目标槽位 (`cover_generation_target_slot`) | 系统设置 | 是 | 按字段合同填写 |
| 风格参考 (`cover_reference_assets`) | 系统设置 | 否 | 按字段合同填写 |

- 无上游业务 Context；生成所需任务包或参考资产由系统字段带入。

### 实际提示词

**角色（平台固定）**

> 你是服务端教育图片生成执行器，只执行已冻结的业务提示词和参考资产合同。

**任务（教师可修改）**

> 为PPT封面生成指定数量的16:9图片候选，保持业务提示词、目标槽位和参考资产顺序；返回文件事实和质量标记。

**方法（平台固定）**

> 通过模型网关选择满足image.generate.education_16x9能力的路由。参考资产仅按节点声明的style_reference角色传入；不把Provider名称、密钥、私有参数或临时URL写入业务产物。对每个结果记录稳定候选键、尺寸、媒体类型和SHA-256。

**质量门禁（平台固定）**

> 候选必须可解码、画幅符合16:9、无文字水印Logo、儿童安全且不依赖准确数学文字；失败结果不得冒充候选；候选只进入创作批次，采用不等于写回项目。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 生成请求键 (`cover_generation_request_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 目标槽位 (`cover_generation_target`) | `text` | 是 | 否 | 按结构化合同生成 |
| 封面候选 (`cover_candidates`) | `repeatable` | 是 | 否 | 子字段：候选键、产物类型、宽度、高度、媒体类型、文件摘要、质量标记 |

### 教师可读投影模板

- 渲染器：`shanhai.image_candidates.markdown.v1`
- 教师可见：是

```markdown
# PPT封面候选

目标槽位：{{cover_generation_target}}

{{cover_candidates}}
```

## 3. PPT正文图片任务包 (`ppt.body_asset_prompts.generate`)

**做什么：** 把逐页资产要求编译为可批量导入图片创作台的不可变任务项。

**逻辑模型能力：** `text.structured.image_prompt`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 生成范围 (`body_asset_scope`) | 教师填写 | 是 | 默认：全部缺失资产 (`all_missing`)；可选：全部缺失资产、选定页面 |
| 选定页面 (`selected_page_keys`) | 教师填写 | 否 | 按字段合同填写 |
| 正文图片补充要求 (`body_prompt_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 逐页规格 (`body_page_specs`) | 上游自动带入 | 是 | 按字段合同填写 |
| PPT视觉合同 (`body_style_contract`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `lesson_plan.approved_version` | 是 | 摘要 |
| `material.approved_parse` | 是 | 摘要 |
| `ppt_page_spec.current_version` | 是 | 完整快照 |
| `ppt_style.approved_version` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是小学数学PPT正文图片资产提示词工程师，负责从已批准页规格编译独立可生成的图片任务。

**任务（教师可修改）**

> 为目标页面的每个asset_requirement生成一个独立任务项，继承PPT视觉合同，写出完整提示词、负面约束、画幅、一致性键和固定目标槽位。不要合并不同资产，不生成PPT文字或数学答案。

**方法（平台固定）**

> 每个提示词说明主体、动作或用途、材质厚度、承托面、接触阴影、光源、透视、构图、色彩、画幅、留白和禁止项。参与精确数量、点数、排序、增删或逐步揭示的具象物件优先生成单体资产，由PPT复制和控制数量；准确文字、数字、算式、表格、关系线和答案留给可编辑层。正文继承封面视觉语言但保持白底，不复制封面背景。

**质量门禁（平台固定）**

> 任务项与页规格资产要求一一对应；每项只有一个目标槽位和一致性键；禁止文字数字公式水印Logo、额外主体和畸形结构；不得照搬教材插图或大段原文；每个资产独立可生成且能回溯页面与要求键。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 图片任务包键 (`body_package_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 视觉合同版本 (`body_style_contract_ref`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 正文图片任务 (`body_asset_items`) | `repeatable` | 是 | 是 | 子字段：任务键、页面键、资产要求键、资产角色、目标槽位、完整图片提示词、负面约束、画幅、一致性键 |
| 资产覆盖检查 (`body_asset_coverage`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.creation_image_package.markdown.v1`
- 教师可见：是

```markdown
# PPT正文图片任务包

视觉合同：{{body_style_contract_ref}}

{{body_asset_items}}

## 覆盖检查
{{body_asset_coverage}}
```

## 4. PPT正文图片生成 (`ppt.body_assets.generate`)

**做什么：** 按正文图片任务包批量生成独立候选并保持页面槽位、风格和文件血缘。

**逻辑模型能力：** `image.generate.education_16x9`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 逻辑质量档位 (`body_generation_quality`) | 教师填写 | 是 | 默认：均衡 (`balanced`)；可选：快速、均衡、高质量 |
| 每项候选数 (`body_candidates_per_item`) | 教师填写 | 是 | 默认：2 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 正文图片任务包 (`body_creation_package_ref`) | 系统设置 | 是 | 按字段合同填写 |
| 视觉参考资产 (`body_reference_assets`) | 系统设置 | 是 | 按字段合同填写 |

- 无上游业务 Context；生成所需任务包或参考资产由系统字段带入。

### 实际提示词

**角色（平台固定）**

> 你是服务端PPT正文图片批量生成执行器。

**任务（教师可修改）**

> 逐项执行冻结的正文图片任务，使用PPT视觉母图和页面构图参考保持一致性，返回分组候选及文件事实。不得合并任务项或猜测目标槽位。

**方法（平台固定）**

> 每个任务项单独调用满足image.generate.education_16x9能力的网关路由；按节点参考资产策略传入ppt_style_master和page_composition_reference。记录任务键、页面键、固定槽位、候选文件摘要和质量标记。准确数量的可复用单体保持同一来源，数量由后续PPT装配控制。

**质量门禁（平台固定）**

> 所有任务项均有结果或显式失败；候选可解码、风格一致、无文字数字公式水印Logo；文件和槽位血缘完整；失败项只重试自身，不重跑已通过页面；采用候选和写回项目保持独立。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 生成批次键 (`body_generation_batch_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 生成结果 (`body_generated_items`) | `repeatable` | 是 | 否 | 子字段：任务键、页面键、目标槽位、候选文件、质量标记 |
| 批次覆盖检查 (`body_generation_coverage`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.image_collection.markdown.v1`
- 教师可见：是

```markdown
# PPT正文图片生成结果

{{body_generated_items}}

## 覆盖检查
{{body_generation_coverage}}
```
