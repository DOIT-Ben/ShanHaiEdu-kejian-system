# 山海教育课件系统前端

责任人：前端承接方
读者：前端开发、测试、部署与后端联调人员
规范路径：`apps/web/README.md`
替换规则：在本文件原位更新，不新增带版本号或日期的副本

这是山海教育课件系统的 React 教师端与管理端。实现严格遵循仓库 `docs/frontend/`、`docs/workflows/` 和 `contracts/` 的现行设计，只包含前端源码、Mock、Storybook 和测试。

当前交付定位为阶段0的Mock-first前端基线：可运行、可测试、可评审，用于准备真实API联调；真实认证和完整业务API尚未接入，因此不是生产发布版本。

## 技术栈

- React 19、TypeScript 严格模式、Vite、React Router；
- Tailwind CSS、Radix UI、代码设计令牌；
- TanStack Query 管理服务端状态，Zustand 只管理面板等界面状态；
- React Hook Form 与 Zod；
- OpenAPI 生成类型、统一 API 客户端、MSW；
- Vitest、Testing Library、Playwright、Storybook。

## 安装与启动

```powershell
cd apps\web
pnpm install --frozen-lockfile
pnpm generate:api
pnpm dev
```

浏览器访问 `http://localhost:5173/app`。开发环境未指定配置时默认启用 Mock，并会先进入登录页。

Mock 模式提供两组固定演示账号：

- 教师：`lin.teacher@example.edu / teacher-demo`
- 管理员：`admin@example.edu / admin-demo`

演示登录只在 Vite 开发环境且 `VITE_API_MODE=mock` 时开放。`real` 模式不会接受演示账号；真实认证尚未接入时会安全阻断登录。

项目、教材文件元数据、草稿、节点、任务、成果版本和保存冲突统一保存在浏览器
`localStorage` 中，可跨路由和刷新恢复。Mock 数据由同一浏览器中的两组演示账号共享，不提供账号级数据隔离；浏览器角色门禁只用于演示导航，不能替代服务端身份认证和资源授权。

## 环境变量

复制 `.env.example` 为 `.env.local`，不要提交真实密钥。

| 变量                   | 可选值          | 说明                             |
| ---------------------- | --------------- | -------------------------------- |
| `VITE_API_MODE`        | `mock` / `real` | 开发默认 `mock`，生产默认 `real` |
| `VITE_API_BASE_URL`    | 路径或同源地址  | 默认 `/api/v2`                   |
| `VITE_RELEASE_VERSION` | 发布标识        | 用于错误追踪和回滚定位           |

浏览器不保存模型服务密钥，所有模型请求都必须经过服务端。

## 常用命令

```powershell
pnpm format
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm verify:production-build
pnpm storybook
pnpm build:storybook
```

Playwright 默认自行启动并关闭隔离的本地前端服务，直接运行：

```powershell
pnpm test:e2e
```

测试并发固定为 2，避免在本机产生过多工作进程。

## Mock 与真实 API

- Mock Service Worker 只在开发模式且 `VITE_API_MODE=mock` 时动态加载；
- 静态构建不会启动或引用Mock Worker，也不包含开发演示凭据，但当前源码仍包含Mock Runtime代码；
- 上传教材目前只保存文件名、大小和类型等元数据，不读取或解析教材正文；
- 核心 Mock 端点和本地运行时覆盖项目、教材元数据、工作台、三类九套、提示词、创作包、生成任务、成果版本、保存冲突和模拟事件更新；
- API 客户端已支持 Cookie、`Idempotency-Key`、`If-Match` 和统一错误包，但真实认证、上传和完整业务联调仍依赖后端，不得把当前 Mock 闭环描述为真实生产闭环；
- SSE 只触发 TanStack Query 刷新，不直接拼装业务对象。

`pnpm build`当前只证明类型、打包和开发内容边界通过，不代表产物已满足生产部署条件。生产发布前必须完成真实认证与API联调，并通过独立检查确认Mock Runtime和演示数据不进入发布产物。

## 目录结构

```text
src/
├─ app/          路由和 Provider
├─ pages/        路由组合页
├─ layouts/      全局、项目、课时工作台、创作台、管理端布局
├─ features/     垂直业务模块与注册表
├─ entities/     前端领域模型和映射
├─ shared/       UI、API、Mock、样式和工具
└─ generated/    OpenAPI 自动生成类型
```

不得手改 `src/generated/api-schema.ts`。合同变化后运行 `pnpm generate:api` 并提交生成差异。

## 已实现工作空间

- 教师首页、项目列表、新建项目、教材与课时、课时工作台；
- 动态教案、三类九套、PPT 大纲/封面/正文、视频全生产链；
- 图片、视频、PPT 独立创作与项目批次创作；
- 素材与成果、任务中心、项目交付；
- 内容中心、工作流、模型服务、运行费用、权限和审计管理端。

工作台节点、动态内容字段、作品预览和创作能力都通过注册表扩展，不在路由页堆叠节点类型判断。

## 旧实现审计

接手时仓库没有 `apps/web` 或旧生产前端，因此没有可迁移或需删除的旧组件。当前工程从现行设计、合同和令牌建立，不复制历史外包页面。

详细路由与 API 映射见 [docs/ROUTES_AND_API.md](docs/ROUTES_AND_API.md)，部署与回滚见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。
