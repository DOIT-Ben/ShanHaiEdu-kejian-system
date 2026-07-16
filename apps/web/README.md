# 山海教育课件系统 · 前端 V2（apps/web）

面向小学数学教师的「教育创作工作室」：从教材上传到教案、PPT、导入视频的全链路课件制作前端。
React 19 + TypeScript（strict）+ Vite 单页应用，所有模型调用一律经过后端模型网关——前端不直连任何模型 Provider，也不保存模型密钥（管理端仅展示掩码与配置状态）。

## 快速开始

```bash
pnpm install

# Mock 模式（无后端，MSW 拦截全部 /api/v2 请求）
pnpm dev:mock

# 真实模式（需要后端网关，默认代理 /api/v2）
pnpm dev
```

Mock 模式演示账号（密码均为 `demo1234`）：

| 账号 | 角色 |
| --- | --- |
| `teacher@shanhai.edu` | 教师 |
| `admin@shanhai.edu` | 系统管理员 |
| `template@shanhai.edu` | 模板管理员 |
| `audit@shanhai.edu` | 审计管理员 |

Mock 模式下顶栏会出现「演示场景」徽标，可切换 28 个契约场景（成功 / 空 / 慢 / 失败 / 可重试 / 部分成功 / 403 / 会话过期 / SSE 重连 / 上游变更失效等）；也可用 URL 参数 `?scenario=<id>` 直接进入。

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `pnpm dev` / `pnpm dev:mock` | 本地开发（真实 / Mock） |
| `pnpm typecheck` | TypeScript 严格检查 |
| `pnpm lint` | ESLint（含「页面禁止直接 fetch」白名单规则） |
| `pnpm test` | Vitest 单元 / 组件 / MSW 场景测试 |
| `pnpm build` | 生产构建（`VITE_API_MODE=mock` 会直接报错） |
| `pnpm check:mock-exclusion` | 校验产物不含 MSW / mockServiceWorker |
| `pnpm test:e2e` | Playwright 端到端（自动以 mock 模式起 4317 端口） |
| `pnpm storybook` / `pnpm build-storybook` | 组件文档 |

## 架构速览

```
src/
  app/        路由、Provider、守卫、开发工具（场景徽标）
  layouts/    应用壳 / 项目壳 / 管理端壳
  pages/      路由页面（薄组装层，≤300 行）
  widgets/    跨页面复合组件（输出面板、审批条、提示词编辑器、任务坞…）
  features/   业务数据层（TanStack Query hooks，按域拆分）
  entities/   领域模型（18 步工作流定义、产物内容 zod schema）
  shared/     api 客户端 / ui 基础组件 / 设计令牌 / 工具
  mocks/      MSW：场景注册表、内存 DB、任务推进引擎、SSE 模拟
```

关键约定：

- **API**：openapi-typescript 生成 `shared/api/generated.ts`，统一 Envelope `{ok, data, meta}` / `{ok:false, error}`；错误经 `AppError` 规范化（教师语言 + trace_id + retryable/action）。
- **状态**：服务端状态全部走 TanStack Query（SSE 事件只做查询失效，不直接写状态）；Zustand 仅存 UI 状态（检查器宽度、页签等）。
- **乐观锁**：所有可编辑内容携带 `row_version`，409 冲突统一走 `ConflictDialog`（保留我的 / 采用服务器版本）。
- **提示词可见**：每个生成节点的检查器都有「提示词」页签，系统组装的最终提示词可见、可编辑、可恢复默认；运行时契约只读展示。
- **视频链路顺序**：视觉母图 → 粗分镜 → 图片资产 → 细分镜 → 镜头提示词 → 视频片段 → 合成，节点依赖在 `entities/workflow/nodes.ts` 中声明，上游未批准时下游锁定。
- **暂停语义**：生成中的「暂停」即取消当前任务（后端任务模型无挂起态）；已产出的版本保留，可随时重新发起生成。「跳过/恢复」只对可跳过节点开放，走 `POST /transitions`。
- **Mock 边界**：页面与业务组件不感知 Mock（只读 `env.apiMode` 的仅有 `main.tsx` 与开发徽标）；Mock 引擎用定时器模拟后端任务推进，真实模式下任务状态只来自后端轮询与 SSE。

## 测试

- 单元：`format` / `idempotency` / `AppError` / `SseParser` / 退避曲线 / 内容 schema。
- 组件：表单字段可达性、状态徽标、空状态交互。
- MSW 场景：登录成败、会话过期、空项目、课时划分 409、预算授权（真实 API 客户端直打 handler）。
- E2E（Playwright，16 条）：登录、三步建项目向导、空状态、工作台 18 步导航、提示词编辑/恢复默认、带警告批准、镜头部分失败单独重试（含备用服务付费确认）、资产选择器、交付完成/阻塞、管理端密钥掩码 + 连接测试、教师访问管理端 403。
