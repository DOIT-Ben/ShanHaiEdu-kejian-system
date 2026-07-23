<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# 课程驱动的三类九套导入方案

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.4.0`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. 课程驱动导入方案 (`intro.generate_options`)

**做什么：** 以已批准课时、知识边界、最小教材证据和教师偏好，在一次生成中产出一套或三类九套最终课堂导入方案；完善已有创意时绑定一个exact来源版本。

**逻辑模型能力：** `text.structured.creative_education`  **视觉预设：** 无固定视觉预设

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 生成方式 (`generation_mode`) | 教师填写 | 是 | 默认：三类九套 (`default_nine`)；可选：三类九套、完善已有创意 |
| 已有创意 (`existing_idea_ref`) | 教师填写 | 否 | default_nine禁止填写；refine_existing必须选择一个同课时exact方案集版本 |
| 媒介偏好 (`medium_preferences`) | 教师填写 | 否 | 按字段合同填写 |
| 建议导入时长 (`duration_preference_seconds`) | 教师填写 | 否 | 按字段合同填写 |
| 创意偏好 (`creative_preferences`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 目标课时 (`target_lesson_unit`) | 上游自动带入 | 是 | 按字段合同填写 |
| 知识点 (`knowledge_point`) | 上游自动带入 | 是 | 按字段合同填写 |
| 一句话学习目标 (`learning_objective_summary`) | 上游自动带入 | 是 | 按字段合同填写 |
| 教学内容边界 (`teaching_content_boundary`) | 上游自动带入 | 是 | 按字段合同填写 |
| 不得提前讲授 (`must_not_preteach`) | 上游自动带入 | 是 | 按字段合同填写 |
| 年级 (`grade_level`) | 上游自动带入 | 是 | 按字段合同填写 |
| 受众年龄段 (`audience_age_band`) | 上游自动带入 | 是 | 按字段合同填写 |
| 教材证据摘要 (`target_material_evidence`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `lesson_division.approved_version` | 是 | 仅目标课时投影（`division_key` + `lesson_unit`） |
| `material.approved_parse` | 是 | 摘要 |
| `intro_options.existing_version` | 否 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是小学数学课程驱动的课堂导入方案设计师，擅长从知识点、学习目标、教材证据和不得提前讲授边界中设计科普、应用、故事倾向可交叉的创意方案。

**任务（教师可修改）**

> 读取目标课时稳定键、知识点、一句话学习目标、教学内容边界、must_not_preteach、年级或年龄段、教材证据摘要及可选教师创意、媒介和时长偏好，在一次调用中直接生成最终intro_option_set。default_nine禁止已有创意来源并生成九套；refine_existing必须基于一个exact已有方案版本只完善一套。不要生成教案正文、PPT、分镜、旁白、字幕、资产、Provider参数或费用。

**方法（平台固定）**

> 先提取课程种子，再从可观察现象、真实任务、人物或主体目标等不同角度生成创意；课程依据必须从创意形成开始参与，不能在完成后补贴课题词。每套同时形成主要与辅助倾向、创意概念、钩子、观看价值、课程关联、课堂第一问、交接时刻、不得提前讲授、媒介、时长、适配、风险和推荐结论。science、application、story只是主要倾向，辅助倾向可以交叉。

**质量门禁（平台固定）**

> default_nine来源版本为0、主要倾向各恰好三套且至少一套包含两个以上辅助倾向；refine_existing来源版本恰好1且方案恰好1套。每套必须可追溯目标课时、知识点和教材证据，创意与课程依据存在实质关联；不得提前讲出需要学生发现的定义、写法、方法或结论；default_nine最高推荐分必须唯一；不得把三种倾向解释为互斥类别；输出不含完整教案、PPT、视频产物、Provider和费用。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 方案集键 (`option_set_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 生成方式 (`generation_mode`) | `enum` | 是 | 否 | 按结构化合同生成 |
| 已有创意来源版本 (`source_intro_option_version_refs`) | `list` | 是 | 否 | default_nine固定为空；refine_existing固定一个exact ArtifactVersion ID |
| 来源课时键 (`source_lesson_unit_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 来源知识点 (`source_knowledge_point`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源教材证据 (`source_material_evidence_keys`) | `list` | 是 | 否 | 按结构化合同生成 |
| 导入方案 (`options`) | `repeatable` | 是 | 是 | 子字段：方案键、来源课时键、知识点、主要创作倾向、辅助创作倾向、标题、课程驱动创意概念、钩子、观看价值、建议媒介、建议时长、课程关联、课堂第一问、交接时刻、不得提前讲授、适配理由、风险、推荐分、推荐理由 |
| 推荐结论 (`recommendation_summary`) | `group` | 是 | 否 | 子字段：最高推荐方案、最高分唯一 |

### 教师可读投影模板

- 渲染器：`shanhai.intro_option_set.markdown.v1`
- 教师可见：是

```markdown
# 课程驱动课堂导入设计

知识点：{{source_knowledge_point}}

{{options}}

## 推荐结论
{{recommendation_summary}}
```
