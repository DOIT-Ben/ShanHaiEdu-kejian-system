# 当前项目状态

当前阶段：阶段1教师可见R1纵向链的生产身份启动门禁。
> 最后核验：2026-07-24。
> 当前唯一P0：[Issue #211](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/211)；实现载体为[Draft PR #216](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/216)。

## 当前可演示成果

- `main`已有项目、上传、教材解析、课时、Artifact、质量报告、批准、IntroSelection、Job/Worker/SSE和模型网关等阶段1运行时基础，但尚未包含#211的生产Session/CSRF启动闭环。
- 在`feat/211-runtime-auth`隔离短分支上，生产前端`/login`已经通过真实FastAPI和PostgreSQL使用受控access code登录，不依赖localStorage、sessionStorage、测试Cookie、MSW或浏览器拦截伪造身份。
- 该分支已经通过真实API完成“登录 -> 带Session和CSRF创建项目 -> 刷新恢复 -> 登出 -> 原Session与CSRF立即失效 -> 后续写请求失败”。
- 上述分支结果只有在PR #216通过独立审查、CI并合并后，才能作为`main`当前能力。

## 已完成

- #211分支已实现`POST /api/v2/auth/session`（`createSession`）、`GET /api/v2/auth/session`（`getCurrentSession`）和`DELETE /api/v2/auth/session`（`deleteSession`）。
- 已同步SQLAlchemy Session模型、Alembic迁移、active OpenAPI、生成的TypeScript客户端、FastAPI路由、前端Session Provider、后端集成测试、真实API Playwright和`contracts/delivery-slices/211-runtime-auth.yaml`。
- 已验证12个PostgreSQL Session/CSRF集成测试全部通过，包含受信代理追加链不能通过伪造最左地址绕过登录限流；Alembic空库upgrade/downgrade/upgrade通过。
- 合同生成前后哈希一致；OpenAPI lint、runtime surface、JSON Schema、TypeScript合同类型、对`origin/main`兼容性和仓库策略门禁通过。合同测试为226 passed；两个本机条件skip分别是Windows无符号链接权限和未注入数据库的stage0资源用例，后者已在PostgreSQL环境另行1 passed。
- 前端format、lint、typecheck、61个文件中的229个单测和生产build全部通过。
- delivery slice已通过精确3个backend selector和3个real API browser selector；每个selector均要求恰好一个通过并拒绝skip、xfail、xpass和flaky。
- delivery runner定向测试为13 passed，覆盖Windows pnpm shim、独立JSON报告、错误spec、skip/xfail/flaky以及backend/browser子进程超时。
- 全树Ruff、Pyright、tracked secret scan和`git diff --check`通过。

## 当前工作

- PR #216仍是Draft；#211实现和本文件当前状态已经提交并推送，PR正文已同步输入、输出、验收、验证和回退证据。
- 当前分支等待最新HEAD的CI和精确base/head独立审查，尚未转Ready或合并。
- 最终base/head必须由未参与实现的同一只读reviewer审查；任何修复导致HEAD变化时，由同一reviewer复核并重新绑定。

## 当前阻塞

- `main`在PR #216合并前没有生产Session/CSRF启动闭环，因此不能把分支验证结果声明为已发布能力。
- 当前没有已知实现阻塞；剩余门禁是独立审查、最新HEAD CI、Squash Merge及合并后复验。
- #211合并前，Issue #11 / PR #208、PPT、视频和新治理工作全部暂停，不得竞争active OpenAPI、生成客户端或公共Session入口。

## 下一个阶段出口

1. 由未参与实现的只读reviewer审查精确`origin/main...HEAD`；关闭全部P0/P1，处置P2/P3，并在最终HEAD重新绑定批准证据。
2. CI全绿后将PR转Ready并Squash Merge，关闭#211，删除任务分支和隔离worktree，从最新`main`复验关键Session/CSRF和delivery门禁。
3. 只有#211进入最新`main`后，才审查PR #208并形成复用、覆盖、失效、重写和删除矩阵，恢复唯一R1纵向链。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. 当前任务只接受#211及PR #216；不要从旧PR或历史文档恢复并行身份口径。
3. 核对分支、HEAD、upstream、dirty文件和GitHub实时状态；`AGENTS.md`是本机规则升级现场，不属于PR #216。
4. 真实验收入口是`contracts/delivery-slices/211-runtime-auth.yaml`及其runner；Mock、静态身份或浏览器拦截不能替代真实API验证。
5. 合并后的下一项工作是只读审计PR #208，而不是直接在旧分支继续堆代码。
