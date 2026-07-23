# 山海教育课件系统前端

责任人：前端承接方
读者：前端开发、测试、部署与后端联调人员
规范路径：`apps/web/README.md`
替换规则：在本文件原位更新，不新增带版本号或日期的副本

这是山海教育课件系统的 React 教师端与管理端。前端只消费仓库根级 runtime OpenAPI 生成类型，不实现后端业务、模型调用或第二套 DTO。

当前工程只有一个 `RuntimeApp` 路由与页面树。real 模式连接真实 API；Vite 开发环境且 `VITE_API_MODE=mock` 时，`main.tsx` 只动态启用 MSW 合同 adapter，为相同页面提供确定性响应。缺失能力不会切换到第二套页面、浏览器状态机或本地假成功。

真实模式已经实现“创建项目 → 计算教材 SHA-256 → 创建上传会话 → 直传对象存储 → 确认上传 → 查询并订阅生成任务 → 读取已有课时或明确阻断 → 查看项目”的前端纵向链。该结论只表示前端代码和确定性测试已经覆盖这条链；真实认证、部署环境联调和完整业务页面尚未完成，因此当前仍不是生产发布版本。

## 技术栈

- React 19、TypeScript 严格模式、Vite、React Router；
- Tailwind CSS、Radix UI、代码设计令牌；
- TanStack Query 管理服务端状态，Zustand 只管理界面状态；
- React Hook Form 与 Zod；
- 根级 OpenAPI 生成类型、`openapi-fetch`、MSW；
- Vitest、Testing Library、Playwright、Storybook。

## 安装与启动

在仓库根目录安装唯一的 pnpm workspace 依赖并生成 runtime API 类型：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @shanhaiedu/web generate:api
```

开发环境未指定配置时仍启动同一个 `RuntimeApp`，并默认使用 DEV MSW 合同 adapter：

```powershell
corepack pnpm --filter @shanhaiedu/web dev
```

浏览器访问 `http://localhost:5173/app`。DEV 合同 adapter 不创建浏览器认证或 `localStorage` 业务状态；登录合同缺失会与 real 模式一样显示安全阻断。

连接真实 API 时显式切换网络 adapter：

```powershell
$env:VITE_API_MODE="real"
$env:VITE_API_BASE_URL="/api/v2"
corepack pnpm --filter @shanhaiedu/web dev
```

## 环境变量

复制 `apps/web/.env.example` 为本地环境文件，不要提交真实密钥。

| 变量                   | 可选值          | 说明                             |
| ---------------------- | --------------- | -------------------------------- |
| `VITE_API_MODE`        | `mock` / `real` | 开发默认 `mock`，生产默认 `real` |
| `VITE_API_BASE_URL`    | 路径或同源地址  | 默认 `/api/v2`                   |
| `VITE_RELEASE_VERSION` | 发布标识        | 用于错误追踪和回滚定位           |

浏览器不保存模型服务密钥，所有模型请求都必须经过服务端模型网关。

## 常用命令

以下命令均从仓库根目录运行：

```powershell
corepack pnpm --filter @shanhaiedu/web format
corepack pnpm --filter @shanhaiedu/web lint
corepack pnpm --filter @shanhaiedu/web typecheck
corepack pnpm --filter @shanhaiedu/web test
corepack pnpm --filter @shanhaiedu/web build:storybook
corepack pnpm --filter @shanhaiedu/web test:storybook:a11y
corepack pnpm --filter @shanhaiedu/web build
corepack pnpm --filter @shanhaiedu/web test:e2e --project=chromium
corepack pnpm --filter @shanhaiedu/web test:e2e:runtime --project=runtime-chromium
```

也可以运行 `corepack pnpm --filter @shanhaiedu/web release:check` 执行 OpenAPI 生成无漂移与全部前端门禁。Runtime Playwright 使用独立配置和 real adapter；合同级确定性网络桩验证首页/项目概览、项目与 Job SSE、教材上传刷新恢复、教材读取、空课时合同阻断、课时集合与分支编辑、课时工作台阻断、素材绑定/解绑、Artifact 只读状态与写操作阻断、Job 取消/失败、无教材创建与 CSRF 安全阻断。默认 Playwright 使用 DEV MSW adapter，在 1440、1024 和 390 宽度验证同一 Runtime 路由、基础可访问性、登录阻断和未声明请求拒绝。两套 Playwright 不会共用浏览器业务状态。

Storybook 门禁会对全部 story 在 1440 宽度运行 axe WCAG 2A/AA、横向溢出、用户文案与运行时异常检查，并拒绝错误壳或空渲染根；标记为 `core-viewport` 的核心 story 还会实际切换浏览器 viewport，在 1024 和 390 宽度重复检查。

## Runtime 入口与 DEV adapter 边界

- `App.tsx` 始终只懒加载 `RuntimeApp`，页面、路由和用户意图没有第二份实现；
- `main.tsx` 仅在 `import.meta.env.DEV` 且 API 模式为 `mock` 时动态启用 MSW；生产构建不会注册或引用 Worker；
- 生产构建检查会拒绝 MSW Worker、本地业务运行时标识、开发凭据和缺失的静态素材引用；
- `RuntimeApp` 使用 Cookie 请求、标准错误包、`Idempotency-Key`、ETag/`If-Match` 和可注入的 CSRF token 读取器；真实模式没有 token 时写请求在 fetch 前安全失败，相关按钮保持禁用；
- 项目与 Job SSE 只使对应 TanStack Query 快照失效并重新读取 REST 真相，不在浏览器内拼装业务对象；
- DEV MSW handlers 只提供 OpenAPI 合同场景，不维护第二套业务真相；其通过结果不构成真实 API 联调证据。

