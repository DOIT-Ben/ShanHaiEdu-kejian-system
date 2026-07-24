# 路由、页面、组件与 API 映射

责任人：前端承接方
读者：前端、后端联调与测试人员
规范路径：`apps/web/docs/ROUTES_AND_API.md`
替换规则：现行路由或合同变化时原位更新

## 应用入口

`src/app/App.tsx` 始终只加载 `RuntimeApp`。`main.tsx` 是唯一网络 adapter 选择点：

- Vite 开发环境且 `VITE_API_MODE=mock` 时动态启动 MSW 合同 handlers；
- 生产构建、预览构建或 `VITE_API_MODE=real` 时不加载 MSW；
- 两种模式共用相同页面、路由和类型化客户端，请求失败不会回退到浏览器本地业务状态。

## RuntimeApp 路由

下表是 `RuntimeApp` 当前真正开放的唯一业务路由树。DEV MSW 模式只替换网络 adapter，不会加载第二套路由或页面。

| 路由                                                       | 页面/布局                      | 当前真实能力                                                        |
| ---------------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------- |
| `/`                                                        | `Navigate`                     | 重定向到 `/app`                                                     |
| `/login`                                                   | `RuntimeLoginPage`             | 受控访问码调用真实 Session API；不保存浏览器身份                    |
| `/app`                                                     | `RuntimeAppShell` + `HomePage` | 品牌首页、真实项目摘要；创作入口禁用                                |
| `/app/projects`                                            | `ProjectsPage`                 | 分页查询项目、前端搜索、新建入口                                    |
| `/app/projects/new`                                        | `RuntimeNewProjectPage`        | 教材 PDF 三段式上传或无教材课程锚点创建                             |
| `/app/projects/:projectId/setup?jobId=...`                 | `RuntimeProjectSetupPage`      | Job 查询/取消、Job SSE、轮询恢复；成功后只读取已有课时              |
| `/app/projects/:projectId`                                 | `RuntimeProjectOverviewPage`   | 项目、课时、AutomationPolicy 和项目 SSE                             |
| `/app/projects/:projectId/materials/:materialId?`          | `RuntimeMaterialsPage`         | 已知 material ID 时读取文件与解析版本；缺 ID 时说明无法发现教材记录 |
| `/app/projects/:projectId/lessons`                         | `RuntimeLessonsPage`           | 课时字段、顺序、软归档与分支编辑，使用 ETag/`If-Match`              |
| `/app/projects/:projectId/assets`                          | `RuntimeAssetsPage`            | 分页读取槽位/素材包；仅绑定来自已有服务端结果的素材                 |
| `/app/projects/:projectId/artifacts/:artifactId`           | `RuntimeArtifactPage`          | 已知 Artifact ID 时只读版本状态；字段/权限合同缺失时阻断全部写动作  |
| `/app/projects/:projectId/jobs/:jobId`                     | `RuntimeJobPage`               | Job REST/SSE、取消、轮询与刷新恢复                                  |
| `/app/projects/:projectId/lessons/:lessonId/work/:stepKey` | `RuntimeLessonWorkbenchPage`   | 读取项目和单课时；缺少生成命令时显式显示不可用                      |
| `/app/projects/:projectId/*`                               | `RuntimeUnavailablePage`       | 后续项目页面的安全不可用态                                          |
| `/app/creation/*`                                          | `RuntimeUnavailablePage`       | 创作中心尚未接入真实页面                                            |
| `/app/tasks`                                               | `RuntimeUnavailablePage`       | 全局任务页尚未接入真实页面                                          |
| `/admin/*`                                                 | `RuntimeUnavailablePage`       | 管理端尚未接入真实页面                                              |
| `*`                                                        | `RuntimeUnavailablePage`       | 全局安全 fallback，不推导或伪造业务资源                             |

`SessionProvider` 在应用启动时调用 `GET /auth/session` 恢复 HttpOnly Cookie 对应的公共教师、组织、Session 和 CSRF 状态；`RuntimeAppShell` 只消费该状态并在匿名时返回 `/login`。浏览器不读取 Cookie，不用 `localStorage` 或 `sessionStorage` 伪造身份。

## DEV MSW 合同适配器

开发环境且 `VITE_API_MODE=mock` 时，`main.tsx` 动态加载 MSW handlers，为同一个 `RuntimeApp` 路由树提供确定性合同场景。页面、组件、路由和用户意图与 real 模式相同；差异只在网络 adapter。handlers 不创建浏览器认证、本地业务状态机、前端任务计时器或第二套 DTO，也不会进入生产构建。

## 注册表与基础控件

