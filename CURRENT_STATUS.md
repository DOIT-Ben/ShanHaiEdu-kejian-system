# 当前项目状态

当前阶段：阶段1教师可见R1纵向链进入开放PR收敛与唯一入口重建。
> 最后核验：2026-07-24。
> 当前唯一P0：[Issue #217](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/217)。

## 当前可演示成果

- `main`已经包含生产Session/CSRF启动闭环：生产前端`/login`通过真实FastAPI和PostgreSQL使用受控access code登录，不依赖localStorage、sessionStorage、测试Cookie、MSW或浏览器拦截伪造身份。
- 从最新`origin/main`创建的干净临时worktree已经通过真实API完成“登录 -> 带Session和CSRF创建项目 -> 刷新恢复同一Session -> 登出 -> 原Session与CSRF失效 -> 后续写请求返回401”。
- `main`已有项目、上传、教材解析、课时、Artifact、QualityReport、Approval、IntroSelection、Job/Worker/SSE和模型网关等阶段1后端轨道基础；这些已实现能力不等于#11的完整教师R1纵向链已经验收。

## 已完成

- [Issue #211](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/211)已经由[PR #216](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/216)Squash Merge并关闭；`createSession`、`getCurrentSession`和`deleteSession`已经进入active OpenAPI、FastAPI运行时和生成的TypeScript客户端。
- SQLAlchemy Session模型、Alembic迁移、Session绑定CSRF、前端Session Provider、PostgreSQL集成测试、真实API Playwright和`contracts/delivery-slices/211-runtime-auth.yaml`已经同步进入`main`。
- PR #216最终Head的前端、后端、合同、PostgreSQL、真实浏览器和仓库治理CI全部通过；同一独立只读reviewer绑定最终base/head，P0/P1/P2/P3均为0。
- 合并后复验在干净`origin/main` worktree运行，生产前端build通过；delivery slice精确通过3个backend selector和3个real API browser selector，零skip、xfail、xpass和flaky，测试进程及监听端口均已清理。

## 当前工作

- [Issue #217](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/217)只负责收敛开放PR和重建唯一R1入口，不新增业务功能或治理框架。
- [PR #212](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/212)仍为开放Draft，必须相对最新`main`形成文件级价值矩阵，只允许最小提取确实不可缺少且未被覆盖的内容，否则关闭。
- [PR #209](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/209)仍为开放Draft，只审计独有价值后标记为historical video WIP并关闭，不恢复视频开发。
- [PR #208](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/208)仍为开放Draft，必须先形成复用、覆盖、失效、重写和删除矩阵，再决定重整或从最新`main`重建；当前不得继续实现。
- [PR #215](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/215)已经关闭；#217只核验其远端分支和本地现场清理状态，不重新审计内容。

## 当前阻塞

- 当前没有已知的Session/CSRF实现阻塞；#211已经合并、关闭并从最新`main`复验。
- 阶段1完整教师R1纵向链尚未验收。PR #208、#209和#212仍占用历史口径，必须由#217先确认独有价值并收口，不能直接恢复任何旧分支开发。
- #217完成前，不开始#208实现、PPT、图片、视频、TTS或新的治理框架，也不竞争修改active OpenAPI、生成客户端、Artifact/Job公共合同、Workflow Binding、Model Gateway或前端公共Session入口。

## 下一个阶段出口

1. 对PR #212形成文件级价值矩阵，决定最小提取或废弃并关闭旧PR。
2. 对PR #209只核验独有价值，记录historical video WIP结论并关闭；核验PR #215已关闭且分支现场已清理。
3. 对PR #208形成复用、覆盖、失效、重写和删除矩阵，明确重整旧PR或关闭后从最新`main`重建。
4. #217收口后，唯一业务主线回到Issue #11，并且只使用一个来自最新`main`的短分支和Draft PR推进真实教师R1纵向链。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. 当前任务只接受#217的只读价值审计、PR关闭清理和唯一R1入口决定；不要从旧PR恢复实现。
3. #211的当前运行证据以`main`中的代码、迁移、测试、active OpenAPI和`contracts/delivery-slices/211-runtime-auth.yaml`为准；PR #216保留合并前CI与独立审查证据。
4. PR #208只有在#217矩阵完成并明确处置后才能恢复，且必须从最新`main`核对接口与正式事实。
