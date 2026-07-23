# 前端交接与状态模型

责任人：前端承接方
读者：前端、联调、测试与产品
规范路径：`apps/web/docs/FRONTEND_HANDOFF.md`
替换规则：路由、组件边界或状态合同变化时原位更新，不新增版本副本。

## 页面清单

| 入口                                                       | Runtime 页面                 | 当前能力与 adapter 边界                                      |
| ---------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------ |
| `/`                                                        | `Navigate`                   | 重定向到 `/app`                                              |
| `/login`                                                   | `RuntimeLoginPage`           | 认证路径待 #11 决策；仅显示安全说明                          |
| `/app`                                                     | `HomePage`                   | 项目摘要；real API 与 DEV MSW 都通过 `projectsApi`           |
| `/app/projects`                                            | `ProjectsPage`               | 项目分页、搜索与新建入口                                     |
| `/app/projects/new`                                        | `RuntimeNewProjectPage`      | 教材上传或无教材创建；DEV MSW 只替换网络响应                 |
| `/app/projects/:projectId/setup?jobId=...`                 | `RuntimeProjectSetupPage`    | Job 查询/取消、SSE、轮询和刷新恢复                           |
| `/app/projects/:projectId`                                 | `RuntimeProjectOverviewPage` | 项目、课时、制作方式和项目 SSE                               |
| `/app/projects/:projectId/materials/:materialId?`          | `RuntimeMaterialsPage`       | 已知 ID 时读取教材与解析；无 ID 时显示发现合同缺口           |
| `/app/projects/:projectId/lessons`                         | `RuntimeLessonsPage`         | 课时重排、软归档、字段与分支读取/编辑                        |
| `/app/projects/:projectId/assets`                          | `RuntimeAssetsPage`          | 分页素材读取，以及已有服务端素材绑定/解绑与幂等重试          |
| `/app/projects/:projectId/artifacts/:artifactId`           | `RuntimeArtifactPage`        | 已知 ID 时只读状态；没有安全字段/权限合同时阻断全部写动作    |
| `/app/projects/:projectId/jobs/:jobId`                     | `RuntimeJobPage`             | Job REST/SSE、轮询、取消与刷新恢复                           |
| `/app/projects/:projectId/lessons/:lessonId/work/:stepKey` | `RuntimeLessonWorkbenchPage` | 读取项目/课时；缺课时/教案生成命令时显示明确阻塞             |
| `/app/creation`                                            | `CreationHomePage`           | 独立图片、视频、PPT 创作入口，不依赖项目                     |
| `/app/creation/:studioPath`                                | `CreationStudioPage`         | 创建 standalone 批次；响应无 CreationItem 时停止，不启动生成 |
| `/app/projects/:projectId/*`                               | `RuntimeUnavailablePage`     | 未接入项目子页的安全 fallback                                |
| `/app/tasks`                                               | `RuntimeUnavailablePage`     | 缺项目级或全局 Job 发现合同                                  |
| `/admin/*`                                                 | `RuntimeUnavailablePage`     | 管理端尚未接入真实页面                                       |
| `*`                                                        | `RuntimeUnavailablePage`     | 全局安全 fallback                                            |

## 组件清单

- 基础控件：`Button`、`IconButton`、`Select`、`StatusBadge`、`EmptyState`。
- 全局布局：`AppShell` 是产品壳；`RuntimeAppShell` 只提供“当前用户”文字及空搜索/通知的安全占位，不代表真实账号、搜索或通知已接入。
- 工作台：`LessonWorkbenchSummary`、`WorkbenchStatusBoard`、`WorkbenchPageFrame`、`MarkdownDocument`、`MarkdownPreview`、`PptCoverArtwork`。
- 项目：`ProjectEntryFrame`、`ProjectEntryForm`、`ProjectRow`、`ProjectLessonGrid`、`ProjectOverviewContent` 是数据源无关展示组件；页面只负责查询、提交、恢复和字段事件映射。
- Runtime 合同组件：`MaterialDetailsPanel`、`LessonCollectionEditor`、`ArtifactWorkbench`、`ProjectAssetSlotsPanel`、`GenerationJobPanel` 只接收生成 DTO、展示状态和用户意图回调，不直接发请求或读取网络 adapter。
- 创作组件：`CreationComposer`、`CreationSetupPanel`、`GenerationJobPanel` 与运行时边界提示由 `CreationStudioPage` 组合；`CreationResultsPanel` 只在获得真实 result 读取合同后才能承载生产结果。
- 内容渲染：`ContentDefinitionRenderer` 只按传入字段定义渲染；Runtime Artifact 页在字段/权限合同缺失时不调用本地定义补位。

