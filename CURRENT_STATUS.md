# 当前项目状态

当前阶段：阶段1后端基座以及R1教材范围、课时划分、十二部分教案和三类九套四个教师可见文本结果已经合并；当前只做合并后状态收口，并保留受控真实文本Provider最终门禁。
> 最后核验：2026-07-26。
> 当前任务：[Issue #239](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/239)；只修正#235合并后的主线状态与清理事实，不修改业务实现。

## 当前可演示成果

- `main`已经包含生产Session/CSRF启动闭环：生产前端`/login`通过真实FastAPI和PostgreSQL使用受控access code登录，不依赖localStorage、sessionStorage、测试Cookie、MSW或浏览器拦截伪造身份。
- 从最新`origin/main`创建的干净临时worktree已经通过真实API完成“登录 -> 带Session和CSRF创建项目 -> 刷新恢复同一Session -> 登出 -> 原Session与CSRF失效 -> 后续写请求返回401”。
- `main`已经通过真实API完成“打开已有LessonUnit -> 异步生成十二部分教案 -> 编辑保存 -> 质量检查 -> 批准exact ArtifactVersion -> 刷新恢复 -> 双课时隔离 -> 登出写入401”。
- `main`已经通过真实API完成“打开真实教材页事实 -> 保存并批准exact范围 -> 异步课时划分 -> 编辑保存 -> 质量检查 -> 批准exact ArtifactVersion -> 刷新恢复 -> 双项目隔离 -> 登出写入401”。
- `main`已经通过真实API完成“三类各三套异步生成 -> 编辑保存 -> 质量检查 -> 批准exact ArtifactVersion -> 采用唯一方案 -> 刷新恢复 -> 双课时隔离 -> 登出写入401”。
- merge commit `44e37ca`的main push workflow已经精确通过11个PostgreSQL backend selector、5个real API browser selector和Alembic升降级循环；本地主worktree也已通过生产前端build和相同11个backend selector。

## 已完成

- [Issue #211](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/211)已经由[PR #216](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/216)Squash Merge并关闭；`createSession`、`getCurrentSession`和`deleteSession`已经进入active OpenAPI、FastAPI运行时和生成的TypeScript客户端。
- SQLAlchemy Session模型、Alembic迁移、Session绑定CSRF、前端Session Provider、PostgreSQL集成测试、真实API Playwright和`contracts/delivery-slices/211-runtime-auth.yaml`已经同步进入`main`。
- PR #216最终Head的前端、后端、合同、PostgreSQL、真实浏览器和仓库治理CI全部通过；同一独立只读reviewer绑定最终base/head，P0/P1/P2/P3均为0。
- 合并后复验在干净`origin/main` worktree运行，生产前端build通过；delivery slice精确通过3个backend selector和3个real API browser selector，零skip、xfail、xpass和flaky，测试进程及监听端口均已清理。
- [Issue #217](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/217)已经由[PR #219](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/219)Squash Merge并关闭；同一既有只读reviewer绑定最终base/head，P0/P1/P2/P3均为0，最终CI全部通过。
- #217已经完成历史PR价值矩阵、唯一R1入口决定和状态同步；`docs/217-convergence-status`的远端/本地分支与隔离worktree均已删除。
- [PR #212](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/212)已经完成相对`main`的26文件价值矩阵；现行runner、delivery schema和真实API门禁均以`main`为准，旧通用治理控制面零提取，PR及分支已经关闭清理。
- [PR #209](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/209)已经完成独有价值审计并标记为historical video WIP；未完成的视频runtime零代码提取，PR及分支已经关闭清理，不恢复视频开发。
- [PR #215](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/215)保持关闭；对应Issue、远端/本地分支和worktree均已核验无残留，没有重新审计或恢复其治理合同。
- [PR #208](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/208)已经完成27文件的复用、覆盖、失效、重写和删除矩阵；同步`startNodeRun`、不存在的审核路径、固定Artifact key和跨模块ORM不能进入主线，决定关闭旧PR并从最新`main`重建，旧分支已经清理。
- [Issue #231](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/231)已经由[PR #232](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/232)Squash Merge并关闭；合并提交`5e56ac4`的repository governance、真实API、前端和后端/PostgreSQL main工作流全部通过。
- [Issue #234](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/234)已经由[PR #236](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/236)交付并关闭；生产页面、active OpenAPI、FastAPI、现有Worker、生成客户端、PostgreSQL集成测试和真实API Playwright共同形成教材范围与课时划分教师闭环。
- [Issue #235](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/235)已经由[PR #238](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/238)Squash Merge并关闭；三类九套生成、编辑、质量检查、exact批准、唯一采用、刷新恢复和最终R1真实API浏览器链已经进入`main`，独立reviewer绑定最终base/head且P0/P1/P2/P3均为0。

## 当前工作

- [Issue #239](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/239)只负责把#235/#238合并、main复验和下一门禁写回本文件，并在合并后清理#235与#239的本地现场。
- Parent [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)仍保持开放；只有受控真实文本Provider通过现有Model Gateway形成脱敏证据后，才能执行最终R1 release收口并关闭父任务。
- [Draft PR #222](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/222)冻结为固定WIP代码来源，不新增代码、不直接合并；[Draft PR #230](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/230)暂停，不转Ready、不默认合并。#223至#229只保留为参考清单，不再强制串行。

## 当前阻塞

- 当前没有已知的Session/CSRF、PostgreSQL、Worker、active OpenAPI或生产页面实现阻塞；四个教师文本结果及完整真实API浏览器链已经进入`main`。
- Parent #11的最终release门禁仍缺受控真实文本Provider实测证据；普通CI确定性Fake和真实API浏览器通过均不能冒充真实Provider完成。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)单独跟踪`origin/main`既有Stage1 E2E旧`impact_scope` fixture；该测试债不改变#231验收结果，也不在救援PR内顺手修复。
- [Issue #237](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/237)单独跟踪文件长度后置项；PPT、图片、视频、TTS、通用查询/审批/状态机、SSE重构和全仓技术债均不在#239范围。

## 下一个阶段出口

1. 合并#239，确认`CURRENT_STATUS.md`、GitHub Issue/PR和main只保留一套当前状态，并清理#235/#239本地现场。
2. 在Parent #11下建立或领取唯一教师可见的受控真实文本Provider验收任务，只复用现有Model Gateway和已合并四个文本结果，不扩展媒体或通用平台。
3. 受控Provider、脱敏审计、完整真实API浏览器链和main复验同时通过后，才更新最终release状态并关闭#11。
4. 后续仍以教师可见结果为合并单位，不恢复#223至#229的技术层严格串行关系。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. #239是唯一实时docs收口入口；#231、#234和#235已经完成四个教师文本结果，禁止恢复按技术层严格串行的旧执行方式。
3. #222继续冻结、#230继续暂停；#223至#229只作参考，不得从中恢复通用查询、审批、状态机或SSE重构。
4. 下一任务必须先核验#11的受控真实文本Provider缺口；生产Session/CSRF、Artifact、LessonPlanRuntime、GenerationJob、Worker、SSE、QualityReport、Approval和Model Gateway全部复用，不建设第二套系统。
