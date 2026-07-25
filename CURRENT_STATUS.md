# 当前项目状态

当前阶段：阶段1教师可见R1纵向链已拆为7个严格串行的child Issues和短PR；当前只推进第一个项目事实查询切片#223。
> 最后核验：2026-07-25。
> 当前唯一P0：[Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)；当前child为[Issue #223](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/223)与Draft [PR #230](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/230)。

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

- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)保持`status:in-progress`，已经批准按#223至#229严格串行推进；前一child合并并从最新`origin/main`复验后，下一child才解除阻塞。
- [PR #222](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/222)只保留102文件大现场的远端WIP恢复证据，固定Head为`19f517a8d3c545a82f929583b0ec4f8eb09dd1e5`；不再新增实现、不直接转Ready或合并。
- [Issue #223](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/223)当前为`status:in-progress`；分支`feat/223-r1-contract-queries`和Draft [PR #230](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/230)从`origin/main@0450b04d`建立，只激活项目材料、Artifact和GenerationJob查询。
- #224至#229保持`status:blocked`；在#223合并前不开始教材范围写命令、Worker/质量闭环、前端页面、real API或真实Provider验收。

## 当前阻塞

- 当前没有已知的Session/CSRF实现阻塞；#211已经合并、关闭并从最新`main`复验。
- 当前没有竞争修改Session、active OpenAPI、生成客户端或`apps/web`公共入口的开放业务PR；#208、#209、#212和#215均已关闭。
- 阶段1完整教师R1纵向链尚未验收；教材列表与范围修订、异步节点启动、质量/批准HTTP闭环、生产页面消费者、真实文本Provider和R1 real API Playwright仍是#11待实现事实。
- #223的本地定向合同、PostgreSQL、OpenAPI surface、类型和仓库治理验证已通过；PR #230的CI与最终独立reviewer尚未完成，不得声明本切片已合并或可用于完整R1。
- #224仍被#223阻塞；Job的`lesson_id`过滤依赖#225新增正式`lesson_unit_id`持久字段和Alembic迁移，不得提前塞入无迁移的#223。

## 下一个阶段出口

1. 完成PR #230的CI、最终base/head自审和一次独立只读reviewer审查；关闭findings后才可转Ready。
2. Squash Merge #223，从干净`origin/main`复验三个项目查询，再把#224从blocked转为ready并创建独立短分支。
3. 严格按#224教材范围/prepare、#225异步运行时、#226质量批准、#227前端消费者、#228生产页面、#229最终验收推进；每项独立验收和回退。
4. #229以前不把deterministic Fake/HTTP stub称为真实Provider验收，也不恢复PPT、图片、视频或TTS开发。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. #217和PR #219已经完成并清理；不要从旧PR恢复实现，也不要把历史矩阵当作可直接合并的代码。
3. #211的当前运行证据以`main`中的代码、迁移、测试、active OpenAPI和`contracts/delivery-slices/211-runtime-auth.yaml`为准；PR #216保留合并前CI与独立审查证据。
4. PR #208已经关闭且不得恢复；PR #222只能作为固定WIP检查点按文件/hunk提取。当前只接续#223/PR #230，禁止整体cherry-pick或并发启动#224至#229。
