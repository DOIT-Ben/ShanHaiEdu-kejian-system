<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# 视频四类图片资产

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

内容包：`shanhai.primary_math.courseware@1.1.0`。

说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate 由平台固定，防止结构和教学边界被改坏。

## 1. 视频四类资产清单 (`video.asset_inventory.generate`)

**做什么：** 从批准母版剧本和粗分镜扫描、分类并去重人物、场景、道具和生物资产。

**逻辑模型能力：** `text.structured.creative_video`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 资产清单补充要求 (`asset_inventory_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 资产复用策略 (`asset_reuse_policy`) | 系统设置 | 是 | 默认：同一基础身份复用 (`deduplicate_base_identity`)；可选：同一基础身份复用 |
| 批准母版剧本 (`inventory_master_script_ref`) | 上游自动带入 | 是 | 按字段合同填写 |
| 批准粗分镜 (`inventory_rough_storyboard_ref`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `video.master_script.approved_version` | 是 | 完整快照 |
| `video.rough_storyboard.approved_version` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是创意短片资产制片，负责从已批准故事事实中建立可复用的四类图片资产清单。

**任务（教师可修改）**

> 联合扫描母版剧本和粗分镜，登记实际需要的人物character、场景scene、道具prop和生物creature。没有某类时保留空分类，不强行创造；同一基础身份去重，明确造型或状态变体另建版本。

**方法（平台固定）**

> 每项建立稳定asset_key和identity_key，记录来源scene/beat、用途、外观与状态、默认构图和项目目标槽位。场景默认无人空镜，道具默认单体无手持；不同资产不得塞进一张全家福。人物、动物、机器或抽象主体都只按故事真实需要登记，不因小学受众强制儿童或教室。

**质量门禁（平台固定）**

> 所有粗分镜资产需求均被覆盖且引用有效；同一基础身份不重复；场景与道具遵守默认独立构图；四类汇总与资产记录一致；不生成图片提示词、文件、Provider参数或未在故事出现的装饰资产。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 资产清单键 (`asset_inventory_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 视频图片资产 (`video_assets`) | `repeatable` | 是 | 是 | 子字段：资产键、资产类型、语义名称、基础身份键、来源场次、来源节拍、用途、外观与状态、默认构图、目标槽位 |
| 四类汇总 (`asset_category_summary`) | `group` | 是 | 否 | 子字段：人物、场景、道具、生物 |
| 去重与变体说明 (`asset_deduplication_notes`) | `rich_text` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.video_asset_inventory.markdown.v1`
- 教师可见：是

```markdown
# 视频四类资产清单

{{video_assets}}

## 四类汇总
{{asset_category_summary}}

## 去重说明
{{asset_deduplication_notes}}
```

## 2. 视频资产图片提示词 (`video.asset_prompts.generate`)

**做什么：** 为四类资产清单逐项编译图片创作任务，继承批准视频风格合同。

**逻辑模型能力：** `text.structured.image_prompt`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 生成范围 (`video_asset_prompt_scope`) | 教师填写 | 是 | 默认：全部缺失资产 (`all_missing`)；可选：全部缺失资产、选定资产 |
| 选定资产 (`selected_video_asset_keys`) | 教师填写 | 否 | 按字段合同填写 |
| 资产图片补充要求 (`video_asset_prompt_requirements`) | 教师填写 | 否 | 按字段合同填写 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 资产清单 (`current_video_asset_inventory`) | 上游自动带入 | 是 | 按字段合同填写 |
| 视频风格合同 (`approved_video_style`) | 上游自动带入 | 是 | 按字段合同填写 |

| 上游快照 | 是否必须 | 注入范围 |
| --- | --- | --- |
| `video.asset_inventory.current_version` | 是 | 完整快照 |
| `video.master_script.approved_version` | 是 | 摘要 |
| `video.style.approved_version` | 是 | 完整快照 |

### 实际提示词

**角色（平台固定）**

> 你是创意短片四类资产图片提示词设计师。

**任务（教师可修改）**

> 为资产清单中的每个目标资产生成一个独立图片任务，逐字继承批准视频风格合同并固定目标槽位。人物、场景、道具、生物不得混成一张全家福。

**方法（平台固定）**

> 提示词写清语义主体、外观状态、材质厚度、承托面、接触阴影、光源、透视、构图、色彩、画幅和用途。character生成清楚身份设定；scene默认无人空镜；prop默认单体无手持；creature保持物种或幻想生物结构稳定。所有任务继承同一视觉语言和一致性键。

**质量门禁（平台固定）**

> 任务与资产清单一一对应，来源、类型、目标槽位和一致性键完整；禁止文字、字幕、公式、水印、Logo、额外主体、畸形结构和风格漂移；不得生成剧情镜头或把视觉母图当成资产替代品。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 图片任务包键 (`video_asset_package_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 视频风格版本 (`video_style_contract_ref`) | `reference` | 是 | 否 | 按结构化合同生成 |
| 视频资产图片任务 (`video_asset_prompt_items`) | `repeatable` | 是 | 是 | 子字段：任务键、资产键、资产类型、目标槽位、完整图片提示词、负面约束、画幅、一致性键 |
| 任务覆盖检查 (`video_asset_prompt_coverage`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.creation_image_package.markdown.v1`
- 教师可见：是

```markdown
# 视频资产图片任务包

风格合同：{{video_style_contract_ref}}

{{video_asset_prompt_items}}

## 覆盖检查
{{video_asset_prompt_coverage}}
```

## 3. 视频四类图片资产生成 (`video.assets.generate`)

**做什么：** 按视频资产图片任务逐项生成候选，继承视觉母图并保持四类资产身份、槽位和文件血缘。

**逻辑模型能力：** `image.generate.education_16x9`  **视觉预设：** `style.primary_math.paper_clay`

### 教师需要填写

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 每项候选数 (`video_asset_candidates_per_item`) | 教师填写 | 是 | 默认：2 |
| 逻辑质量档位 (`video_asset_generation_quality`) | 教师填写 | 是 | 默认：均衡 (`balanced`)；可选：快速、均衡、高质量 |

### 系统自动带入

| 字段 | 来源 | 必填 | 默认值或说明 |
| --- | --- | --- | --- |
| 视频资产图片任务包 (`video_asset_creation_package_ref`) | 系统设置 | 是 | 按字段合同填写 |
| 视觉母图参考 (`video_style_master_asset`) | 系统设置 | 是 | 按字段合同填写 |

- 无上游业务 Context；生成所需任务包或参考资产由系统字段带入。

### 实际提示词

**角色（平台固定）**

> 你是服务端视频四类图片资产批量生成执行器。

**任务（教师可修改）**

> 逐项执行冻结的character、scene、prop和creature图片任务，使用批准视觉母图维持风格一致，返回候选和文件事实。不得合并任务或改变固定槽位。

**方法（平台固定）**

> 每项独立调用满足image.generate.education_16x9能力的网关路由；按video_style_master角色传入视觉母图。记录任务键、资产键、类型、槽位、候选摘要和质量标记。场景保持无人空镜、道具保持单体，除非任务合同明确要求变体。

**质量门禁（平台固定）**

> 候选可解码、风格一致、角色或物件身份稳定、无文字字幕公式水印Logo；每项有结果或显式失败；失败项只重试自身；候选采用不等于创建已批准资产版本或写回项目。

### 结构化输出字段

| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |
| --- | --- | --- | --- | --- |
| 生成批次键 (`video_asset_generation_batch_key`) | `text` | 是 | 否 | 按结构化合同生成 |
| 视频图片资产候选 (`generated_video_assets`) | `repeatable` | 是 | 否 | 子字段：任务键、资产键、资产类型、目标槽位、候选文件、质量标记 |
| 资产批次覆盖 (`video_asset_generation_coverage`) | `rubric` | 是 | 否 | 按结构化合同生成 |

### 教师可读投影模板

- 渲染器：`shanhai.video_image_assets.markdown.v1`
- 教师可见：是

```markdown
# 视频四类图片资产生成结果

{{generated_video_assets}}

## 覆盖检查
{{video_asset_generation_coverage}}
```
