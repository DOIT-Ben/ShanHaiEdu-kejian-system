# 当前项目状态

当前阶段：阶段1后端基座以及R1教材范围、课时划分、十二部分教案和三类九套四个教师可见文本结果已经进入`main`；受控真实文本Provider教师黄金项目、独立审查、合并和`main`复验均已完成。当前正在交付首个教师可见媒体结果：约6秒课堂导入短片黄金纵向切片。
> 最后核验：2026-07-30。
> 当前任务：[Issue #205](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/205)由[Draft PR #247](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/247)承载；确定性Fake下的真实API教师闭环已经通过。一次授权的真实NewAPI请求已生成经SHA-256和ffprobe验证的6.041667秒MP4，但Worker因Adapter未声明可选时长字段而在正式采用前失败关闭；当前正在收口最小修复，尚待新final head的CI与独立审查。未经新的明确授权不得再次调用Provider、转Ready或合并。

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

- #165的relay/cleanup部署合同、阶段化脱敏失败证据和systemd运行来源门禁已进入`main`；本PR不重复迁移生产服务器，也不调用付费Provider。
- [Issue #205](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/205)正在交付“exact已采用IntroSelection + 同课时正式关键帧 -> 异步生成约6秒MP4 -> 进度/失败可见 -> 播放 -> exact采用 -> LessonUnit槽位写回 -> 刷新恢复”的教师纵向闭环；[Draft PR #247](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/247)是唯一实现现场。
- #205复用现有Session/CSRF、LessonUnit、IntroSelection、ArtifactVersion、NodeRun、GenerationJob、Worker、Model Gateway、对象存储、FileAssetVersion、GenerationResult/Adoption和生成客户端，没有新增第二套任务、候选、采用、文件或前端DTO。
- 当前分支已通过active OpenAPI/生成客户端、PostgreSQL视频隔离与采用、Worker MP4校验、前端质量/构建，以及14个backend和5个real API browser delivery selectors；浏览器视频场景使用确定性Fake经FFmpeg形成真实6秒MP4，不代表真实视频Provider验收。
- 公网NewAPI `v1.9.0`已经提供`POST /v1/files`、私有`file_id`、Provider签名内容读取和`first_frame_file_id`视频提交合同；#205适配器现已改为校验内部正式关键帧后上传临时文件，不再把自建relay URL作为视频输入。
- 2026-07-30的一次授权真实请求已完成且未重试：临时关键帧上传1次、视频提交1次；Provider返回的MP4为`video/mp4`、1,465,128字节，SHA-256为`f120bc77057de1dc9b80d230667d2f9502644d00097940999335894a350f5d75`，ffprobe为6.041667秒、736x400。验收因NewAPI Adapter未填`GeneratedFileFact.duration_seconds`而被Worker以`VIDEO_FILE_INVALID`失败关闭，未形成GenerationResult、Adoption或LessonUnit槽位写回；receipt不含密钥、Prompt、Provider task ID、storage key、临时URL或原始响应。
- #205正在以红测试收口最小修复：Provider未声明可选时长时继续以实际MP4的ffprobe结果为权威门禁；Provider明确声明错误时长仍失败关闭。新提交会使既有独立审查绑定失效，同一只读reviewer必须复核最终base/head。修复、CI和审查完成前PR保持Draft，未经董事长新的明确授权不得再次调用Provider、转Ready或合并。
- [Issue #239](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/239)已经由[PR #240](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/240)完成主线状态收口并关闭。
- [Issue #241](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/241)已由[PR #242](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/242)完成技术交付；生产Worker在未注入测试模型时通过现有`build_real_text_gateway()`调用真实文本Provider，普通CI继续使用确定性Fake。
- #242只增加受控黄金项目、脱敏receipt、现有Provider流式接线和验收发现的最小质量修复，没有建设新的Provider平台、Worker队列、状态机或治理框架。
- #242前向内容包为`1.5.3`：保持不可变`1.5.2`及既有项目绑定不变，将`validator.intro.single_anchor`前向升级为`1.2.1`；课堂实际呈现字段继续扫描冻结主题，教师侧`fit_reason`不再作为课堂内容扫描，旧`1.2.0`和`1.1.0`仍按原行为注册。
- `secondary_tendencies`及跨倾向阻塞门禁已从现行Schema、内容包和运行质量合同删除；第一阶段禁止自评分，第二阶段不得漏评、多评或改写候选正文。正常成功为1个Job、2个成功GenerationAttempt；首轮评分非法时同一Job有界重投一次，只重跑评分并复用已持久化候选，成功时共3个Attempt。
- `1.5.3`不改变active OpenAPI、生成TypeScript客户端、Worker、Job、Artifact、Approval或页面合同；交付分支通过940项完整单元/合同测试和95项相关PostgreSQL内容包、Intro runtime、Worker与质量运行时测试。发布回归固定`1.5.2`的package/workflow checksum，并验证旧发布行与既有项目绑定不变。
- 真实API浏览器验收只在真实模式且exact三类九套Job以`MODEL_TIMEOUT`失败时允许教师页面重试一次，不改变生产Worker、状态机或通用Provider行为；Ruff format/check、Pyright、仓库治理、密钥扫描和`git diff --check`也已通过。
- OpenAI-compatible文本Provider由服务端消费并聚合SSE，必须同时取得正文、finish reason、usage和`[DONE]`，截断、坏JSON、身份漂移或usage缺失均失败关闭。
- `1.5.3`修复后的全新黄金项目最终为`2 passed`：主课时十二部分教案、三类九套生成与独立统一评分、第二课时隔离，以及教材范围与课时划分均通过；不存在`INTRO_PRETEACH_VIOLATION`或其他质量finding。
- 本次5次Provider调用均HTTP 200：主课时教案139.867秒、Intro候选68.644秒、Intro评分49.465秒、隔离课时教案179.881秒、课时划分18.473秒；合计16,520 prompt tokens和28,826 completion tokens。
- Parent [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)的受控真实文本Provider门禁已有passed receipt，#242合并和`main`复验均已通过。
- [Draft PR #222](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/222)冻结为固定WIP代码来源，不新增代码、不直接合并；[Draft PR #230](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/230)暂停，不转Ready、不默认合并。#223至#229只保留为参考清单，不再强制串行。

## 当前阻塞

- #205当前阻塞在真实Provider验收未闭环：唯一已授权请求生成了有效MP4，但因Worker对可选Provider时长字段的错误前置要求而在采用前失败；最小修复完成后仍需新的明确授权才能再次执行真实Provider请求。不得把已验证的孤立MP4表述为GenerationResult、教师采用或LessonUnit槽位闭环。
- 当前没有已知的Session/CSRF、PostgreSQL、Worker、active OpenAPI、生产页面、真实文本Provider验收或R1收口阻塞。
- 真实黄金项目已经生成passed receipt；不再调用Provider。普通CI继续只允许确定性Fake，不得把真实模型内容写入仓库测试夹具。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)单独跟踪`origin/main`既有Stage1 E2E旧`impact_scope` fixture；该测试债不改变#231验收结果，也不在救援PR内顺手修复。
- [Issue #237](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/237)单独跟踪文件长度后置项；PPT、图片、视频、TTS、通用查询/审批/状态机、SSE重构和全仓技术债均不在#241范围。

## 下一个阶段出口

1. #205先完成可选Provider时长字段的最小修复、相关门禁和同一独立只读reviewer对新final base/head的审查绑定，关闭全部P0/P1并处置P2/P3；PR仍保持Draft。
2. 第二次真实视频Provider最短付费验收必须在调用前取得新的明确授权，并只保存脱敏文件、lineage与Usage事实；未经授权继续以确定性Fake为普通开发和CI证据，不恢复失败Job或重用私有Provider task。
3. 未经董事长在新任务中明确授权，不合并PR #247；完整图片链、母版剧本、粗/细分镜、多镜头、TTS、字幕、混音、时间线和长视频合成继续由后续独立Decision/Issue定界。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件。
2. #231、#234、#235和#241已经完成R1四个教师文本结果及真实Provider验收，禁止恢复按技术层严格串行的旧执行方式。
3. #222继续冻结、#230继续暂停；#223至#229只作参考，不得从中恢复通用查询、审批、状态机或SSE重构。
4. R1已经复用生产Session/CSRF、Artifact、LessonPlanRuntime、GenerationJob、Worker、SSE、QualityReport、Approval和Model Gateway；receipt不得包含密钥、Prompt或模型正文。
