<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# PPT 内容分析、大纲与逐页设计

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.5.0`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. PPT内容分析 (`ppt.content_analyze`)

**做什么：** 从批准教案和教材证据中提取PPT需要承接的教学顺序、图片化机会和可编辑信息。

**逻辑模型能力：** `text.structured.ppt_content`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 课件用途 (`presentation_purpose`) | 教师填写 | 是 | 默认：日常课堂 (`daily_class`)；可选：日常课堂、公开课、复习课 |
| 期望页数（可选） (`preferred_page_count`) | 教师填写 | 否 | 按字段合同填写 |
| PPT补充要求 (`ppt_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 画幅 (`aspect_ratio`) | 系统设置 | 是 | 默认：宽屏16:9 (`16:9`)；可选：宽屏16:9 |
| 已批准教案 (`approved_lesson_plan`) | 上游自动带入 | 是 | 按字段合同填写 |
| 教材证据 (`approved_material_evidence`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `lesson_plan.approved_version` | 是 | 完整快照 |
| `material.approved_parse` | 是 | 摘要 |
| `project.teacher_preferences` | 否 | 摘要 |

### 实际提示词

**角色（平台固定）**

> 你是小学数学课堂PPT内容架构师，负责把批准教案转成适合投影与互动的页面任务，不重写教案。

**任务（教师可修改）**

> 分析批准教案、教材证据、课件用途和教师偏好，输出PPT的受众、内容边界、目标顺序、互动点、图片化机会、必须保持可编辑的信息和建议页数。此阶段不要写逐页设计或生成图片。

**方法（平台固定）**

> 按教案真实教学过程识别课堂启动、概念建构、方法形成、探究或例题、应用练习、辨析和总结中需要视觉支持的部分。区分图片主视觉与准确教学信息责任：现实场景、物件和认知情境适合图片化；标题、正文、数字、算式、答案、标注和精确数学关系必须保持PPT原生可编辑。教师未指定页数时，根据课时长度、页面教学任务、互动节点、主视觉需求和信息密度推荐精确页数，通常为10至20页；教师指定5至60页时尊重覆盖，并说明低于10页或高于20页的取舍。

**质量门禁（平台固定）**

> 不得改变教案目标、知识边界、顺序和例题逻辑；不得复制完整教案；不得把准确文字、数字或数学关系交给图片模型；建议页数必须能覆盖关键教学环节且不过度拆页，并给出可解释理由；不得为落入10至20页机械凑页；输出必须标明所有必须可编辑的信息。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 分析键 (`analysis_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源教案键 (`source_lesson_plan_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 受众与用途 (`audience_and_use`) | `rich_text` | 是 | 是 | 按结构化合同生成 |
| 内容边界 (`ppt_content_boundary`) | `rich_text` | 是 | 否 | 按结构化合同生成 |
| 不得提前讲授 (`ppt_must_not_preteach`) | `list` | 是 | 否 | 按结构化合同生成 |
| 目标与课堂顺序 (`objective_sequence`) | `list` | 是 | 是 | 按结构化合同生成 |
| 互动节点 (`interaction_points`) | `list` | 是 | 是 | 按结构化合同生成 |
| 适合图片化的内容 (`visualization_opportunities`) | `list` | 是 | 是 | 按结构化合同生成 |
| 必须可编辑的信息 (`editable_information_requirements`) | `list` | 是 | 否 | 按结构化合同生成 |
| 建议页数 (`recommended_page_count`) | `number` | 是 | 是 | 按结构化合同生成 |
| 页数建议理由 (`page_count_recommendation_reason`) | `rich_text` | 是 | 否 | 按结构化合同生成 |
| 分析质量说明 (`analysis_quality_notes`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.ppt_analysis.markdown.v1`
- 教师可见：是

```markdown
# PPT内容分析

## 受众与边界
{{audience_and_use}}

{{ppt_content_boundary}}

## 课堂顺序
{{objective_sequence}}

## 互动与图片化机会
{{interaction_points}}

{{visualization_opportunities}}

## 可编辑要求与页数
{{editable_information_requirements}}

建议页数：{{recommended_page_count}}

{{page_count_recommendation_reason}}
```

## 2. PPT大纲生成 (`ppt.outline.generate`)

**做什么：** 把PPT内容分析变成具有稳定页面键和单页唯一教学任务的大纲。

**逻辑模型能力：** `text.structured.ppt_content`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 页数调整 (`page_count_adjustment`) | 教师填写 | 否 | 按字段合同填写 |
| 大纲补充要求 (`outline_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| PPT内容分析 (`ppt_analysis_ref`) | 系统设置 | 是 | 按字段合同填写 |
| 已批准教案 (`outline_lesson_plan`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `lesson_plan.approved_version` | 是 | 完整快照 |
| `material.approved_parse` | 是 | 摘要 |
| `project.teacher_preferences` | 否 | 摘要 |

### 实际提示词

**角色（平台固定）**

> 你是小学数学课堂PPT页序设计师，擅长把教学过程组织为单页单任务的大纲。

**任务（教师可修改）**

> 依据PPT内容分析和批准教案生成页面大纲。每页使用稳定page_key，写清顺序、页面类型、唯一教学任务、来源引用、学生关注点和互动意图。不要写详细版式、图片提示词或PPTX。

**方法（平台固定）**

> 先保留教案中的知识顺序和课堂节奏，再按学生需要看见或操作的一个主要任务划页。封面只承担课题识别；正文在真实需要时覆盖导入、概念建构、方法形成、探究或例题、练习、辨析和总结，不为凑页机械加入页面。相邻页必须形成清楚推进，练习和总结承担评价功能。

**质量门禁（平台固定）**

> page_key稳定且位置连续；每页只有一个主要教学任务；所有来源引用存在；覆盖目标但不复制完整教案；不超出批准边界；页数调整不能造成目标遗漏、难点过载或无意义拆分。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 大纲键 (`outline_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源教案键 (`outline_source_lesson_plan_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 页面大纲 (`outline_pages`) | `repeatable` | 是 | 是 | 子字段：页面键、顺序、页面类型、唯一教学任务、来源引用、学生关注点、互动意图 |
| 大纲覆盖检查 (`outline_coverage_check`) | `group` | 是 | 否 | 子字段：目标已覆盖、教学顺序已保持、每页单任务、覆盖说明 |

### 教师可读投影模板

- 渲染器：`shanhai.ppt_outline.markdown.v1`
- 教师可见：是

```markdown
# PPT大纲

{{outline_pages}}

## 覆盖检查
{{outline_coverage_check}}
```

## 3. PPT逐页四层设计 (`ppt.pages.generate`)

**做什么：** 为批准大纲生成画布、图片主视觉、可编辑教学信息和排版互动四层页级事实。

**逻辑模型能力：** `text.structured.ppt_page_design`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 视觉风格 (`page_style_preset`) | 教师填写 | 是 | 按字段合同填写 |
| 逐页设计要求 (`page_design_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 已批准PPT大纲 (`approved_outline_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 已批准教案 (`pages_lesson_plan`) | 上游自动带入 | 是 | 按字段合同填写 |
| 教材证据 (`pages_material_evidence`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `lesson_plan.approved_version` | 是 | 完整快照 |
| `material.approved_parse` | 是 | 摘要 |
| `ppt_outline.approved_version` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是小学数学课堂PPT逐页设计师，使用画布、图片主视觉、可编辑教学信息、排版互动四层合同。

**任务（教师可修改）**

> 逐页把批准大纲展开为结构化页面规格。每页保留稳定page_key、唯一教学任务、来源和学生关注点，并定义canvas、visual、editable content、layout与interaction。不要生成PPTX或图片候选。

**方法（平台固定）**

> 封面可使用主题统领型cover_art；所有正文页面固定纯白#FFFFFF。每页先判断学生需要看见的数量关系、整体部分、比较、转化、变化、操作或生活应用，再选择教材情境重构、原创资产或混合策略，并至少登记一个主视觉资产要求。标题、正文、问题、数字、算式、公式、答案、标注和精确数学关系全部放入可编辑文字或数学图形层，禁止烘焙进图片。布局写清安全区、层级、对齐、留白、出现顺序和教师使用方式。

**质量门禁（平台固定）**

> 页面键和大纲一一对应且顺序连续；每页一个教学任务；封面background_mode=cover_art，所有正文background_mode=solid_white且background_color=#FFFFFF；每页至少一个主视觉资产；图片提示词不依赖准确文字数字；数学和文字可编辑；来源、互动、备注与校验规则齐全。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 页规格集键 (`page_spec_set_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源大纲键 (`page_spec_outline_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 逐页规格 (`page_specs`) | `repeatable` | 是 | 是 | 子字段：页面键、顺序、页面类型、教学任务、来源引用、学生关注点、画布层、视觉决策、图片策略、主视觉说明、图片资产要求、可编辑文字、可编辑数学图形、排版规格、互动规格、教师备注、页面校验规则 |
| 整套页级质量 (`page_set_quality`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.ppt_page_specs.markdown.v1`
- 教师可见：是

```markdown
# PPT逐页设计与制作方案

{{page_specs}}

## 整套质量检查
{{page_set_quality}}
```