| 注册表           | 路径                                                        | 当前边界                                          |
| ---------------- | ----------------------------------------------------------- | ------------------------------------------------- |
| `fieldRegistry`  | `features/content-definition/ContentDefinitionRenderer.tsx` | 动态内容字段纯渲染；当前 Runtime 页未伪造字段定义 |
| `studioRegistry` | `features/creation-studio/registry.ts`                      | 未路由创作组件的类型配置，不代表生产创作页已接入  |

- 页面主操作统一使用 `shared/ui/Button.tsx`，尺寸只允许 `sm`、`md`、`lg` 三档；
- 图标操作统一使用 `shared/ui/IconButton.tsx`；
- 下拉选择统一使用基于 Radix Select 的 `shared/ui/Select.tsx`；
- 标准表单控件为 40px，高密度工具栏为 36px，重要操作上限为 44px。

## 类型化 API 客户端

所有合同路径都相对于 `VITE_API_BASE_URL`，默认前缀为 `/api/v2`。前端类型来自 `contracts/generated/typescript/schema.ts`；`apps/web/src/generated/api-schema.ts` 只做类型导出，不维护第二套 DTO。

| 领域           | runtime 合同端点                                                                                                                                                                               | 前端入口                                            | 页面接入状态                                                                      |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------- |
| 教师会话       | `POST/GET/DELETE /auth/session`                                                                                                                                                                | `features/session/api/sessionApi.ts`                | 登录、启动恢复、CSRF 内存注入和退出撤销已接入                                     |
| 项目           | `GET/POST /projects`；`GET /projects/{project_id}`                                                                                                                                             | `features/projects/api/projectsApi.ts`              | 列表、创建、详情已接入 Runtime 页面                                               |
| 制作方式       | `GET/PATCH /projects/{project_id}/automation-policy`                                                                                                                                           | `features/projects/api/automationPolicyApi.ts`      | 项目概览已接入，写入使用 ETag/`If-Match`                                          |
| 教材           | `POST /projects/{project_id}/materials/uploads`；对象存储直传；`POST /projects/{project_id}/materials/{material_id}/confirm`                                                                   | `features/materials/api/materialsApi.ts`            | 上传三段式链已接入新建项目页                                                      |
| 教材读取       | `GET .../file-asset`；`GET .../parse-versions`                                                                                                                                                 | `features/materials/api/materialsApi.ts`            | 已接入已知 material ID 深链；缺项目级教材发现入口                                 |
| 课时           | `GET/PATCH /projects/{project_id}/lessons`；`GET /lessons/{lesson_id}`；`PATCH /lessons/{lesson_id}/branches`                                                                                  | `features/lessons/api/lessonsApi.ts`                | 集合/单课时读取、重排、软归档、字段编辑和分支设置已接入                           |
| Workflow       | `GET /projects/{project_id}/workflow`                                                                                                                                                          | `features/workflow/api/workflowApi.ts`              | 客户端已实现；课时工作台尚未读取节点进度                                          |
| 导入方案       | `GET /lessons/{lesson_id}/intro-options`；`POST /lessons/{lesson_id}/intro-selections`                                                                                                         | 尚未封装                                            | active 合同已有，当前 Runtime 页面尚未消费                                        |
| 提示词预览     | `GET /node-runs/{node_run_id}/prompt-preview`                                                                                                                                                  | 尚未封装                                            | active 合同已有，当前 Runtime 页面尚未消费                                        |
| Artifact       | `POST /projects/{project_id}/artifacts`；`GET /artifacts/{artifact_id}`；`PUT .../drafts/{draft_branch}`；`POST .../versions`；`POST /artifact-versions/{artifact_version_id}/approvals`       | `features/artifacts/api/artifactsApi.ts`            | 类型化客户端已覆盖；页面仅接入详情读取，写端点在内容字段/权限可解析前不可达       |
| 素材槽位       | `GET /projects/{project_id}/asset-slots`；`GET .../asset-package`；`POST /asset-slots/{slot_id}/bindings`；`POST /asset-bindings/{binding_id}/unbind`                                          | `features/assets/api/assetsApi.ts`                  | 游标分页、部分读取保留、已有服务端素材绑定/解绑与模糊失败幂等重试已接入           |
| 创作批次       | `POST /creation-batches`；`POST /creation-batches/{batch_id}/generate`                                                                                                                         | `features/creation-studio/api/creationApi.ts`       | 仅创建客户端已实现；整批生成无可达 Runtime 页面，且缺结果 GET，未增加孤立 wrapper |
| 创作四动作     | `POST /creation-items/{item_id}/prompt-versions`；`POST /creation-items/{item_id}/generate`；`POST /generation-results/{result_id}/adoptions`；`POST /adoptions/{adoption_id}/save-to-project` | `features/creation-studio/api/creationApi.ts`       | 四个独立客户端已实现，Runtime 页面待接入                                          |
| Generation Job | `GET /generation-jobs/{job_id}`；`POST /generation-jobs/{job_id}/cancel`                                                                                                                       | `features/jobs/api/jobsApi.ts`                      | 教材 setup 与独立 Job 深链已接入                                                  |
| SSE            | `GET /projects/{project_id}/events/stream`；`GET /generation-jobs/{job_id}/events/stream`                                                                                                      | `shared/api/useProjectEvents.ts`、`useJobEvents.ts` | Runtime 项目资源页与 Job/setup 页用于 REST 对账                                   |

