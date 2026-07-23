# 跨前后端合同

本目录保存前端、后端和内容运行时共同依赖的唯一现行机器合同。设计说明见 `docs/backend/05_API_SSE权限与安全.md`，本目录文件优先用于代码生成、Mock 和 CI 校验。

当前业务切片还必须遵守[Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)的纵向交付门禁：active合同表示运行时可调用，不等于教师功能已经完成。只有FastAPI运行时、生成客户端、生产页面消费者、正式持久化事实和真实API浏览器验收共同通过，当前业务切片才能关闭。

## 文件

- `api-conventions.md`：HTTP、分页、并发、幂等和错误约定。
- `api-surface.openapi.yaml`：当前真实可调用的联调面；operationId与后端运行时OpenAPI必须双向一致，也是生成客户端和Mock消费者的唯一API来源。
- `planned-api-surface.openapi.yaml`：尚未注册到运行时的规划接口，只用于产品和工程追踪，不参与客户端生成、Mock运行或当前可用性声明。
- `error-envelope.schema.json`：统一错误响应。
- `sse-event.schema.json`：统一事件信封。
- `creation-lifecycle-event.schema.json`：提示词版本、候选采用、项目写回和下游stale传播事件。
- `workflow-node-status.schema.json`：节点状态枚举。
- `intro-option-set.schema.json`：课程驱动的一套/三类九套导入设计、0/1 exact来源版本和课程追溯。
- `ppt-page-spec.schema.json`：PPT逐页四层结构、白底和可编辑内容合同。
- `video-shot.schema.json`：细分镜、垫图引用和6至30秒逻辑生成合同。
- `creation-package.schema.json`：项目导入通用创作台的不可变包；兼容旧包，2.0包强制工作流来源、上下文快照和目标槽位。
- `content-definition.schema.json`：动态内容字段树。
- `material-evidence-package.schema.json`：教材PDF页级文本块、图片引用和来源追溯合同。
- `content-package-manifest.schema.json`：可导入内容包的版本、条目、路径、Schema和哈希清单。
- `content-item.schema.json`：内容项共同信封。
- `input-definition.schema.json`：教师输入、系统补全、上下文注入、UI可见性和跨字段条件要求。
- `style-preset.schema.json`：图片、视频和PPT的视觉语言及模态扩展。
- `prompt-template.schema.json`：业务Prompt分层、Context白名单和教师修订策略。
- `projection-template.schema.json`：结构化事实到完整提示词和教师可读文档的确定性投影。
- `generation-template.schema.json`：输入、风格、Prompt、输出、投影和逻辑能力的组合。
- `builtin-generation-source.schema.json`：仓库内置业务生成源的紧凑声明合同；由确定性构建器展开为可发布内容包。
- `golden-courseware-case.schema.json`：黄金教材、教案、三类九套、PPT、视频、音频和交付期望的跨成果测试合同。
- `delivery-slice.schema.json`：生产页面、active API、正式持久化事实和真实测试的单行纵向交付证据合同。
- `delivery-slices/`：按`<issue>-<slice>.yaml`保存当前纵向切片回归清单；PR正文证据并集必须与清单一致。
- `workflow-node-generation-binding.schema.json`：v2业务节点执行类型、48节点显式拓扑、必需/可选输入、生成模板、validator descriptor、三类参考策略、Artifact/CreationPackage输出投影、质量报告和人工/策略门禁的声明式绑定目录。
- `markdown-template-draft.schema.json`：普通Markdown导入后的可审核模板草稿。
- `markdown-template-compilation-profile.schema.json`：已审核模板草稿编译为内容包时的显式发布配置。
- `mock-scenarios.json`：前端必须覆盖的关键 Mock 场景。
- `fixtures/stage0/`：项目、上传、任务、工作流聚合、错误和SSE的确定性合同样例。
- `fixtures/creation-lifecycle/`：project/standalone批次、提示词版本、采用、项目写回、CreationPackage 2.0和stale事件样例。
- `fixtures/workflow-node-generation-bindings/`：覆盖教材、课时、教案、三类九套、PPT、图片、视频、音频和交付的48节点完整脱敏目录样例（22个`model_generation`、13个`deterministic`、13个`human_gate`）。
- `fixtures/primary-math-courseware-package/`：由内置生成源确定性展开的首套小学数学业务内容包；22个模型节点均有输入、Prompt、输出、投影和生成模板。
- `fixtures/golden-projects/`：不包含原教材和媒体文件的脱敏黄金项目；固定可复现实例、上下文隔离、跨成果质量不变量和分支可消费的精确规划输出。
- `generated/`：由当前OpenAPI确定性生成的bundle和TypeScript类型，不是第二份手工合同。
- `typescript/client.ts`：基于生成paths和openapi-fetch的共享客户端工厂。

