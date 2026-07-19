# 路由、页面、组件与 API 映射

责任人：前端承接方
读者：前端、后端联调与测试人员
规范路径：`apps/web/docs/ROUTES_AND_API.md`
替换规则：现行路由或合同变化时原位更新

## 教师端路由

| 路由                                                       | 页面/布局                               | 主要能力                             |
| ---------------------------------------------------------- | --------------------------------------- | ------------------------------------ |
| `/login`                                                   | `LoginPage`                             | 登录入口                             |
| `/app`                                                     | `HomePage`                              | 品牌首屏、继续创作、快捷创作、待处理 |
| `/app/projects`                                            | `ProjectsPage`                          | 项目查询、错误回退、新建入口         |
| `/app/projects/new`                                        | `NewProjectPage`                        | PDF 选择、项目表单、创建请求         |
| `/app/projects/:projectId`                                 | `ProjectOverviewPage`                   | 课时、分支、预算暂停、继续工作       |
| `/app/projects/:projectId/materials`                       | `ProjectMaterialsPage`                  | 教材状态、课时增删排序和批准         |
| `/app/projects/:projectId/lessons`                         | `LessonsPage`                           | 课时卡与分支状态                     |
| `/app/projects/:projectId/lessons/:lessonId`               | 重定向                                  | 恢复到当前教案步骤                   |
| `/app/projects/:projectId/lessons/:lessonId/work/:stepKey` | `ProjectWorkbenchLayout` + 注册表渲染器 | 教案、导入、PPT、视频和交付步骤      |
| `/app/projects/:projectId/results`                         | `ProjectResultsPage`                    | 当前成果、素材筛选、版本与替换       |
| `/app/projects/:projectId/tasks`                           | `ProjectTasksPage`                      | 项目任务                             |
| `/app/projects/:projectId/delivery`                        | `DeliveryPage`                          | 最终文件与交付包                     |
| `/app/creation`                                            | `CreationHomePage`                      | 三类创作入口、项目批次、最近作品     |
| `/app/creation/images`                                     | `CreationStudioPage`                    | 独立图片创作                         |
| `/app/creation/videos`                                     | `CreationStudioPage`                    | 独立视频创作                         |
| `/app/creation/presentations`                              | `CreationStudioPage`                    | 独立 PPT 创作                        |
| `/app/creation/batches/:batchId`                           | `CreationBatchPage`                     | 项目包批量创作与原子保存             |
| `/app/tasks`                                               | `TasksPage`                             | 全局长任务、状态筛选、失败内容重做   |

## 管理端路由

| 路由               | 页面                 | 主要能力                             |
| ------------------ | -------------------- | ------------------------------------ |
| `/admin/content`   | `AdminContentPage`   | 上传、检查、预览、试运行、发布内容包 |
| `/admin/workflows` | `AdminWorkflowsPage` | 步骤、上下文、门禁、预算和发布检查   |
| `/admin/models`    | `AdminModelsPage`    | 逻辑能力、主备服务和连接测试         |
| `/admin/usage`     | `AdminUsagePage`     | 积压、失败、费用与异常操作           |
| `/admin/users`     | `AdminUsersPage`     | 角色与资源范围                       |
| `/admin/audit`     | `AdminAuditPage`     | 发布、批准、保存、替换和下载记录     |

## 注册表

| 注册表                    | 路径                                                        | 扩展对象                        |
| ------------------------- | ----------------------------------------------------------- | ------------------------------- |
| `nodeRendererRegistry`    | `pages/projects/WorkStepPage.tsx`                           | 课时工作台步骤渲染器            |
| `fieldRegistry`           | `features/content-definition/ContentDefinitionRenderer.tsx` | 动态内容字段                    |
| `artifactPreviewRegistry` | `features/project-results/artifactPreviewRegistry.tsx`      | 图片、视频、PPT、文档、音频预览 |
| `studioRegistry`          | `features/creation-studio/registry.ts`                      | 图片、视频、PPT 创作能力        |

