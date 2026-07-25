# 当前项目状态

当前阶段：十二部分教案教师纵向救援已完成实现和本地门禁，等待#231/#232最终审查、CI与合并。
> 最后核验：2026-07-25。
> 当前唯一P0：[Issue #231](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/231)；任务分支`feat/231-lesson-plan-rescue`和[Draft PR #232](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/232)已经建立，状态为`status:in-progress`。

## 当前可演示成果

- `main`已经包含生产Session/CSRF启动闭环：生产前端`/login`通过真实FastAPI和PostgreSQL使用受控access code登录，不依赖localStorage、sessionStorage、测试Cookie、MSW或浏览器拦截伪造身份。
- 从最新`origin/main`创建的干净临时worktree已经通过真实API完成“登录 -> 带Session和CSRF创建项目 -> 刷新恢复同一Session -> 登出 -> 原Session与CSRF失效 -> 后续写请求返回401”。
- `main`已有项目、上传、教材解析、课时、Artifact、QualityReport、Approval、IntroSelection、Job/Worker/SSE和模型网关等阶段1后端轨道基础；这些已实现能力不等于#11的完整教师R1纵向链已经验收。

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

## 当前工作

- [Issue #231](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/231)是当前唯一P0；[Draft PR #232](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/232)已经完成lesson-scoped active API、应用服务、现有Worker接线、生产页面和验收测试。
- 真实API浏览器已从全新PostgreSQL数据库通过“生产登录 -> 打开已有LessonUnit -> 异步生成十二部分教案 -> 真实进度 -> 编辑保存 -> 质量检查 -> 批准exact ArtifactVersion -> 刷新恢复 -> 双课时隔离 -> 登出写入401”。
- active OpenAPI、FastAPI运行面与生成TypeScript客户端保持一致且相对`origin/main`兼容；查询只提供exact lesson-scoped Artifact与GenerationJob，不新增项目级通用查询平台。
- PostgreSQL集成测试、Alembic完整往返、后端静态门禁、完整前端门禁、确定性/runtime Playwright和真实API Playwright均已完成本地验证。
- [Draft PR #222](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/222)冻结为固定WIP代码来源，不新增代码、不直接合并；[Draft PR #230](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/230)暂停，不转Ready、不默认合并。#223至#229只保留为参考清单，不再强制串行。

## 当前阻塞

- 当前没有已知的Session/CSRF实现阻塞；#211已经合并、关闭并从最新`main`复验。
- 当前没有实现或外部阻塞；#232保持Draft，等待远端CI全部通过，再由未参与实现的只读reviewer绑定最终base/head完成审查。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)单独跟踪`origin/main`既有Stage1 E2E旧`impact_scope` fixture；该测试债不改变#231验收结果，也不在救援PR内顺手修复。
- 教材上传和范围确认、课时划分、三类九套、PPT、图片、视频、TTS、通用查询/审批/状态机、SSE重构和全仓技术债均不在本轮范围。

## 下一个阶段出口

1. 等待#232远端CI全部通过；若出现分支特有失败，只修复与本切片直接相关的问题并刷新验证证据。
2. 由未参与实现的只读reviewer绑定最终base/head完成全量diff审查；关闭全部P0/P1并处置P2/P3后将#232转Ready。
3. Squash Merge #232并从干净`origin/main`复验delivery slice、生产build和真实API教师闭环，关闭#231并清理任务分支/worktree。
4. 合并后分别建立“教材范围与课时划分”和“三类九套与最终R1验收”两个教师可见纵向任务。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. #231和#232是唯一实时任务入口；#11是父任务，#210是既有Decision，不得恢复按技术层严格串行的旧执行方式。
3. #222只允许按#231范围提取必要文件或hunk，禁止整体cherry-pick；#230保持暂停，禁止把项目级通用查询带入救援切片。
4. #211的生产Session/CSRF和main已有Artifact、LessonPlanRuntime、GenerationJob、Worker、SSE、QualityReport、Approval、Model Gateway必须复用，不建设第二套系统。