## Runtime 与 DEV adapter 边界

`src/app/App.tsx` 始终只加载 `RuntimeApp`。`main.tsx` 只有在开发环境且 `VITE_API_MODE=mock` 时才动态启动 MSW；real 模式和生产构建不加载 Worker。两种模式共用完全相同的路由、页面、类型化客户端和用户意图，差异只在网络 adapter。DEV handlers 不创建浏览器认证、本地业务写入函数或前端任务计时器。

Runtime 页面只消费 `features/*/api` 的类型化客户端和 TanStack Query。`ProjectEntryFrame`、`ProjectEntryForm`、`ProjectLessonGrid`、`ProjectRow`、`LessonWorkbenchSummary`、`WorkbenchStatusBoard` 及上述 Runtime 合同组件不读取 API 或 MSW；Storybook 与页面 adapter 都通过 props 和用户意图回调驱动它们。颜色、图标和语义文案只在共用组件中维护。

## 前端状态模型

| 状态层       | 责任                                                                 | 持久化                                      |
| ------------ | -------------------------------------------------------------------- | ------------------------------------------- |
| 服务端资源   | 项目、课时、workflow、任务、素材和产物的事实状态                     | PostgreSQL，经 REST/SSE 返回                |
| 查询缓存     | 请求状态、失效、重试和页面读取                                       | TanStack Query，标签页内存                  |
| UI 状态      | 抽屉、主题、侧栏、当前筛选、焦点，以及正式响应中的创作 item/Job 标识 | Zustand/React state；创作标识不承诺刷新恢复 |
| 编辑恢复     | 新建项目表单、PDF 元数据、SHA-256、幂等意图、上传会话、Job ID        | `sessionStorage`，不保存或伪造 `File`       |
| DEV 合同场景 | 只为同一 Runtime 页面返回确定性 OpenAPI 响应，不维护第二套业务真相   | MSW Worker 生命周期内；禁止作为生产证据     |

合同资源状态必须分别处理，不能把不同资源的同名或近义状态合并成浏览器业务真相：

