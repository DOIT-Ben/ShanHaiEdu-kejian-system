# 山海教育课件系统前端

责任人：前端承接方
读者：前端开发、测试、部署与后端联调人员
规范路径：`apps/web/README.md`
替换规则：在本文件原位更新，不新增带版本号或日期的副本

这是山海教育课件系统的 React 教师端与管理端。前端只消费仓库根级 runtime OpenAPI 生成类型，不实现后端业务、模型调用或第二套 DTO。

当前工程已经从单一 Mock 演示基线调整为两个明确隔离的入口：

- `RuntimeApp` 是真实 API 与生产构建入口，只呈现已经接入 runtime 合同的页面，缺失能力不会回退到 Mock 假成功；
- `MockApp` 只在 Vite 开发环境且 `VITE_API_MODE=mock` 时加载，用于完整视觉流程、组件状态和浏览器自动化测试。

真实模式已经实现“创建项目 → 计算教材 SHA-256 → 创建上传会话 → 直传对象存储 → 确认上传 → 查询并订阅生成任务 → 读取课时 → 查看项目”的前端纵向链。该结论只表示前端代码和确定性测试已经覆盖这条链；真实认证、部署环境联调和完整业务页面尚未完成，因此当前仍不是生产发布版本。

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

开发环境未指定配置时默认启动 `MockApp`：

```powershell
corepack pnpm --filter @shanhaiedu/web dev
```

浏览器访问 `http://localhost:5173/app`。Mock 模式提供两组固定演示账号：

- 教师：`lin.teacher@example.edu / teacher-demo`
- 管理员：`admin@example.edu / admin-demo`

演示账号、浏览器角色门禁和 `localStorage` 中的 Mock 业务状态只用于开发演示，不能替代服务端认证、授权或 PostgreSQL 中的业务真相。

连接真实 API 时显式切换模式；真实模式不会接受演示账号：

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
corepack pnpm --filter @shanhaiedu/web build
corepack pnpm --filter @shanhaiedu/web test:e2e --project=chromium
```

也可以运行 `corepack pnpm --filter @shanhaiedu/web release:check` 执行完整前端门禁。Playwright 默认自行启动并关闭隔离的本地开发服务，测试并发固定为 2。

## Runtime 与 Mock 边界

- `App.tsx` 仅在 `import.meta.env.DEV` 且 API 模式为 `mock` 时懒加载 `MockApp`，其他情况统一进入 `RuntimeApp`；
- MSW Worker 同样只在开发 Mock 模式动态加载；生产构建不会注册或引用 Worker；
- 生产构建检查会拒绝 MSW Worker、Mock Runtime 标识、开发演示凭据和缺失的静态素材引用；
- `RuntimeApp` 使用 Cookie 请求、标准错误包、`Idempotency-Key`、ETag/`If-Match` 和可注入的 CSRF token 读取器；
- 项目与 Job SSE 只使对应 TanStack Query 快照失效并重新读取 REST 真相，不在浏览器内拼装业务对象；
- `MockApp` 保留完整视觉壳、交互状态和本地演示数据，但这些能力不构成真实 API 联调证据。

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

其中当前 `RuntimeApp` 页面已经使用项目、上传、Job、课时、AutomationPolicy 和 SSE 客户端完成教材上传纵向链。Workflow、Artifact、素材槽位和创作四动作虽然已有客户端及定向测试，但生产页面仍待接入，不能把开发 Mock 页面描述为真实业务完成。

## 当前页面范围与缺口

`RuntimeApp` 当前开放品牌首页、项目列表、新建项目、教材任务进度和项目概览。创作中心、课时工作台、成果、项目任务、交付和管理端尚未接入真实页面，访问时显示安全的不可用状态。

真实认证仍缺少 runtime 合同中的登录、当前用户、刷新和退出入口；前端目前只依赖服务端已有 Cookie，并未建立认证 bootstrap 或 CSRF token 注入。后端真实图片/视频 Provider Adapter 与受控冒烟也尚未完成，前端素材和 Mock 预览不能冒充真实媒体生成结果。

## 目录结构

```text
src/
├─ app/          RuntimeApp、开发 MockApp、路由和 Provider
├─ pages/        路由组合页与真实模式安全边界页
├─ layouts/      全局、项目、课时工作台、创作台、管理端布局
├─ features/     垂直业务模块、类型化客户端与注册表
├─ entities/     前端视图模型和映射
├─ shared/       UI、API、SSE、Mock、样式和工具
└─ generated/    指向根级 OpenAPI 生成类型的只读桥接
```

不得手改 `contracts/generated/typescript/schema.ts`。合同变化后运行 `pnpm --filter @shanhaiedu/web generate:api`，提交根级生成物及前端只读桥接的必要差异。

详细路由与 API 映射见 [docs/ROUTES_AND_API.md](docs/ROUTES_AND_API.md)，部署与回滚见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。