`shared/api/client.ts` 统一使用 `credentials: include`、标准成功/错误信封和网络错误映射。只有 `createSession` 可在没有既有 CSRF 时启动；其余写操作从 `SessionProvider` 读取当前 Session 绑定的 CSRF，并由各 feature 客户端显式携带 `Idempotency-Key`。真实模式没有 token 时，客户端会在 fetch 前安全失败。

`POST /generation-results/{result_id}/save-to-project` 在 active OpenAPI 中已标记 deprecated。新前端故意不封装该旧入口，只使用“采用候选”与“把 adoption 原子写回项目”两个独立事实端点。

## 合同缺口与页面阻塞

下表只描述当前 `contracts/api-surface.openapi.yaml` 的运行时表面。未定义的操作不会由浏览器、MSW 或本地状态补造。

| 能力                    | 当前精确端点/操作                                                                                                                                                                                                                                                      | 缺失操作与页面阻塞                                                                                                                                                                                               | 跟踪      |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 教材发现                | 已有已知 material ID 的文件与解析结果读取                                                                                                                                                                                                                              | 缺 `GET /projects/{project_id}/materials`；项目页无法发现教材记录，教材页只能从已知 ID 深链进入                                                                                                                  | #11       |
| Job 发现                | `GET /generation-jobs/{job_id}` 与 Job SSE                                                                                                                                                                                                                             | 缺项目级或全局 Generation Job 列表，具体路径待 #11 决策；`/app/tasks` 与项目任务入口无法从项目事实恢复                                                                                                           | #11       |
| 课时与教案生成          | `GET/PATCH /projects/{project_id}/lessons`、`GET /lessons/{lesson_id}`、`PATCH /lessons/{lesson_id}/branches`、`GET /projects/{project_id}/workflow`                                                                                                                   | 缺 planned `POST /node-runs/{node_run_id}/start`；课时划分、教案生成与课时工作台节点启动均不可达                                                                                                                 | #11       |
| 创作结果恢复            | `POST /creation-batches`、`POST /creation-batches/{batch_id}/generate`、`POST /creation-items/{item_id}/prompt-versions`、`POST /creation-items/{item_id}/generate`、`POST /generation-results/{result_id}/adoptions`、`POST /adoptions/{adoption_id}/save-to-project` | 没有 `GET /creation-batches/{batch_id}`、`GET /creation-items/{item_id}` 或 `GET /generation-results/{result_id}`；Runtime 创作页无法在刷新后恢复批次、候选和采用结果                                            | #11       |
| 正式 PPTX               | 只有通用 Artifact 与创作写操作                                                                                                                                                                                                                                         | 缺 `GET /lessons/{lesson_id}/ppt`、`PATCH /ppt-pages/{page_id}`、`POST /ppt-documents/{id}/render` 以及正式 PPTX Artifact 下载关系；PPT 工作台保持阻塞                                                           | #108、#11 |
| 最终视频                | 只有通用创作写操作和 `GenerationJob` 查询                                                                                                                                                                                                                              | 缺 `GET /lessons/{lesson_id}/video`、`PATCH /video-shots/{shot_id}`、`POST /video-shots/{shot_id}/select-clip`、`POST /video-projects/{id}/assemble`；视频工作台保持阻塞                                         | #11       |
| 交付                    | active OpenAPI 没有项目交付资源                                                                                                                                                                                                                                        | 缺 `GET/POST /projects/{project_id}/deliveries`；交付列表、创建、状态查询和下载关系均不可达                                                                                                                      | #11       |
| 内容来源与后补教材      | `POST /projects` 与项目内教材上传/确认端点                                                                                                                                                                                                                             | `CreateProjectRequest`/`Project` 没有 `source_mode`，也没有为既有无教材项目发现、追加并恢复教材流程的页面合同                                                                                                    | #11       |
| Artifact 发现与审核字段 | `GET /artifacts/{artifact_id}` 返回 `content_definition_version_id`、草稿和版本的不透明 `content`；写合同为 `PUT /artifacts/{artifact_id}/drafts/{draft_branch}`、`POST /artifacts/{artifact_id}/versions`、`POST /artifact-versions/{artifact_version_id}/approvals`  | 没有 `GET /projects/{project_id}/artifacts`，也没有使用 `content_definition_version_id` 读取字段定义与当前用户编辑/审核权限的 Runtime 端点；页面不能安全显示待写或待审内容，因此草稿保存、版本提交和批准全部阻断 | #11       |

