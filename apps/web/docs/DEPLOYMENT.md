# 构建、部署与回滚

责任人：前端承接方
读者：部署、运维与前端负责人
规范路径：`apps/web/docs/DEPLOYMENT.md`
替换规则：部署方式变化时在本文件原位更新

## 当前交付边界

当前前端是阶段0的Mock-first工程基线。`pnpm build`用于验证类型、打包和开发内容边界；由于真实认证和完整业务API尚未接入，且源码仍包含Mock Runtime代码，该产物不得作为生产发布批准。

## 构建验证

```powershell
cd apps\web
pnpm install --frozen-lockfile
pnpm generate:api
pnpm format
pnpm lint
pnpm typecheck
pnpm test
pnpm build:storybook
pnpm build
pnpm exec playwright test --project=chromium --workers=2
```

构建产物位于 `apps/web/dist`。进入生产部署前必须同时满足：

1. 真实认证bootstrap、Cookie、CSRF和权限合同完成并通过安全测试；
2. 项目、上传、任务、SSE、成果和保存冲突完成真实API联调；
3. 生产入口不再依赖Mock Runtime、演示数据或浏览器本地业务状态；
4. 真实环境的前端CI、合同测试和关键浏览器流程通过；
5. 有可访问预览、发布标识、监控和可验证回滚产物。

满足前置条件后设置：

```text
VITE_API_MODE=real
VITE_API_BASE_URL=/api/v2
VITE_RELEASE_VERSION=<发布标识>
```

不要把 `.env.local`、真实教材、签名下载地址、服务密钥、Mock数据或演示凭据复制到产物目录。

## Web 服务器要求

- 所有前端路由回退到 `index.html`；
- `/api/v2` 和 SSE 端点反向代理到后端；
- Cookie 保持 `Secure`、`HttpOnly` 和适当的 `SameSite`；
- 服务端认证 bootstrap 必须提供 CSRF token，并由前端以内存读取器注入 `X-CSRF-Token`；未完成该合同前不得开放 Cookie 写操作；
- 静态哈希资源设置长期缓存，`index.html` 不使用长期不可变缓存；
- 保留上一版静态产物和发布标识，以便快速回滚。

## 验证

部署后至少检查：

1. `/app`、项目工作台、创作中心和管理端可直接打开与刷新；
2. 登录 Cookie、项目查询、文件上传会话和短期下载授权可用；
3. 生成任务刷新后继续，SSE 中断后可以恢复；
4. 409 编辑冲突和保存位置占用不会覆盖旧版本；
5. 生产网络请求中不存在 `mockServiceWorker.js` 注册；
6. 浏览器控制台不显示密钥、完整教材或内部供应商响应。

## 回滚

1. 将静态站点指向上一版已验证产物；
2. 恢复上一版 `VITE_RELEASE_VERSION` 对应的错误追踪标识；
3. 不回滚后端数据或内容版本，除非后端有独立迁移回退方案；
4. 验证登录、项目列表、关键直达 URL 和下载；
5. 记录失败版本、影响范围和后续修复任务。
