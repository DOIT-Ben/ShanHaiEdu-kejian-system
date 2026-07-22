# 前端交接与状态模型

责任人：前端承接方  
读者：前端、联调、测试与产品  
规范路径：`apps/web/docs/FRONTEND_HANDOFF.md`  
替换规则：路由、组件边界或状态合同变化时原位更新，不新增版本副本。

## 页面清单

| 入口                                                       | Runtime 页面                 | Mock 页面                                 | 数据来源                                          |
| ---------------------------------------------------------- | ---------------------------- | ----------------------------------------- | ------------------------------------------------- |
| `/app`                                                     | `HomePage`                   | `HomePage`                                | Runtime 使用项目查询；Mock 使用 MSW fixture       |
| `/app/projects`                                            | `ProjectsPage`               | `ProjectsPage`                            | `projectsApi`                                     |
| `/app/projects/new`                                        | `RuntimeNewProjectPage`      | `NewProjectPage`                          | Runtime 使用项目与教材合同；Mock 使用 MockRuntime |
| `/app/projects/:projectId`                                 | `RuntimeProjectOverviewPage` | `ProjectOverviewPage`                     | Runtime 使用项目、课时、策略查询                  |
| `/app/projects/:projectId/lessons/:lessonId/work/:stepKey` | `RuntimeLessonWorkbenchPage` | `ProjectWorkbenchLayout` + `WorkStepPage` | Runtime 使用 workflow 查询；Mock 使用演示状态机   |
| `/app/creation/*`                                          | 安全不可用态                 | 图片、视频、PPT 创作台                    | Runtime 尚无创作合同页面                          |

## 组件清单

- 基础控件：`Button`、`IconButton`、`Select`、`StatusBadge`、`EmptyState`。
- 全局布局：`GlobalAppShell`、`RuntimeAppShell`、`WorkbenchPageFrame`、`ProjectWorkbenchLayout`。
- 工作台：`ProjectStepNavigation`、`WorkbenchStatusBoard`、`TaskStatusBar`、`ContextDrawer`。
- 项目与成果：项目列表、项目概览、素材、结果和交付页面位于对应 feature/page 目录。
- 创作台：`CreationComposer`、`CreationResultsPanel`、`ProjectAssetDrawer` 和 `CreationParameterBar`。
- 内容渲染：`ContentDefinitionRenderer`、`MarkdownDocument`、`artifactPreviewRegistry`。

## Runtime/Mock 边界

`src/app/App.tsx` 是唯一分流点。只有开发环境且 `VITE_API_MODE=mock` 时才加载 `MockApp`；生产构建和 `VITE_API_MODE=real` 只加载 `RuntimeApp`。MockRuntime、MSW、演示凭据、确定性任务计时器和本地保存冲突不得进入真实页面，也不能被描述成后端能力。

Runtime 页面只消费 `features/*/api` 的类型化客户端和 TanStack Query。Runtime 与 Mock 可以复用 `shared/ui` 和 `features/*/components` 的展示组件，但不能共享 Mock 状态读写函数。`WorkbenchStatusBoard` 是节点状态展示的单一产品组件：Runtime 传入服务端状态，Mock 传入演示状态，颜色、图标和语义文案只在 `StatusBadge` 中维护。

## 前端状态模型

| 状态层     | 责任                                                          | 持久化                                 |
| ---------- | ------------------------------------------------------------- | -------------------------------------- |
| 服务端资源 | 项目、课时、workflow、任务、素材和产物的事实状态              | PostgreSQL，经 REST/SSE 返回           |
| 查询缓存   | 请求状态、失效、重试和页面读取                                | TanStack Query，标签页内存             |
| UI 状态    | 抽屉、主题、侧栏、当前筛选、焦点                              | Zustand/React state                    |
| 编辑恢复   | 新建项目表单、PDF 元数据、SHA-256、幂等意图、上传会话、Job ID | `sessionStorage`，不保存或伪造 `File`  |
| Mock 状态  | 仅开发演示的项目、节点、任务和草稿                            | MockRuntime 本地存储，禁止作为生产证据 |

状态显示必须区分 `loading`、`empty`、`error`、`queued`、`running`、`review_required`、`partially_completed`、`approved` 和 `failed`。成功与失败不能只依赖颜色，必须同时显示图标和文字；加载时禁止重复提交，并支持 `prefers-reduced-motion`。

## Storybook 覆盖

当前 Storybook 入口覆盖基础按钮、图标按钮、选择框、空状态、状态徽章、保存对话框、动态内容字段和 `WorkbenchStatusBoard`。工作台状态板覆盖：加载、空态、错误、进行中、完成、失败和部分完成；状态徽章覆盖所有合同状态及未知状态。新增产品组件必须同时新增默认态、加载态、空态、错误态和成功态故事。

## 测试与联调计划

1. 单元与组件：`pnpm --dir apps/web test`，变更文件先用 Vitest 定向运行。
2. 静态门禁：format、lint、typecheck、生产构建和 Storybook build。
3. Mock 浏览器：核心流、创建台、滚动可访问性、主题和视觉回归。
4. Runtime 浏览器：项目读取、教材上传恢复、Job 状态和项目概览；真实认证缺口必须显式失败，不能回退 Mock。
5. 发布前检查构建产物不得包含 MSW Worker、MockRuntime、演示凭据或合同测试入口。

## 交接阻塞

真实登录/bootstrap、完整创作台 Runtime 页面和真实图片/视频 Provider 仍由对应 Issue 负责。本文件不把确定性 Fake、Mock 预览或合同测试网络桩写成生产能力。
