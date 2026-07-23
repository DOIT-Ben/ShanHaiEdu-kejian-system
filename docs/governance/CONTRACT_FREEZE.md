# 全链路合同冻结

## 1. 目的

本文件定义前端、教材到教案主链、完整 PPT、完整视频和交付包并行开发前必须共同遵守的冻结面。

冻结不是重新设计业务，也不是把实现写死。冻结的是已经由黄金手册、内容包和 48 节点工作流目录共同确认的边界：

```text
输入来源与 exact 版本
→ 节点与执行种类
→ Prompt / GenerationTemplate
→ 输出合同
→ 校验与批准
→ 持久化事实
→ 下游 exact 引用
→ 页面与 API 消费方式
```

冻结完成后，各轨道可以使用固定黄金输入独立实现内部节点；输出必须通过结构、业务边界、血缘和质量断言，才能与其他轨道对接。

## 2. 唯一事实源

冻结合同不复制已发布内容，而是引用以下现行机器事实：

- `contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json`：48 节点拓扑、输入输出、执行种类、作用域、validator、批准和持久化声明；
- `contracts/fixtures/primary-math-courseware-package/manifest.json`：不可变 `shanhai.primary_math.courseware@1.4.0` 内容项和哈希；
- `workflow/builtin/primary_math_courseware/generation-source.json`：内置内容包的手写源；
- `docs/workflows/PPT_PRODUCTION.md`：完整 PPT 黄金手册；
- `docs/workflows/VIDEO_PRODUCTION.md`：完整视频黄金手册；
- `contracts/api-surface.openapi.yaml`：当前 active API；
- `contracts/planned-api-surface.openapi.yaml`：尚未提升为 active、但已经冻结名称和语义的 API；
- `contracts/full-chain-freeze.json`：上述事实的并行开发冻结索引；
- `contracts/page-api-fact-matrix.json`：页面动作、operationId、正式事实和恢复方式；
- `contracts/development-leases.json`：并行轨道的写入、只读和禁止边界；
- `contracts/fixtures/contract-freeze/primary-math-two-lessons.json`：双课时 exact 交接样本。

任何说明文档、原型或分支代码与这些机器事实冲突时，以机器合同和不可变 Release 为准。

## 3. 固定产品作用域

```text
一个 Project = 一个完整教材范围或知识点项目
Project 下包含一个或多个 LessonUnit
每个 LessonUnit 独立拥有：
- 教案
- 三类九套与唯一 IntroSelection
- PPT
- 完整课堂导入视频
```

所有课时级产物必须绑定：

```text
organization_id
project_id
lesson_id / lesson_unit_id
content_release_id
workflow_definition_version_id
exact source version id
content hash
```

禁止以“项目最新教案”“最新三类九套”“最新图片”作为下游输入。跨课时读取、替换或 stale 传播必须失败关闭。

## 4. 冻结节点图

### 4.1 教材、课时、教案和三类九套

```text
material.file_validate
→ material.parse
→ material.scope_review
→ lesson.division.generate
→ lesson.division.validate
→ lesson.division.approve
→ LessonUnit sync

每个 LessonUnit：
├── lesson_plan.generate
│   → lesson_plan.validate
│   → lesson_plan.approve
│   → 完整 PPT
└── intro.generate_options
    → intro.validate
    → intro.approve
    → intro.select
    → 完整视频
```

### 4.2 完整 PPT

```text
ppt.content_analyze
→ ppt.outline.generate
→ ppt.outline.approve
→ ppt.pages.generate
→ ppt.cover.prompt.generate
→ ppt.cover.image.generate
→ ppt.cover.approve
→ ppt.style_contract.build
→ ppt.body_asset_prompts.generate
→ ppt.body_assets.generate
→ ppt.pages.assemble
→ pptx.export
→ ppt.final.validate
→ ppt.final.approve
```

不得压缩为“教案直接生成 PPTX”。正文白底、封面视觉合同、独立图片资产、可编辑教学信息、确定性装配和最终 PPTX 校验均属于正式链路。

### 4.3 完整视频