## 教材上传纵向链

`RuntimeNewProjectPage` 与 `RuntimeProjectSetupPage` 当前按以下顺序调用真实合同，不使用前端计时器伪造进度：

创建入口有两种互斥模式：

- 教材模式：创建项目后建立上传会话、计算 SHA-256、直传 PDF、确认教材并进入解析 Job；
- 无教材模式：仅用年级、可选教材版本、知识点和标题调用 `POST /projects`，创建成功后进入项目概览，不建立上传会话，也不显示虚假的解析进度。

现行 `CreateProjectRequest` 和 `Project` 没有内容来源字段；教材上传也没有“为已有无教材项目补充教材”的页面级读取/恢复口径。因此来源选择只用于决定本次创建是否继续上传，不能在项目详情中持久显示，也不能承诺创建后追加教材。这个合同缺口关联 #11，前端不得用 `sessionStorage` 或本地对象伪造服务端来源事实。

1. 校验 PDF，并在浏览器计算文件 SHA-256；
2. `POST /projects` 创建项目；
3. `POST /projects/{project_id}/materials/uploads` 创建上传会话；
4. 按会话返回的 method、URL 和 required headers 将文件直传对象存储，并读取 ETag；
5. `POST /projects/{project_id}/materials/{material_id}/confirm` 确认文件，取得 Generation Job；
6. 进入 setup 页面，通过 Job REST 快照、Job SSE 和 5 秒轮询读取服务端进度，可取消非终态任务；
7. Job 成功后只读取服务端已有课时；有课时时进入课时页核对，空集合时明确说明当前合同没有课时划分/教案生成命令，并返回项目或教材详情，不暗示后台会自动建立课时。

当前标签页会在 `sessionStorage` 保存表单、文件元数据与 SHA-256、三段幂等意图、项目 ID、上传会话、ETag 和 Job ID。浏览器刷新后不会伪造或恢复 `File` 对象，而是请用户重新选择同一份 PDF，再从已保存的服务端阶段继续。签名上传地址在确认前过期时，前端保留项目并轮换上传与确认意图，重新建立上传会话；若确认请求已经发出，则先保留原上传会话、ETag 和确认幂等键重试，让服务端回放可能已经成功的 Job。只有服务端明确返回 `UPLOAD_REJECTED` 后，前端才轮换上传与确认意图。

这条链已经完成前端实现和确定性测试；#211 的真实 API 门禁已覆盖登录后无教材创建项目，但尚未覆盖反向代理、对象存储直传和完整教材到教案组合环境，不能据此宣布阶段1联调或生产闭环完成。

## SSE 恢复语义

- 使用 Fetch 流并携带 Cookie，允许发送正整数 `Last-Event-ID`；最近 sequence 只保存在当前标签页的 `sessionStorage`；
- 严格校验 SSE `id`、事件名和 JSON 信封中的 `sequence_no`、`event_type`、资源及 payload，丢弃不递增的重复事件；
- 收到事件后只使相关 TanStack Query 失效，再从 REST 读取业务快照；
- 服务端返回 409/`EVENT_HISTORY_EXPIRED` 时清除游标并刷新 REST 快照；
- 网络错误、408、429 和 5xx 按 1 秒到 15 秒指数退避重连；除历史过期外的永久 4xx 停止重连，并执行一次 REST 快照对账；组件卸载时通过 AbortController 清理连接。

## 尚未完成的生产边界

- 三个 Session operationId 和 `SessionProvider` 已接入；生产仍需从受控环境注入映射、HTTPS Cookie、允许 Origin 与可信代理配置并复验；
- 课时/教案生成、创作结果查询恢复、正式 PPTX、最终视频和交付合同仍是 #11/#108 的页面阻塞；
- 即使通用 Workflow、Artifact、素材槽位、创作写操作和 Job 客户端已接入部分 Runtime 界面，完整业务流程仍需真实认证和浏览器验收；
- 后端目前只有 Provider 中立媒体合同和确定性 Fake，真实图片/视频 Adapter 与受控冒烟不属于当前前端已完成能力；
- DEV 合同 fixture、静态素材和视觉预览只能验证版式与前端映射，不能作为真实生成、下载或原子写回的验收证据。

独立的 `playwright.runtime.config.ts` 继续用合同级确定性网络桩覆盖既有 Runtime 资源场景；默认 `playwright.config.ts` 用 DEV MSW adapter 做多视口和未声明请求检查。`playwright.real-api.config.ts` 不加载 MSW 或浏览器拦截，启动真实 FastAPI/PostgreSQL 与生产预览，逐项验证登录并创建项目、刷新恢复同一 Session、退出后旧 CSRF 写入返回 401。
