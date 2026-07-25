# 当前项目状态

当前阶段：阶段1教师可见R1纵向链已经在#11唯一Draft PR形成冻结的WIP检查点；最小Contract Change已确认，完整R1尚未验收。
> 最后核验：2026-07-25。
> 当前唯一P0：[Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)，状态为`status:in-progress`。

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

- 历史竞争PR已经全部关闭；[PR #222](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/222)是当前唯一R1业务Draft PR。
- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)是唯一业务主线；`feat/11-real-teacher-r1`已经从最新`origin/main`建立，不恢复PR #208或其分支。
- #11/#210已经确认最小Contract Change；当前WIP覆盖合同与数据命令、后端Worker/质量闭环、前端消费者/SSE以及最终验收拓扑，但尚未形成可合并的短PR序列。
- 本地真实API浏览器曾运行到教材范围批准和课时划分生成；先后定位前端SSE缓存失效和deterministic HTTP测试Provider重复request ID，两个最小修复均已落盘。request ID修复后未重新运行浏览器验收。
- deterministic HTTP Provider仅用于可重复测试，不是受控真实文本Provider验收证据；在拆分方案确认前冻结新增实现，不继续追查下一业务失败。

## 当前阻塞

- 当前没有已知的Session/CSRF实现阻塞；#211已经合并、关闭并从最新`main`复验。
- 当前没有竞争修改Session、active OpenAPI、生成客户端或`apps/web`公共入口的开放业务PR；#208、#209、#212和#215均已关闭。
- 当前WIP超过20个文件和800行门禁，不能作为一个长期PR继续扩展；必须先按合同与数据命令、后端Worker/质量、前端消费者/SSE、最终验收拆成串行child Issues和短PR。
- 当前仓库治理门禁失败：存在11个未授权跨模块ORM import和11个文件/函数规模所有权错误；这些问题尚未修复，当前Draft不具备Ready条件。
- 阶段1完整教师R1纵向链尚未验收；PostgreSQL集成组、迁移循环、delivery slice、修复后的real API Playwright、受控真实文本Provider和最终独立审查均未形成最终证据。
- #11的最小Contract Change已经确认，当前没有产品决策阻塞；PPT、图片、视频、TTS和新的治理框架继续暂停。

## 下一个阶段出口

1. 先把当前冻结现场推送为远端WIP检查点，并让PR #222准确记录真实规模、Review Map、已通过/失败/未运行证据。
2. 由#11保留父结果，确认串行child Issues和短PR的文件边界、依赖、验收与回退；在此之前不恢复新增实现。
3. 最终短PR以PostgreSQL集成测试、迁移循环、real API Playwright、delivery slice和受控真实文本Provider共同验收完整R1，并由同一未参与实现的reviewer绑定实际最终base/head。
4. R1合并验收前不恢复PPT、图片、视频、TTS或新的治理开发。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. #217和PR #219已经完成并清理；不要从旧PR恢复实现，也不要把历史矩阵当作可直接合并的代码。
3. #211的当前运行证据以`main`中的代码、迁移、测试、active OpenAPI和`contracts/delivery-slices/211-runtime-auth.yaml`为准；PR #216保留合并前CI与独立审查证据。
4. PR #208已经关闭且不得恢复；PR #222是唯一实现入口，按#11/#210已经确认的最小Contract Change推进。