上述首套业务内容包的人类可读确定性投影位于`docs/workflows/generation-guide/`。它供产品负责人、内容管理员和开发者审查，不是第二套机器合同，也不是教师公共界面。

## 当前切片激活规则

- 新业务operation进入active前，必须有FastAPI运行时实现、合同测试和明确的当前消费者；仅有未来页面需求时保留在planned合同。
- active合同变化必须同步生成bundle和TypeScript客户端；生成后有diff即阻塞合并。
- 前端消费者不得通过手写DTO、未声明字段、静态Mock或known-ID深链绕过缺失合同。
- 后端端点通过单元测试不代表业务切片完成；当前父Issue还必须提供生产页面消费、PostgreSQL事实和真实API Playwright证据。
- Session、授权和CSRF属于写操作合同的一部分；前端Token注入不能替代服务端校验。
- PR声明的operationId必须来自active OpenAPI标准HTTP方法；`x-*`扩展、planned operation或未被运行时和当前消费者共同使用的名称不能作为完成证据。
- 改变生产交付边界的PR必须同时改变一份`delivery-slices/<issue>-<slice>.yaml`，使页面路由、真实导航、API方法/路径、正式事实和精确测试选择器在同一行绑定；机器只核验结构、一致性和实际执行，业务断言的充分性仍由独立评审确认。
- 发布Release、Artifact审核、统一Job/NodeRun状态和项目写回语义只有一个活动所有者，不得由并行分支分别扩展。

## 使用规则

1. 前端只从`api-surface.openapi.yaml`生成API类型，不手写第二套DTO，也不得消费`planned-api-surface.openapi.yaml`。
2. 后端 CI 校验响应和事件符合 Schema。
3. 破坏性变更必须同时修改调用方、测试、迁移和本文档，不另建补丁说明。
4. 未在合同中定义的供应商字段只能停留在后端适配层，不能泄漏为前端依赖。
5. Schema ID 和枚举值一经发布不得改变语义。
6. 内容包导出稳定键、类型、版本和语义哈希，不导出数据库UUID、密钥、平台安全层正文、Provider私有参数、项目数据或运行快照。
7. 教师公共界面只获得一段完整、可修改的业务提示词；内部模板、handbook、Context装配细节、输出Schema、校验修复和Provider格式只保存在服务端，不进入教师公共投影。
8. Markdown只作为管理员导入与预览格式；发布前必须编译为结构化内容定义，不能直接成为运行时事实源。
9. 教师提示词修订不能改变字段、类型、必填项和十段/十二段等结构；结构调整只能由管理员发布新的不可变内容与生成模板版本。
10. 节点未显式声明Context或参考资产时一律禁止装配；规范资料、结构化Context和媒体参考资产必须分别校验与快照。
11. 用户侧执行方式只允许`automatic/guided`，二者必须引用同一个WorkflowDefinition；节点级暂停策略不能形成第三套模式或复制项目数据。
12. 创作批次必须通过判别字段区分`project/standalone`：项目来源必须引用不可变CreationPackage及固定目标槽位，独立来源不得伪造项目、工作流或节点上下文。
13. `save_prompt_version`、`generate`、`adopt`和`save_to_project`是四个独立合同；采用不等于写回项目，保存提示词版本不触发生成。
14. 项目来源只能写回创作包固定项目与槽位；独立来源写回项目必须显式提交目标、重新鉴权并保存授权快照。
15. 旧`manual/assisted/automatic`和旧创作端点必须通过显式兼容与弃用周期迁移；已发布策略快照不改写，客户端未迁移完成前不得删除旧值或静默改变含义。
16. 新客户端通过`AutomationPolicyMode`、`source_kind`和四个独立创作动作接入；旧`AutomationMode`及候选直接写回入口只用于兼容，并在OpenAPI中标记`deprecated`。

