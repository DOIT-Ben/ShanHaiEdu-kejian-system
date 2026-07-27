# 当前项目状态

当前阶段：阶段1后端基座以及R1教材范围、课时划分、十二部分教案和三类九套四个教师可见文本结果已经进入`main`；受控真实文本Provider教师黄金项目已通过，正在完成独立审查、合并和`main`复验。
> 最后核验：2026-07-27。
> 当前任务：[Issue #241](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/241)与[Draft PR #242](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/242)承载最终交付收口；真实验收已通过，仍待审查发现关闭、合并、`main`复验和清理。

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
- [Issue #241](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/241)的`1.5.3`受控真实文本Provider教师黄金项目已经通过：生产Worker经现有Model Gateway完成5次`NewAPI -> deepseek`流式请求，两个真实API浏览器场景`2 passed (8.2m)`，并生成Schema有效的脱敏passed receipt。
- 本次receipt包含3个正式Artifact、4个exact GenerationJob、5个GenerationAttempt、exact Approval与唯一Intro选择事实；SHA-256为`46c5bb6f13add7dea7d7002004ee6cf554893be74b280d259f6e7af43f912e21`，不包含密钥、Prompt或模型正文。

## 当前工作

- [Issue #239](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/239)已经由[PR #240](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/240)完成主线状态收口并关闭。
- [Issue #241](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/241)的[Draft PR #242](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/242)已通过真实验收，正在修复独立审查发现；生产Worker在未注入测试模型时通过现有`build_real_text_gateway()`调用真实文本Provider，普通CI继续使用确定性Fake。
- #242只增加受控黄金项目、脱敏receipt、现有Provider流式接线和验收发现的最小质量修复，没有建设新的Provider平台、Worker队列、状态机或治理框架。
- #242前向内容包为`1.5.3`：保持不可变`1.5.2`及既有项目绑定不变，将`validator.intro.single_anchor`前向升级为`1.2.1`；课堂实际呈现字段继续扫描冻结主题，教师侧`fit_reason`不再作为课堂内容扫描，旧`1.2.0`和`1.1.0`仍按原行为注册。
- `secondary_tendencies`及跨倾向阻塞门禁已从现行Schema、内容包和运行质量合同删除；第一阶段禁止自评分，第二阶段不得漏评、多评或改写候选正文。正常成功为1个Job、2个成功GenerationAttempt；首轮评分非法时同一Job有界重投一次，只重跑评分并复用已持久化候选，成功时共3个Attempt。
- `1.5.3`不改变active OpenAPI、生成TypeScript客户端、Worker、Job、Artifact、Approval或页面合同；交付分支通过940项完整单元/合同测试和95项相关PostgreSQL内容包、Intro runtime、Worker与质量运行时测试。发布回归固定`1.5.2`的package/workflow checksum，并验证旧发布行与既有项目绑定不变。
- 真实API浏览器验收只在真实模式且exact三类九套Job以`MODEL_TIMEOUT`失败时允许教师页面重试一次，不改变生产Worker、状态机或通用Provider行为；Ruff format/check、Pyright、仓库治理、密钥扫描和`git diff --check`也已通过。
- OpenAI-compatible文本Provider由服务端消费并聚合SSE，必须同时取得正文、finish reason、usage和`[DONE]`，截断、坏JSON、身份漂移或usage缺失均失败关闭。
- `1.5.3`修复后的全新黄金项目最终为`2 passed`：主课时十二部分教案、三类九套生成与独立统一评分、第二课时隔离，以及教材范围与课时划分均通过；不存在`INTRO_PRETEACH_VIOLATION`或其他质量finding。
- 本次5次Provider调用均HTTP 200：主课时教案139.867秒、Intro候选68.644秒、Intro评分49.465秒、隔离课时教案179.881秒、课时划分18.473秒；合计16,520 prompt tokens和28,826 completion tokens。
- Parent [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)的受控真实文本Provider门禁已有passed receipt，最终关闭仍以#242合并和`main`复验为准。
- [Draft PR #222](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/222)冻结为固定WIP代码来源，不新增代码、不直接合并；[Draft PR #230](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/230)暂停，不转Ready、不默认合并。#223至#229只保留为参考清单，不再强制串行。

## 当前阻塞

- 当前没有已知的Session/CSRF、PostgreSQL、Worker、active OpenAPI、生产页面或真实文本Provider验收阻塞；#242合并仍受独立审查发现、最终CI和exact Head复核约束。
- 真实黄金项目已经生成passed receipt；不再调用Provider。普通CI继续只允许确定性Fake，不得把真实模型内容写入仓库测试夹具。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)单独跟踪`origin/main`既有Stage1 E2E旧`impact_scope` fixture；该测试债不改变#231验收结果，也不在救援PR内顺手修复。
- [Issue #237](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/237)单独跟踪文件长度后置项；PPT、图片、视频、TTS、通用查询/审批/状态机、SSE重构和全仓技术债均不在#241范围。

## 下一个阶段出口

1. 关闭#242的独立审查发现，等待最终CI，由同一reviewer绑定exact Head；通过后转Ready并Squash Merge，再从干净`origin/main`复验和清理。
2. #222继续冻结、#230继续暂停；#223至#229仅作参考，不恢复技术层严格串行关系。
3. PPT、图片、视频、TTS和其他媒体能力仍不在本轮范围，必须单独决策和验收。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. #231、#234和#235已经完成R1四个教师文本结果；#241真实Provider验收已通过但尚待合并收口，禁止恢复按技术层严格串行的旧执行方式。
3. #222继续冻结、#230继续暂停；#223至#229只作参考，不得从中恢复通用查询、审批、状态机或SSE重构。
4. R1已经复用生产Session/CSRF、Artifact、LessonPlanRuntime、GenerationJob、Worker、SSE、QualityReport、Approval和Model Gateway；receipt不得包含密钥、Prompt或模型正文。