| 资源                           | OpenAPI 状态                                                                                                                                                                                  | 前端处理规则                                                   |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `Project`                      | `draft`、`active`、`archived`                                                                                                                                                                 | 项目页以 REST 快照为真；项目 SSE 只触发相关查询失效            |
| `AutomationPolicy`             | `guided`、`automatic`                                                                                                                                                                         | 以独立 REST 资源和 ETag 为真；不得从项目旧字段或 UI 选择推导   |
| `FileAsset`                    | `pending`、`active`、`rejected`                                                                                                                                                               | 文件资产 REST 为真；不得把上传确认或解析成功等同于资产可用     |
| `FileAssetVersion.scan_status` | `pending`、`clean`、`rejected`                                                                                                                                                                | 扫描状态独立显示；只有 `clean` 才能满足要求清洁扫描的素材合同  |
| `MaterialParseVersion`         | `pending`、`running`、`succeeded`、`failed`                                                                                                                                                   | 解析版本 REST 为真；Job 事件只触发重新读取，不反推解析终态     |
| `Lesson`                       | `active`、`archived`                                                                                                                                                                          | 课时集合/单课时 REST 为真；软归档不能由列表缺失推导            |
| `LessonBranch`                 | `enabled: boolean`；`workflow_status: disabled`、`not_ready`                                                                                                                                  | 分支配置与节点运行状态分开；不得由启用状态伪造生成已就绪       |
| `GenerationJob`                | `created`、`queued`、`running`、`succeeded`、`failed`、`cancel_requested`、`cancelled`                                                                                                        | Job REST 为真；传输错误不推断失败或解锁重复生成，终态停止取消  |
| `WorkflowRun`                  | `active`、`paused`、`completed`、`failed`、`cancelled`                                                                                                                                        | 当前合同只有项目级读取；没有启动或推进命令时不得显示可执行操作 |
| `NodeRun`                      | `disabled`、`not_ready`、`ready`、`draft`、`queued`、`running`、`review_required`、`approved`、`partially_completed`、`failed`、`paused`、`cancel_requested`、`cancelled`、`stale`、`skipped` | 保留原始节点状态；展示映射不得反写服务端对象                   |
| `Artifact`                     | `draft`、`in_review`、`approved`、`stale`、`archived`                                                                                                                                         | 只读服务端状态；内容字段与权限不可解析时不开放任何版本写动作   |
| `ProjectAssetSlot`             | `empty`、`satisfied`                                                                                                                                                                          | 槽位 REST 为真；绑定/解绑响应后重新读取，不按本地数组推导状态  |
| `CreationBatch`                | `draft`、`ready`、`running`、`partially_completed`、`completed`、`archived`                                                                                                                   | standalone 创建当前返回空 `items`；缺少 GET 时不能刷新恢复     |
| `CreationItem`                 | `draft`、`ready`、`generating`、`review_required`、`adopted`、`saved`、`failed`                                                                                                               | active OpenAPI 无创建端点；没有服务端 item 时禁止调用后续写链  |

状态显示必须区分 `loading`、`empty`、`error`、`queued`、`running`、`review_required`、`partially_completed`、`approved` 和 `failed`。成功与失败不能只依赖颜色，必须同时显示图标和文字；加载时禁止重复提交，并支持 `prefers-reduced-motion`。

## Storybook 覆盖

Storybook 覆盖基础控件、`AppShell`、项目来源入口、项目行、课时概览、工作台总览、动态教案字段、创作输入与结果、保存冲突、PPT 封面、视频关键帧，以及教材解析、课时集合编辑、Artifact、素材槽位和 Generation Job 等 Runtime 纯展示组件。适用组件分别覆盖加载、空态、错误、409 冲突、进行中、部分成功、失败、取消和完成；所有 fixture 都是确定性合同对象，不读取 MSW 或启动假任务。

PPT 与视频的进行中、部分成功和完成包装目前只用于 Storybook 的确定性视觉 fixture；正式生成、页级或镜头级状态、预览和下载端点仍被 #108/#11 阻塞，因此这些 story 不构成 Runtime 页面或生产完成声明。合同进入 active OpenAPI 后，应由对应 Runtime 页面复用同一纯展示组件并删除 story 内的临时状态包装。

`test:storybook:a11y` 会枚举静态 Storybook 中的全部 story，在 1440 宽度运行 axe WCAG 2A/AA、横向溢出、内部制作词泄漏、控制台异常、页面异常、错误壳与空渲染根检查；带 `core-viewport` 标签的核心 story 还会实际把 Playwright viewport 切换到 1024 和 390 后重复检查。Storybook 的 `Narrow390` 参数仅用于人工预览，不代替上述自动门禁。

## 测试与联调计划

1. 单元与组件：`pnpm --dir apps/web test`，变更文件先用 Vitest 定向运行。
2. 静态门禁：format、lint、typecheck、生产构建、Storybook build 和 `test:storybook:a11y`。
3. DEV MSW 浏览器：`contract-preview.spec.ts` 在 1440、1024、390 验证同一 Runtime 路由、基础可访问性、横向溢出、登录阻断和未声明请求拒绝；视觉回归也只访问 Runtime 路由。
4. Runtime 浏览器：合同桩场景覆盖首页/项目概览、教材上传恢复与读取、空课时合同阻断、课时集合与分支写入、课时工作台缺少生成命令时的阻断、素材读取/绑定/解绑、Artifact 只读状态与写操作阻断、Job REST/SSE/取消/失败、项目 SSE、无教材课程锚点、standalone 创作批次空 `items` 阻断，以及 CSRF 缺失安全失败；该创作场景断言提示词、生成、Job REST 和 Job SSE 请求均为 0。
5. 发布前检查构建产物不得包含 MSW Worker、本地业务运行时标识、开发凭据或合同测试入口。

