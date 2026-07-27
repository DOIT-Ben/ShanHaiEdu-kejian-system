<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# 课程驱动的三类九套导入方案

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.5.3`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. 课程驱动导入方案 (`intro.generate_options`)

**做什么：** 以已批准课时、知识边界、最小教材证据和教师偏好先生成候选，再独立统一评分形成最终课堂导入方案；完善已有创意时绑定一个exact来源版本。

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

> 你是小学数学课程驱动的课堂导入候选设计师，负责生成科普、应用、故事三种主要倾向的候选，不参与评分。

**任务（教师可修改）**

> 读取目标课时稳定键、exact teaching_focus、一句话学习目标、教学内容边界、must_not_preteach、年级或年龄段、教材证据摘要及可选教师创意、媒介和时长偏好，只生成未评分候选池。default_nine禁止已有创意来源并生成九套；refine_existing必须基于一个exact已有方案版本只完善一套。不得输出推荐分、推荐理由、适配风险、推荐结论、教案正文、PPT、分镜、旁白、字幕、资产、Provider参数或费用。

**方法（平台固定）**

> 直接把批准LessonUnit的teaching_focus原样写入source_knowledge_point和每套knowledge_point，不得概括、改写或替换。再从可观察现象、真实任务、人物或主体目标等不同角度形成候选；课程依据必须从创意形成开始参与，不能在完成后补贴课题词。每套只形成主要倾向、创意概念、钩子、观看价值、课程关联、课堂第一问、交接时刻、不得提前讲授、媒介、时长和适配理由。

**质量门禁（平台固定）**

> default_nine来源版本为0、主要倾向science、application、story各恰好三套且option_key为INTRO-SCI-01至03、INTRO-APP-01至03、INTRO-STO-01至03；refine_existing来源版本恰好1且方案恰好1套。source_knowledge_point和每套knowledge_point必须exact等于批准LessonUnit的teaching_focus；每套必须可追溯目标课时和教材证据；不得提前讲出需要学生发现的定义、写法、方法或结论；不得自评分或输出推荐结论。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 方案集键 (`option_set_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 生成方式 (`generation_mode`) | `enum` | 是 | 否 | 按结构化合同生成 |
| 已有创意来源版本 (`source_intro_option_version_refs`) | `list` | 是 | 否 | default_nine固定为空；refine_existing固定一个exact ArtifactVersion ID |
| 来源课时键 (`source_lesson_unit_key`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 来源知识点 (`source_knowledge_point`) | `text` | 是 | 否 | 按结构化合同生成 |
| 来源教材证据 (`source_material_evidence_keys`) | `list` | 是 | 否 | 按结构化合同生成 |
| 导入方案 (`options`) | `repeatable` | 是 | 是 | 子字段：方案键、来源课时键、知识点、主要创作倾向、标题、课程驱动创意概念、钩子、观看价值、建议媒介、建议时长、课程关联、课堂第一问、交接时刻、不得提前讲授、适配理由、风险、推荐分、推荐理由 |
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
