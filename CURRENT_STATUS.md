# 当前项目状态

当前阶段：阶段1十二部分教案教师纵向救援已经合并并完成main复验；当前推进教材范围与课时划分教师纵向闭环。
> 最后核验：2026-07-25。
> 当前任务：[Issue #234](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/234)；任务分支`feat/234-material-scope-lesson-division`已经从最新`origin/main`建立，状态为`status:in-progress`。

## 当前可演示成果

- `main`已经包含生产Session/CSRF启动闭环：生产前端`/login`通过真实FastAPI和PostgreSQL使用受控access code登录，不依赖localStorage、sessionStorage、测试Cookie、MSW或浏览器拦截伪造身份。
- 从最新`origin/main`创建的干净临时worktree已经通过真实API完成“登录 -> 带Session和CSRF创建项目 -> 刷新恢复同一Session -> 登出 -> 原Session与CSRF失效 -> 后续写请求返回401”。
- `main`已经通过真实API完成“打开已有LessonUnit -> 异步生成十二部分教案 -> 编辑保存 -> 质量检查 -> 批准exact ArtifactVersion -> 刷新恢复 -> 双课时隔离 -> 登出写入401”。
- `main`已有项目、上传、教材解析、material_scope Artifact、课时划分运行时、LessonUnit、Job/Worker/SSE和模型网关基础；#234只补教材范围与课时划分的教师可见接线，不重建同类系统。

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

## 当前工作

- [Issue #234](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/234)以“真实教材上传与解析 -> 教师确认exact范围 -> 异步课时划分 -> 编辑保存 -> 刷新恢复”为单一教师结果。
- 当前main已经具备上传确认、教材解析查询、material_scope与lesson_division领域运行时、LessonUnit编辑、Artifact质量与批准、Job/Worker/SSE；缺口是刷新后教材发现、范围确认命令、课时划分启动与exact Artifact/Job恢复，以及对应生产页面接线。
- 实现只增加本切片必需的project/material/division窄接口和页面，不引入项目级通用Artifact/Job查询平台、第二状态机或SSE重构。
- [Draft PR #222](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/222)冻结为固定WIP代码来源，不新增代码、不直接合并；[Draft PR #230](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/230)暂停，不转Ready、不默认合并。#223至#229只保留为参考清单，不再强制串行。

## 当前阻塞

- 当前没有已知的Session/CSRF实现阻塞；#211已经合并、关闭并从最新`main`复验。
- 当前没有外部阻塞；#234从PostgreSQL红测试开始，只提取冻结WIP中经当前main重新验证的必要hunk。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)单独跟踪`origin/main`既有Stage1 E2E旧`impact_scope` fixture；该测试债不改变#231验收结果，也不在救援PR内顺手修复。
- 三类九套由[Issue #235](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/235)阻塞等待#234；PPT、图片、视频、TTS、通用查询/审批/状态机、SSE重构和全仓技术债均不在本轮范围。

## 下一个阶段出口

1. 用PostgreSQL测试固定教材、解析版本、范围、Job、ArtifactVersion和LessonUnit的exact绑定、幂等与租户/项目隔离。
2. 接通最小active API、现有Worker和生产页面，完成刷新恢复与真实API Playwright。
3. 通过OpenAPI生成客户端、前后端质量门禁和独立base/head审查后合并#234，并从干净`origin/main`复验。
4. #234关闭后解除#235阻塞，再以三类九套与最终R1教师验收为下一个纵向合并单位。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. #234是唯一实时任务入口；#11是父任务，#231是已完成上游教师结果，#235保持阻塞，不得恢复按技术层严格串行的旧执行方式。
3. #222只允许按#234范围提取必要文件或hunk，禁止整体cherry-pick；#230保持暂停，禁止把项目级通用Artifact/Job查询带入本切片。
4. #211的生产Session/CSRF和main已有Artifact、LessonPlanRuntime、GenerationJob、Worker、SSE、QualityReport、Approval、Model Gateway必须复用，不建设第二套系统。