## 交接阻塞

真实登录/bootstrap 的端点路径尚未形成合同，由 #11 决策，前端不发明 `/auth/*`。教材缺 `GET /projects/{project_id}/materials`，Artifact 缺 `GET /projects/{project_id}/artifacts`，Generation Job 缺项目级或全局列表合同，因此这些资源只能从已知 ID 深链进入，`/app/tasks` 保持阻塞。课时合同只有 `GET/PATCH /projects/{project_id}/lessons`、`GET /lessons/{lesson_id}`、`PATCH /lessons/{lesson_id}/branches` 和只读 workflow；缺 planned `POST /node-runs/{node_run_id}/start`，课时划分与教案生成不可启动。独立创作入口保持开放且不依赖项目，但 `POST /creation-batches` 的 standalone 响应当前为 `items: []`，active OpenAPI 没有 CreationItem 创建端点（路径待 #11 决策）；页面创建真实批次后立即停止，不保存提示词、不调用生成，也不启动 Job。另缺 `GET /creation-batches/{batch_id}`、`GET /creation-items/{item_id}` 和 `GET /generation-results/{result_id}`，因此刷新恢复、候选预览、采用和保存到项目也保持阻断。

正式 PPT 缺 `GET /lessons/{lesson_id}/ppt`、`PATCH /ppt-pages/{page_id}`、`POST /ppt-documents/{id}/render` 与 PPTX Artifact 下载关系，由 #108/#11 跟踪。视频缺 `GET /lessons/{lesson_id}/video`、`PATCH /video-shots/{shot_id}`、`POST /video-shots/{shot_id}/select-clip`、`POST /video-projects/{id}/assemble`；交付缺 `GET/POST /projects/{project_id}/deliveries`，由 #11 跟踪。上述页面均保持安全阻塞，不用 Storybook fixture 或 DEV handler 补造生产能力。

active OpenAPI 已提供 `GET /lessons/{lesson_id}/intro-options`、`POST /lessons/{lesson_id}/intro-selections` 与 `GET /node-runs/{node_run_id}/prompt-preview`，但当前 Runtime 页面尚未消费。deprecated 的 `POST /generation-results/{result_id}/save-to-project` 故意不封装，新前端只使用 adoption 与原子写回两个独立端点。

Artifact 已有 `GET /artifacts/{artifact_id}`，响应包含 `content_definition_version_id` 以及草稿/版本的不透明 `content`；写合同也已有 `PUT /artifacts/{artifact_id}/drafts/{draft_branch}`、`POST /artifacts/{artifact_id}/versions` 和 `POST /artifact-versions/{artifact_version_id}/approvals`。但 active OpenAPI 没有 `GET /projects/{project_id}/artifacts`，也没有使用 `content_definition_version_id` 读取字段定义与当前用户编辑/审核权限的 Runtime 端点。生产页因此只读版本状态，不展示裸 JSON，不用本地定义伪造草稿，并阻断草稿保存、版本提交和批准；该页面阻塞关联 #11。

现行 `CreateProjectRequest` 与 `Project` 没有 `source_mode`，因此创建后的项目详情无法可靠显示“教材/无教材”来源；也没有为既有无教材项目发现、追加并恢复教材流程的页面合同。前端只允许本次无教材创建继续，不在浏览器补造来源事实；来源持久化与后补教材入口由 #11 跟踪。本文件不把确定性 Fake、DEV fixture 预览或合同测试网络桩写成生产能力。
