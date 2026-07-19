# 构建、部署与回滚

责任人：前端承接方
读者：部署、运维与前端负责人
规范路径：`apps/web/docs/DEPLOYMENT.md`
替换规则：部署方式变化时在本文件原位更新

## 当前交付边界

前端不再是单一 Mock-first 工程。生产构建统一进入 `RuntimeApp`，开发 Mock 入口通过环境和动态导入隔离；构建边界检查会拒绝 MSW Worker、Mock Runtime 标识、演示凭据和缺失静态素材。

当前源码由 Open Draft PR [#111](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/111) 承载，尚未合并或获得发布批准。真实模式已经实现项目、教材三段式上传、Generation Job/项目 SSE、课时读取和项目概览的前端纵向链，但真实认证、完整业务页面和部署环境端到端联调仍未完成，因此 `dist` 目前只能作为候选构建产物，不能宣称生产发布完成。

## 构建验证

从仓库根目录运行：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @shanhaiedu/web generate:api
corepack pnpm --filter @shanhaiedu/web format
corepack pnpm --filter @shanhaiedu/web lint
corepack pnpm --filter @shanhaiedu/web typecheck
corepack pnpm --filter @shanhaiedu/web test
corepack pnpm --filter @shanhaiedu/web build:storybook
corepack pnpm --filter @shanhaiedu/web build
corepack pnpm --filter @shanhaiedu/web test:e2e --project=chromium
corepack pnpm --filter @shanhaiedu/web test:e2e:runtime --project=runtime-chromium
```

也可以运行：

```powershell
corepack pnpm --filter @shanhaiedu/web release:check
```

构建产物位于 `apps/web/dist`。`build` 已包含 TypeScript 构建、Vite production build 和生产内容边界检查。

生产内容边界检查能够证明：

- 不存在 `mockServiceWorker.js` 或 MSW Worker 注册代码；
- 不包含已知 Mock Runtime 标识和开发演示凭据；
- 文本产物中的 `/assets/...` 引用都有对应构建文件。

它不能证明真实认证、API 可用性、对象存储 CORS、SSE 反向代理、真实媒体 Provider、监控或业务页面已经通过生产验收。

## 环境配置

生产候选必须显式设置：

```text
VITE_API_MODE=real
VITE_API_BASE_URL=/api/v2
VITE_RELEASE_VERSION=<发布标识>
```

不要把 `.env.local`、真实教材、签名上传或下载地址、服务密钥、Mock 数据或演示凭据复制到产物目录。浏览器不得持有模型 Provider 密钥。

## 发布前置条件

进入生产部署前必须同时满足：

1. PR #111 完成前端门禁、独立审查和合并，部署只从受保护的可发布提交构建；
2. 服务端提供并验证真实认证 bootstrap、当前用户、退出、Cookie、CSRF 和权限合同，前端安装 `configureCsrfTokenProvider`；
3. 项目创建、上传会话、对象存储直传、上传确认、Job REST/SSE、课时和项目概览在目标环境完成浏览器端到端联调；
4. Workflow、Artifact、素材槽位、创作四动作、任务、交付和管理端按对应阶段接入 Runtime 页面，不能以 `MockApp` 代替；
5. 真实图片/视频能力上线前，服务端媒体 Adapter、供应商状态映射和受控真实冒烟单独通过；前端静态素材不作为 Provider 验收；
6. 前端 CI、合同兼容、关键浏览器流程、可访问预览、发布标识、监控和回滚产物全部可验证。

若只部署当前教材上传纵向演示，必须明确标注为受控联调环境，不得开放尚未完成的创作、交付和管理入口，也不得描述为完整产品发布。

## Web 服务器要求

- 所有前端路由回退到 `index.html`；
- `/api/v2`、项目 SSE 和 Generation Job SSE 反向代理到同一受信后端；
- 代理必须支持流式响应，关闭 SSE 缓冲并保留 `Last-Event-ID`；
- 对象存储上传地址必须允许合同返回的 method、required headers 和 ETag 暴露；
- Cookie 保持 `Secure`、`HttpOnly` 和适当的 `SameSite`；
- 服务端认证 bootstrap 提供 CSRF token，由前端以内存读取器注入 `X-CSRF-Token`；未完成该合同前不得开放 Cookie 写操作；
- 静态哈希资源设置长期缓存，`index.html` 不使用长期不可变缓存；
- 保留上一版静态产物和发布标识，以便快速回滚。

## 部署后验证

当前 Runtime 范围至少检查：

1. `/app`、`/app/projects`、`/app/projects/new` 和项目详情可直接打开、刷新和返回；
2. 未认证、无权限、会话过期和 CSRF 缺失均安全失败，不出现 Mock 假成功；
3. 项目创建后能够完成教材 SHA-256、上传会话、对象存储 PUT、ETag 与确认请求；
4. setup 页面刷新后可凭 `jobId` 恢复 Job REST 快照，SSE 中断后携带 `Last-Event-ID` 重连；
5. 409/`EVENT_HISTORY_EXPIRED` 会清除游标并重新读取 REST 快照，任务取消和失败不会显示为成功；
6. Job 成功后能够读取课时和项目概览，AutomationPolicy 并发更新不会绕过 ETag；
7. 生产网络请求中不存在 MSW 注册、演示凭据或浏览器本地业务真相；
8. 浏览器控制台、错误上报和访问日志不显示密钥、完整教材、签名 URL 或内部供应商响应。

后续 Runtime 页面开放时，再把对应 Workflow、Artifact、素材槽位、创作四动作、任务、交付和管理端流程加入同一部署验收，不提前把开发 Mock 流程列为已通过项。

## 回滚

1. 将静态站点指向上一版已验证产物；
2. 恢复上一版 `VITE_RELEASE_VERSION` 对应的错误追踪标识；
3. 不回滚后端数据、上传对象或不可变内容版本，除非后端有独立迁移回退方案；
4. 验证认证、项目列表、项目详情、关键直达 URL 和上传链的安全失败/恢复；
5. 记录失败版本、影响范围和后续修复 Issue。