`pnpm build`只证明类型、打包和生产内容边界通过，不代表真实认证、后端环境或媒体 Provider 已经完成生产验收。

## 已实现的真实数据层

前端已经基于根级 runtime OpenAPI 实现以下类型化客户端：

- 项目列表、项目详情、创建项目和 `AutomationPolicy` 读取/更新；
- 教材上传会话、对象存储直传、上传确认、源文件资产和解析版本读取；
- 课时集合、单课时、分支读取/更新，以及项目 Workflow 读取；
- Artifact 创建、详情、草稿保存、版本提交和审核；
- 项目素材槽位、素材包、绑定和解绑；
- 创作批次，以及保存提示词版本、生成候选、采用候选、原子写回项目四个独立动作；
- Generation Job 查询/取消，以及项目和 Job 两类 SSE 订阅。

其中当前 `RuntimeApp` 页面已经使用项目、上传、Job、课时、AutomationPolicy 和 SSE 客户端完成教材上传纵向链，并提供读取项目与单课时的课时工作台路由。教材深链可读取文件与解析版本；课时页可编辑集合和分支；素材页可读取槽位/素材包并绑定或解绑已有服务端素材；Job 深链支持 REST/SSE 对账和取消，同一未确认取消意图会复用幂等键；Artifact 深链只读服务端版本状态，并在内容字段与权限不可解析时阻断草稿保存、版本提交和批准。新建项目页面把表单、文件摘要、幂等意图、项目、上传会话、ETag 和 Job 标识保存在当前标签页，可在刷新后重新选择同一文件继续，且不会复用过期的签名上传地址。

这些资源页仍受服务端发现与字段合同约束：教材、Artifact 和 Job 没有完整项目级发现入口时只能从已知 ID 深链进入；Artifact 没有按 `content_definition_version_id` 读取可编辑字段与权限的端点，因此不展示裸 JSON，也不使用本地定义伪造草稿编辑器。Workflow 与创作动作即使已有客户端，也只有被 Runtime 页面真实调用并通过浏览器检查后才算页面接入。

## 当前页面范围与缺口

`RuntimeApp` 当前开放品牌首页、项目列表、新建项目、教材任务进度、项目概览、教材/解析深链、课时集合编辑、素材槽位、Artifact/Job 深链、读取项目和单课时数据的课时工作台，以及独立创作中心。创作中心不依赖项目，并可按正式合同创建 standalone 批次；当前批次响应不创建 CreationItem，且没有条目创建端点，因此页面在这里明确停止，不保存提示词、不启动生成 Job。课时工作台没有课时/教案生成命令时也会明确显示进度不可用，不会启动浏览器假任务。完整成果发现与查询、项目任务、交付和管理端尚未形成可恢复的真实流程，未接入路由保持安全不可用。

真实认证的登录、当前用户、刷新、退出和 CSRF bootstrap 路径尚未形成合同，由 #11 决策。教材缺 `GET /projects/{project_id}/materials`，Artifact 缺 `GET /projects/{project_id}/artifacts`，Job 缺项目级或全局列表；`GET/PATCH /projects/{project_id}/lessons`、`GET /lessons/{lesson_id}` 与 `GET /projects/{project_id}/workflow` 也缺 planned `POST /node-runs/{node_run_id}/start`，不能启动课时划分、教案或节点生成。standalone `POST /creation-batches` 当前返回空 `items`，active OpenAPI 没有创建 CreationItem 的端点（路径待 #11 决策）；此外还缺 `GET /creation-batches/{batch_id}`、`GET /creation-items/{item_id}` 与 `GET /generation-results/{result_id}`。因此当前页不伪造 item 或生成 Job，刷新恢复、候选预览、采用和保存到项目也保持阻断。正式 PPT 缺 `GET /lessons/{lesson_id}/ppt`、`PATCH /ppt-pages/{page_id}`、`POST /ppt-documents/{id}/render` 和 PPTX 下载关系；视频缺 `GET /lessons/{lesson_id}/video`、`PATCH /video-shots/{shot_id}`、`POST /video-shots/{shot_id}/select-clip`、`POST /video-projects/{id}/assemble`；交付缺 `GET/POST /projects/{project_id}/deliveries`。上述服务端合同缺口由 #11 跟踪，PPT 专项同时关联 #108；浏览器不得用 DEV fixture、定时器或本地对象补造这些事实。

前端目前只依赖服务端已有 Cookie，并未建立生产认证 bootstrap，因此真实写操作在没有 CSRF token 时会保持禁用。后端真实图片/视频 Provider Adapter 与受控冒烟也尚未完成，前端素材和 DEV fixture 预览不能冒充真实媒体生成结果。

## 目录结构

```text
src/
├─ app/          单一 RuntimeApp、路由和 Provider
├─ pages/        Runtime 路由组合页与安全边界页
├─ layouts/      AppShell 与 RuntimeAppShell
├─ features/     垂直业务模块、类型化客户端与注册表
├─ entities/     前端视图模型和映射
├─ shared/       UI、API、SSE、DEV MSW、样式和工具
└─ generated/    指向根级 OpenAPI 生成类型的只读桥接
```

不得手改 `contracts/generated/typescript/schema.ts`。合同变化后运行 `pnpm --filter @shanhaiedu/web generate:api`，提交根级生成物及前端只读桥接的必要差异。

详细路由与 API 映射见 [docs/ROUTES_AND_API.md](docs/ROUTES_AND_API.md)，页面/组件/状态交接见 [docs/FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md)，部署与回滚见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。
