# 路由、页面、组件与 API 映射

责任人：前端承接方
读者：前端、后端联调与测试人员
规范路径：`apps/web/docs/ROUTES_AND_API.md`
替换规则：现行路由或合同变化时原位更新

## 应用入口

`src/app/App.tsx` 是唯一入口选择器：

- Vite 开发环境且 `VITE_API_MODE=mock` 时加载 `MockApp`；
- 生产构建、预览构建或 `VITE_API_MODE=real` 时加载 `RuntimeApp`；
- `RuntimeApp` 不导入开发 Mock 路由，也不会在真实请求失败时回退到浏览器本地业务状态。

## RuntimeApp 路由

下表是生产构建当前真正开放的路由。未列出的业务页面即使在 `MockApp` 中已有视觉实现，也不能视为真实页面已接入。

| 路由                                       | 页面/布局                      | 当前真实能力                                     |
| ------------------------------------------ | ------------------------------ | ------------------------------------------------ |
| `/login`                                   | `RuntimeLoginPage`             | 认证说明页；无登录提交接口                       |
| `/app`                                     | `RuntimeAppShell` + `HomePage` | 品牌首页、真实项目摘要；创作入口禁用             |
| `/app/projects`                            | `ProjectsPage`                 | 分页查询项目、前端搜索、新建入口                 |
| `/app/projects/new`                        | `RuntimeNewProjectPage`        | 创建项目和教材三段式上传                         |
| `/app/projects/:projectId/setup?jobId=...` | `RuntimeProjectSetupPage`      | Job 查询/取消、Job SSE、轮询恢复、成功后读取课时 |
| `/app/projects/:projectId`                 | `RuntimeProjectOverviewPage`   | 项目、课时、AutomationPolicy 和项目 SSE          |
| `/app/projects/:projectId/*`               | `RuntimeUnavailablePage`       | 后续项目页面的安全不可用态                       |
| `/app/creation/*`                          | `RuntimeUnavailablePage`       | 创作中心尚未接入真实页面                         |
| `/app/tasks`                               | `RuntimeUnavailablePage`       | 全局任务页尚未接入真实页面                       |
| `/admin/*`                                 | `RuntimeUnavailablePage`       | 管理端尚未接入真实页面                           |

`RuntimeAppShell` 不创建浏览器会话或伪造用户身份。它假定服务端已经通过 HttpOnly Cookie 建立会话；当前 runtime 合同没有登录、当前用户或退出端点，因此认证 bootstrap 仍是显式缺口。

## 开发 MockApp 路由

以下页面只在开发 Mock 模式用于视觉、交互和自动化测试：

| 路由范围                                                           | 页面范围                                 |
| ------------------------------------------------------------------ | ---------------------------------------- |
| `/login`、`/app`、`/app/projects*`                                 | 演示登录、首页、项目、教材、课时与工作台 |
| `/app/projects/:projectId/lessons/:lessonId/work/:stepKey`         | 教案、导入、PPT、视频和交付步骤渲染器    |
| `/app/projects/:projectId/results`、`tasks`、`delivery`            | 成果、项目任务和交付演示                 |
| `/app/creation*`                                                   | 图片、视频、PPT 独立创作与项目批次演示   |
| `/app/tasks`                                                       | 全局任务演示                             |
| `/admin/content`、`workflows`、`models`、`usage`、`users`、`audit` | 管理端演示                               |

这些路由中的本地生成状态、演示账号、保存冲突和媒体预览都不是生产数据或真实 Provider 结果。

## 注册表与基础控件

| 注册表                    | 路径                                                        | 扩展对象                        |
| ------------------------- | ----------------------------------------------------------- | ------------------------------- |
| `nodeRendererRegistry`    | `pages/projects/WorkStepPage.tsx`                           | 课时工作台步骤渲染器            |
| `fieldRegistry`           | `features/content-definition/ContentDefinitionRenderer.tsx` | 动态内容字段                    |
| `artifactPreviewRegistry` | `features/project-results/artifactPreviewRegistry.tsx`      | 图片、视频、PPT、文档、音频预览 |
| `studioRegistry`          | `features/creation-studio/registry.ts`                      | 图片、视频、PPT 创作能力        |

- 页面主操作统一使用 `shared/ui/Button.tsx`，尺寸只允许 `sm`、`md`、`lg` 三档；
- 图标操作统一使用 `shared/ui/IconButton.tsx`；
- 下拉选择统一使用基于 Radix Select 的 `shared/ui/Select.tsx`；
- 标准表单控件为 40px，高密度工具栏为 36px，重要操作上限为 44px。

## 类型化 API 客户端

所有合同路径都相对于 `VITE_API_BASE_URL`，默认前缀为 `/api/v2`。前端类型来自 `contracts/generated/typescript/schema.ts`；`apps/web/src/generated/api-schema.ts` 只做类型导出，不维护第二套 DTO。