```text
video.master_script.generate
→ video.master_script.approve
→ video.rough_storyboard.generate
→ video.rough_storyboard.approve
→ video.style_master.prompt.generate
→ video.style_master.image.generate
→ video.style_master.approve
→ video.asset_inventory.generate
→ video.asset_prompts.generate
→ video.assets.generate
→ video.fine_storyboard.generate
→ video.shots.generate
→ video.clips.select
→ audio.plan.generate
→ audio.tts.generate
→ audio.subtitles.compile
→ video.timeline.assemble
→ video.classroom_quality.evaluate
→ video.technical.validate
→ video.final.approve
```

视频唯一课程输入是 exact `IntroSelection` 的不可变快照。视频不得重新读取完整教案、教材正文或 PPT，也不得自行重新选择九套方案。

完整视频必须保留母版剧本、粗分镜、视觉母图、四类图片资产、细分镜、逐 shot 候选、正式 clip、TTS、字幕、时间线、最终 MP4、课堂质量和技术质量。不得以单镜头或无音频最小切片替代正式链路。

### 4.4 交付包

```text
delivery.package
```

交付包只消费同一项目、同一课时下的 exact 已批准教案、三类九套事实、PPT 和视频，生成带版本与哈希的交付清单。交付包不得修复或重新解释上游内容。

## 5. 前端消费规则

前端必须围绕以下事实链设计，而不是围绕一次 HTTP 请求设计：

```text
NodeRun
→ GenerationJob / SSE
→ GenerationAttempt / Usage
→ ArtifactVersion 或 FileAssetVersion
→ ArtifactQualityReport
→ Approval / IntroSelection / Adoption
→ 下游 exact input
```

必须区分：

```text
请求已接受
≠ Provider 已完成
≠ Artifact 已提交
≠ 质量通过
≠ 教师批准
≠ 可供下游消费
```

前端只允许使用 active OpenAPI 生成的 TypeScript 客户端。planned operation 在提升为 active 前只能用于类型和开发排期，不得伪装成生产可调用接口。

刷新恢复必须从正式 API 和 PostgreSQL 事实重建，不得依赖 localStorage、内存状态、MSW 或页面自行推断。

## 6. 黄金测试规则

模型结果不做全文逐字比较。每个节点至少验证：

1. 输出符合 ContentDefinition / JSON Schema；
2. 只读取允许的 exact 上游；
3. 项目、课时、Release、Workflow 和内容哈希血缘一致；
4. 通过黄金手册质量断言；
5. 修改一个 LessonUnit 不影响同项目其他 LessonUnit；
6. 上游替换后，仅真实依赖的下游进入 stale；
7. 模型、图片、视频和 TTS 候选不自动等于正式采用结果。

双课时 Fixture 是并行开发的公共输入，不是假装真实 Provider 已运行。真实图片、视频、TTS、PPTX 和 MP4 仍必须在对应里程碑使用真实 Provider 与文件探针验收。

## 7. 变更规则

- `1.0.0` 至 `1.4.0` 及既有项目绑定不可原地修改；
- 对节点输入、输出、Prompt、validator、批准或持久化语义的修改必须前向发布新 ContentRelease；
- active OpenAPI、生成客户端、内容 Release 和公共 Workflow/Artifact/Job 合同同一时刻只能有一个写入所有者；
- 前端、PPT 和视频轨道需要改变共享合同，必须先提交 Contract Change，由合同所有者修改并合并；
- 任一分支不得创建别名节点、别名 DTO、第二套任务状态机或第二套正式资产真源。

## 8. 开放并行的门禁

只有以下检查全部通过，才能全面恢复并行：

- `python scripts/check_contract_freeze.py`；
- `pytest tests/contract/test_contract_freeze.py`；
- 内容包、48 节点目录、黄金项目、OpenAPI 和生成客户端原有门禁；
- 双课时隔离与 exact 交接断言；
- 独立只读工程审查和教学合同审查 P0/P1 清零；
- 冻结 PR 合并到最新 `main`。

冻结 PR 只建立并行开发前置，不宣称完整 PPT 或完整视频运行时已经实现。各轨道的真实实现和真实 Provider 验收仍在冻结后分别完成。