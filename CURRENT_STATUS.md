# 当前项目状态

当前阶段：阶段1教师可见R1纵向链的历史PR已经收敛，#217进入最终状态同步与唯一入口确认。
> 最后核验：2026-07-25。
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
- [PR #212](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/212)已经完成相对`main`的26文件价值矩阵；现行runner、delivery schema和真实API门禁均以`main`为准，旧通用治理控制面零提取，PR及分支已经关闭清理。
- [PR #209](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/209)已经完成独有价值审计并标记为historical video WIP；未完成的视频runtime零代码提取，PR及分支已经关闭清理，不恢复视频开发。
- [PR #215](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/215)保持关闭；对应Issue、远端/本地分支和worktree均已核验无残留，没有重新审计或恢复其治理合同。
- [PR #208](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/208)已经完成27文件的复用、覆盖、失效、重写和删除矩阵；同步`startNodeRun`、不存在的审核路径、固定Artifact key和跨模块ORM不能进入主线，决定关闭旧PR并从最新`main`重建，旧分支已经清理。

## 当前工作

- [Issue #217](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/217)只负责收敛开放PR和重建唯一R1入口，不新增业务功能或治理框架。
- 历史竞争PR已经全部关闭；#217当前只剩最小状态同步、同一既有只读reviewer的最终复核、合并关闭和任务分支清理。
- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)在#217关闭前保持`status:blocked`；随后唯一允许的实现入口是从当时最新`origin/main`创建`feat/11-real-teacher-r1`和一个新的Draft PR，不恢复PR #208或其分支。
- #11的第一个原子动作是先确认最小Contract Change：`startNodeRun`返回`202 AcceptedJob`并绑定现有Job/Worker/SSE；教材范围合法修订及质量阶段到`reviewArtifactVersion`的正式HTTP顺序必须同时明确，合同未确认前不得自造接口。

## 当前阻塞

- 当前没有已知的Session/CSRF实现阻塞；#211已经合并、关闭并从最新`main`复验。
- 当前没有竞争修改Session、active OpenAPI、生成客户端或`apps/web`公共入口的开放业务PR；#208、#209、#212和#215均已关闭。
- 阶段1完整教师R1纵向链尚未验收；教材列表与范围修订、异步节点启动、质量/批准HTTP闭环、生产页面消费者、真实文本Provider和R1 real API Playwright仍是#11待实现事实。
- #217完成前，不开始#11实现、PPT、图片、视频、TTS或新的治理框架，也不竞争修改active OpenAPI、生成客户端、Artifact/Job公共合同、Workflow Binding、Model Gateway或前端公共Session入口。

## 下一个阶段出口

1. 合并#217的最小状态同步，由同一既有只读reviewer绑定最终base/head；随后关闭#217并删除其分支和worktree。
2. 从最新`origin/main`创建`feat/11-real-teacher-r1`和新的Draft PR，将Issue #11转回`status:in-progress`。
3. 先在#11/#210确认异步`startNodeRun`、教材范围修订和质量/批准HTTP顺序的最小Contract Change，再同步active OpenAPI、FastAPI和生成客户端。
4. 只推进“真实登录 -> 项目 -> 教材与物理页 -> 课时划分 -> LessonUnit -> 十二部分教案 -> 三类九套 -> 批准 -> 唯一IntroSelection -> 刷新恢复”的生产页面、PostgreSQL、Job/Worker/SSE、真实Provider和real API Playwright闭环。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. 当前任务只接受#217的状态同步、最终只读复核和关闭清理；不要从旧PR恢复实现。
3. #211的当前运行证据以`main`中的代码、迁移、测试、active OpenAPI和`contracts/delivery-slices/211-runtime-auth.yaml`为准；PR #216保留合并前CI与独立审查证据。
4. PR #208已经关闭且不得恢复；#11必须在#217关闭后从最新`main`建立新的唯一短分支和Draft PR。