| 领域           | runtime 合同端点                                                                                                                                                                               | 前端入口                                            | 页面接入状态                                     |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------ |
| 项目           | `GET/POST /projects`；`GET /projects/{project_id}`                                                                                                                                             | `features/projects/api/projectsApi.ts`              | 列表、创建、详情已接入 Runtime 页面              |
| 制作方式       | `GET/PATCH /projects/{project_id}/automation-policy`                                                                                                                                           | `features/projects/api/automationPolicyApi.ts`      | 项目概览已接入，写入使用 ETag/`If-Match`         |
| 教材           | `POST /projects/{project_id}/materials/uploads`；对象存储直传；`POST /projects/{project_id}/materials/{material_id}/confirm`                                                                   | `features/materials/api/materialsApi.ts`            | 上传三段式链已接入新建项目页                     |
| 教材读取       | `GET .../file-asset`；`GET .../parse-versions`                                                                                                                                                 | `features/materials/api/materialsApi.ts`            | 客户端已实现，Runtime 页面待接入                 |
| 课时           | `GET/PATCH /projects/{project_id}/lessons`；`GET /lessons/{lesson_id}`；`PATCH /lessons/{lesson_id}/branches`                                                                                  | `features/lessons/api/lessonsApi.ts`                | 课时列表已接入；编辑集合、单课时和分支页面待接入 |
| Workflow       | `GET /projects/{project_id}/workflow`                                                                                                                                                          | `features/workflow/api/workflowApi.ts`              | 客户端已实现，Runtime 工作台待接入               |
| Artifact       | `POST /projects/{project_id}/artifacts`；`GET /artifacts/{artifact_id}`；`PUT .../drafts/{draft_branch}`；`POST .../versions`；`POST /artifact-versions/{artifact_version_id}/approvals`       | `features/artifacts/api/artifactsApi.ts`            | 客户端已实现，Runtime 成果与审核页面待接入       |
| 素材槽位       | `GET /projects/{project_id}/asset-slots`；`GET .../asset-package`；`POST /asset-slots/{slot_id}/bindings`；`POST /asset-bindings/{binding_id}/unbind`                                          | `features/assets/api/assetsApi.ts`                  | 客户端已实现，Runtime 素材页面待接入             |
| 创作           | `POST /creation-batches`                                                                                                                                                                       | `features/creation-studio/api/creationApi.ts`       | 批次客户端已实现，Runtime 创作页待接入           |
| 创作四动作     | `POST /creation-items/{item_id}/prompt-versions`；`POST /creation-items/{item_id}/generate`；`POST /generation-results/{result_id}/adoptions`；`POST /adoptions/{adoption_id}/save-to-project` | `features/creation-studio/api/creationApi.ts`       | 四个独立客户端已实现，Runtime 页面待接入         |
| Generation Job | `GET /generation-jobs/{job_id}`；`POST /generation-jobs/{job_id}/cancel`                                                                                                                       | `features/jobs/api/jobsApi.ts`                      | 教材任务进度页已接入                             |
| SSE            | `GET /projects/{project_id}/events/stream`；`GET /generation-jobs/{job_id}/events/stream`                                                                                                      | `shared/api/useProjectEvents.ts`、`useJobEvents.ts` | 项目概览和教材任务进度页已接入                   |

`shared/api/client.ts` 统一使用 `credentials: include`、标准成功/错误信封和网络错误映射。写操作由各 feature 客户端显式携带 `Idempotency-Key`；并发编辑读取响应 ETag，并在修改时发送 `If-Match`。CSRF header 必须由真实认证 bootstrap 提供；真实模式没有 token 时，客户端会在 fetch 前安全失败，页面同时禁用新建、取消任务和制作方式写操作。

## 教材上传纵向链

`RuntimeNewProjectPage` 与 `RuntimeProjectSetupPage` 当前按以下顺序调用真实合同，不使用前端计时器伪造进度：

1. 校验 PDF，并在浏览器计算文件 SHA-256；
2. `POST /projects` 创建项目；
3. `POST /projects/{project_id}/materials/uploads` 创建上传会话；
4. 按会话返回的 method、URL 和 required headers 将文件直传对象存储，并读取 ETag；
5. `POST /projects/{project_id}/materials/{material_id}/confirm` 确认文件，取得 Generation Job；
6. 进入 setup 页面，通过 Job REST 快照、Job SSE 和 5 秒轮询读取服务端进度，可取消非终态任务；
7. Job 成功后读取项目课时，并进入项目概览读取项目、课时和制作方式。

当前标签页会在 `sessionStorage` 保存表单、文件元数据与 SHA-256、三段幂等意图、项目 ID、上传会话、ETag 和 Job ID。浏览器刷新后不会伪造或恢复 `File` 对象，而是请用户重新选择同一份 PDF，再从已保存的服务端阶段继续；若签名上传地址已经过期，保留项目并轮换上传与确认意图，重新建立上传会话。

这条链已经完成前端实现和确定性测试，但尚未在真实认证、反向代理、对象存储和后端部署组合环境中完成浏览器端到端验收，不能据此宣布阶段1联调或生产闭环完成。

## SSE 恢复语义

- 使用 Fetch 流并携带 Cookie，允许发送正整数 `Last-Event-ID`；最近 sequence 只保存在当前标签页的 `sessionStorage`；
- 严格校验 SSE `id`、事件名和 JSON 信封中的 `sequence_no`、`event_type`、资源及 payload，丢弃不递增的重复事件；
- 收到事件后只使相关 TanStack Query 失效，再从 REST 读取业务快照；
- 服务端返回 409/`EVENT_HISTORY_EXPIRED` 时清除游标并刷新 REST 快照；
- 普通断线按 1 秒到 15 秒指数退避重连，组件卸载时通过 AbortController 清理连接。

## 尚未完成的生产边界

- runtime OpenAPI 尚无真实登录、当前用户、刷新和退出合同，CSRF token provider 也尚未安装；
- Workflow、Artifact、素材槽位、创作四动作、完整 Job 中心、交付和管理端仍缺生产页面编排与浏览器验收；
- 后端目前只有 Provider 中立媒体合同和确定性 Fake，真实图片/视频 Adapter 与受控冒烟不属于当前前端已完成能力；
- Mock 媒体、静态素材和视觉预览只能验证版式，不能作为真实生成、下载或原子写回的验收证据。

独立的 `playwright.runtime.config.ts` 只启动真实模式入口，并使用合同级确定性网络桩覆盖首页、项目、新建上传、刷新恢复、Job REST/SSE 与项目概览；默认 `playwright.config.ts` 继续验证开发 Mock 视觉流程，两者由前端 CI 分别执行。