## 本地命令

```powershell
pnpm install --frozen-lockfile
pnpm contracts:lint
pnpm contracts:surface
pnpm contracts:generate
pnpm contracts:typecheck
pnpm contracts:test
pnpm contracts:check-generated
```

检查Markdown模板草稿和规范化预览：

```powershell
uv run python scripts/inspect_markdown_template.py contracts\fixtures\markdown-template\math-comic-lesson.md --format json
uv run python scripts/inspect_markdown_template.py contracts\fixtures\markdown-template\math-comic-lesson.md --format markdown
```

将管理员已确认且状态为`ready`的TemplateDraft编译为#38内容包：

```powershell
uv run python scripts/compile_markdown_template.py <ready-draft.json> --profile contracts\fixtures\markdown-template\math-comic-compilation-profile.json --output "$env:TEMP\shanhai-compiled-template"
uv run python scripts/validate_content_package.py "$env:TEMP\shanhai-compiled-template"
```

编译命令使用操作系统原子 no-replace 发布语义，拒绝已有路径、断链符号链接和最终发布瞬间出现的竞争目标；协作锁只负责同类编译任务互斥，不作为防覆盖安全边界。`ready-draft.json`来自后续管理端审核流程，不允许把解析器生成的`needs_review`草稿直接改状态后自动发布。

首次更新依赖锁时运行 `pnpm install`。修改OpenAPI后必须重新生成并提交 `contracts/generated/`；CI会拒绝生成漂移和未声明的破坏性变更。

校验脱敏生成模板示例包：

```powershell
uv run python scripts/update_content_package_hashes.py contracts\fixtures\generation-template-package
uv run python scripts/validate_content_package.py contracts\fixtures\generation-template-package
uv run pytest tests\contract\test_generation_template_contracts.py
```

校验全流程节点绑定目录：

```powershell
uv run python scripts\validate_workflow_node_catalog.py contracts\fixtures\workflow-node-generation-bindings\primary-math-courseware.json
uv run pytest tests\contract\test_workflow_node_generation_binding.py
```

构建并校验首套内置业务内容包与黄金项目：

```powershell
uv run python scripts\build_builtin_generation_package.py workflow\builtin\primary_math_courseware\generation-source.json <空输出目录>
uv run python scripts\render_builtin_generation_guide.py --check
uv run python scripts\validate_content_package.py contracts\fixtures\primary-math-courseware-package
uv run python scripts\validate_golden_courseware.py contracts\fixtures\golden-projects\numbers-1-to-5\golden-project.json
uv run python scripts\validate_golden_courseware.py contracts\fixtures\golden-projects\numbers-1-to-5\golden-project.json --source-pdf <受控本地教材PDF>
uv run pytest tests\contract\test_golden_courseware_package.py
```

`scripts/golden_courseware_branch_inputs.py` 将跨成果聚合数据确定性投影为教案、PPT和视频分支入口，以及16个符合各自 `ContentDefinition` 的规划型节点输出；`scripts/golden_courseware_stage_inputs.py` 继续连接不依赖真实媒体的内部阶段。其余7个节点依赖真实图片、视频、TTS文件或最终媒体质检，只保留合同和Provider门禁，不在黄金Fixture中伪造候选文件、SHA或质量报告。

普通CI只运行脱敏Fixture和确定性构建，不要求教材原件或真实Provider。传入受控本地PDF的命令额外核验SHA-256、总页数和黄金页段；真实文本、图片和视频仍属于对应适配器任务与里程碑出口。TTS当前只保留计划数据，待音频Provider可用后独立验收。