## 基础控件边界

- 页面主操作统一使用 `shared/ui/Button.tsx`，尺寸只允许 `sm`、`md`、`lg` 三档；业务页面不得用额外纵向内边距放大按钮。
- 图标操作统一使用 `shared/ui/IconButton.tsx`。
- 所有下拉选择统一使用基于 Radix Select 的 `shared/ui/Select.tsx`；业务页面不得直接渲染原生 `select` 或自行绘制下拉箭头、弹层和选中态。
- 标准表单控件为 40px，高密度工具栏为 36px，重要但不夸张的操作上限为 44px。

## 核心 API 映射

| 操作          | 合同端点                                               | 前端入口                               | 当前状态                     |
| ------------- | ------------------------------------------------------ | -------------------------------------- | ---------------------------- |
| 查询项目      | `GET /projects`                                        | `features/projects/api/projectsApi.ts` | 客户端已接入，认证待联调     |
| 获取/更新项目 | `GET/PATCH /projects/{project_id}`                     | `features/projects/api/projectsApi.ts` | 客户端已就绪，页面待接入     |
| 创建项目      | `POST /projects`                                       | `NewProjectPage`                       | 客户端已就绪，受上传合同阻断 |
| 项目工作台    | `GET /projects/{project_id}/workflow`                  | MSW/后端联调面                         | Mock 已闭环，真实接口待接入  |
| 三类九套      | `GET /lessons/{lesson_id}/intro-options`               | 导入方案步骤                           | Mock 已闭环，真实接口待接入  |
| 选择导入方案  | `POST /lessons/{lesson_id}/intro-selections`           | 导入方案主操作                         | Mock 已闭环，真实接口待接入  |
| 生成指令预览  | `GET /node-runs/{node_run_id}/prompt-preview`          | `ContextDrawer`                        | Mock 已闭环，真实接口待接入  |
| 启动长任务    | `POST /node-runs/{node_run_id}/start`                  | 工作台主操作                           | Mock 已闭环，真实接口待接入  |
| 创建创作包    | `POST /node-runs/{node_run_id}/creation-packages`      | 项目到创作中心                         | Mock 已闭环，真实接口待接入  |
| 创建创作批次  | `POST /creation-batches`                               | 独立/项目创作                          | Mock 已闭环，真实接口待接入  |
| 批量生成      | `POST /creation-batches/{batch_id}/generate`           | 候选生成                               | Mock 已闭环，真实接口待接入  |
| 保存回项目    | `POST /generation-results/{result_id}/save-to-project` | `SaveToProjectDialog`                  | Mock 已闭环，真实接口待接入  |
| 项目事件      | `GET /projects/{project_id}/events/stream`             | `useProjectEvents`                     | 已订阅，真实查询源待接入     |

教材上传流程要求“创建上传会话 → 直传对象存储 → 确认”，但当前 OpenAPI 尚未声明上传会话和确认端点。真实模式不得把本地文件选择视为上传完成；补齐合同后再接入该闭环。

## Mock 与真实模式边界

- `mock` 只用于本地演示、组件状态和自动化测试；生产构建不注册 MSW，Mock session 也不能作为真实权限来源。
- `real` 当前只启用查询项目等客户端已接入的合同能力；创建项目仍受上传合同阻断。登录、上传、工作流、生成与保存回项目在合同补齐前必须显示不可用状态，不回退到 Mock 假成功。
- Cookie 写请求由真实认证 bootstrap 通过 `configureCsrfTokenProvider` 注入服务端签发的 `X-CSRF-Token`。客户端不保存令牌、不推测获取端点；服务端必须在认证合同中提供安全的签发/刷新方式。
- 项目 SSE 使用 Fetch 流传输，以便按 OpenAPI 发送 `Last-Event-ID` 请求头；连接错误只触发节流后的 REST 快照刷新。

组件不拼接 URL；请求通过 `shared/api/client.ts`，DTO 经 feature mapper 转为视图模型。
