# 当前项目状态

更新时间：2026-07-23

验证基线：`main`；#130与PR #141、#146与PR #148、#89与PR #147、#133与PR #164、#134与PR #174、#125与PR #177、#126与PR #178、#116与PR #183、#127与PR #184、#128与PR #187、#129与PR #192、#170与PR #190及#118与PR #196已经进入当前树，Decision #185已经批准关闭；[Decision #199](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/199)与[Decision #201](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/201)把当前交付重心固定为教师可见MVP纵向闭环；不可变`1.1.0`、`1.2.0`与既有项目保持不变，当前树的`1.3.0`/`1.4.0`为待显式发布的前向候选；实现事实以本文件所在提交的代码、迁移和测试为准，任务状态以链接的GitHub Issue和Pull Request为准

当前阶段：阶段1后端轨道、公共基座和教材到Intro运行时已经具备，#118已补齐真实页面不能绕过的`material_scope`正式输出与教师保存路径。当前唯一出口是一个生产教师页面：选择已上传教材和物理页码，经服务端调用真实`newapi/deepseek`，展示课时划分、每课时十二部分教案和三类九套导入方案，支持编辑、局部重生成、批准、唯一选择，并在刷新后从正式API和PostgreSQL恢复。PPT、PPTX、图片、视频、TTS、失败重试和SSE hardening均不属于首个MVP完成条件。

本文件只描述现在，不保存开发日志。任务细节、负责人、讨论和交接以GitHub Issue与Pull Request为准。

## 当前可演示成果

- 后端已经具备可运行的FastAPI模块化单体、PostgreSQL、Redis、MinIO、Alembic、Worker、Outbox、SSE和幂等基座。
- API和测试已经覆盖租户与用户边界、项目、课时与分支、上传、文件资产与不可变版本、内容发布、工作流运行、产物审核与依赖、Prompt与Context快照、教材PDF解析以及项目资产原子绑定。
- OpenAPI、JSON Schema、生成TypeScript客户端、确定性Mock/Fake和后端CI已经进入自动门禁；文本模型网关已经完成受控真实冒烟。
- 正式发布的`shanhai.primary_math.courseware@1.0.0`继续固定原内容、v1工作流和既有项目绑定；不可变`1.1.0`、`1.2.0`保留既有合同，当前树新增`1.3.0`/v2前向候选，为PPT装配/导出发布确定性输出、linked-file质量源和workflow gate声明。显式PostgreSQL发布可原子成为后续新项目默认，但尚未宣称生产环境已执行该发布；旧Release和既有项目绑定不会被改写。“1～5的认识”黄金Fixture已用于PPT运行时合同、事务和失败路径测试，但不代表真实文本/图片Provider或最终视觉生产完成。
- 已审核的Markdown TemplateDraft可以通过显式CompilationProfile确定性编译为同一套结构化内容包合同；该能力不替代内容发布服务或模型节点执行运行时。
- 当前可以通过自动化测试和API/CLI验证后端链路，但尚未完成浏览器到真实API的阶段1纵向演示，不得描述为阶段1产品完成。
- 生产前端由[Issue #4](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/4)和唯一Draft [PR #111](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/111)承载，#179至#182正在同一分支收口。源码已经存在，但PR仍落后`main`且浏览器/治理门禁未通过；在其合并并由#11完成真实API联调前，不得把Mock闭环、交付ZIP或本地分支描述为生产前端完成。

## 已完成

- [Issue #2](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/2)的后端平台子任务#6至#10已经合并：目录与本地基础设施、数据模型与Alembic、Worker与可靠性、合同与CI、模型网关与真实文本冒烟。
- [Issue #19](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/19)的#20至#29已经完成：阶段路线、身份授权、课时分支、文件资产、内容与工作流运行时、产物版本审核、Prompt与Context审计、教材解析、项目资产绑定和阶段1后端纵向E2E。
- [Issue #29](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/29)与[PR #66](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/66)已经合并并从`origin/main`复验：真实PostgreSQL、Redis、MinIO、Alembic、Worker纵向E2E、完整后端门禁和受控`newapi/deepseek`真实文本冒烟均已通过。
- [Issue #49](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/49)与[PR #52](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/52)已经合并：模型生成、确定性执行和人工门禁使用统一节点绑定合同，完整节点目录进入主线。
- [Decision #55](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/55)已经批准：以后统一采用一个标准工作流内核、`automatic/guided`两种用户执行方式、项目/独立创作判别合同和四个独立创作动作。
- [Issue #56](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/56)与[PR #59](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/59)已经合并：产品、工作流、前后端数据语义和合同说明只保留#55批准的新口径。
- [Issue #57](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/57)与[PR #60](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/60)已经合并：OpenAPI、JSON Schema、生成客户端、Mock和兼容测试已经统一到新口径。
- [Issue #58](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/58)与[PR #63](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/63)已经合并：`automatic/guided`策略快照、项目/独立创作来源、不可变创作包、四个独立动作、Outbox/SSE、原子写回和真实依赖stale传播已经进入主线。
- [Issue #68](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/68)与[PR #71](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/71)已经合并首套内置内容包和黄金Fixture；[Decision #99](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/99)、[Issue #100](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/100)与[PR #101](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/101)随后把三类九套纠正为知识点驱动的单节点生成，#48字段阻塞保持解除。
- [Issue #88](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/88)与[PR #105](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/105)已经把`shanhai.primary_math.courseware@1.0.0`、111个内容项、22个内容定义投影和47节点v1目录正式发布到数据库；新项目从追加式默认版本固定Release与工作流，旧项目保持原绑定。
- [Issue #61](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/61)与[PR #62](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/62)已经完成Provider中立文本、图片和视频合同、Port、路由、确定性Fake、统一错误、异步任务标识和用量审计；真实媒体Adapter与冒烟仍由后续独立任务负责。
- [Issue #112](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/112)与[PR #120](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/120)已经为#89合并最小应用接口和跨模块ORM、文件/函数增长门禁，没有扩大为#92全量重构。
- [Issue #51](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/51)与[PR #119](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/119)已经收窄教师公共Prompt投影；教师端只获得可编辑业务提示词与编辑元数据，完整Prompt、Context、Schema与Provider约束继续只保留在服务端快照中。
- [Issue #123](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/123)已经退役Prompt领域从未实现的`append`教师修订模式；受控发布模板inventory为22条`replace_editable_layer`、0条Prompt `append`。
- [Issue #130](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/130)与[PR #141](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/141)已经合并47节点v2拓扑、22个模型节点的Artifact/CreationPackage输出投影、validator descriptor、质量报告和人工门禁声明；合并后的安全缺口由#146独立收口。
- [Issue #146](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/146)与[PR #148](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/148)已经关闭并合并，P0安全与发布固定性缺口已经收口。
- [Issue #89](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/89)、[Decision #153](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/153)与[PR #147](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/147)已经关闭并合并：通用节点执行器、两阶段事务、确定性Fake、完整血缘、幂等/取消/恢复/回滚/并发、私有恢复事实保留期和CreationPackage固定条件已经进入主线。
- [Issue #133](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/133)与[PR #164](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/164)已经关闭并合并：Artifact与FileAsset质量源可形成不可变ArtifactQualityReport，并与validate NodeRun终态和事件原子提交。
- [Issue #134](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/134)与[PR #174](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/174)已经在当前树实现：所有Artifact批准入口从项目固定发布合同解析exact质量要求，只接受当前submitted版本的passing报告，用户与系统身份不能伪造或绕过服务端证据。
- [Issue #125](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/125)与[PR #177](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/177)已经在当前树实现：正式教材证据驱动课时划分generate/validate/approve三节点，批准时按稳定课时键原子同步LessonUnit、发布拓扑分支与入口NodeRun，并只传播changed/archived下游stale。
- [Issue #126](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/126)与[PR #178](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/178)已经在当前树实现：每个LessonUnit从exact批准划分、教材解析和范围运行十二部分教案generate/validate/approve，字段级返修形成新不可变版本并重新生成QualityReport与gate；旧报告不可复用，gate终态与批准原子，双课时互不改写。
- [Issue #116](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/116)与[PR #183](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/183)已经在当前树实现：`default_nine`/`refine_existing`固定0/1 exact来源，Intro拓扑拆为generate/validate/approve/select四段，`auto_select`不再从其他自动动作推断，选择只绑定exact已批准方案集版本；正式`1.0.0`和既有项目不漂移。
- [Issue #127](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/127)与[PR #184](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/184)已经在当前树实现：default_nine九套与refine_existing一套复用通用NodeExecution、ArtifactQualityReport和Approval；exact optional来源、跨租户拒绝、返修重校验、重复投递和事务回滚均有PostgreSQL证据。
- [Issue #128](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/128)与[PR #187](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/187)已经在当前树实现：teacher_selected与policy_default形成不可变IntroSelection快照；每课时唯一active、并发重选、幂等历史、命令前重鉴权、exact批准失效、策略显式auto_select和唯一最高分均由PostgreSQL事务与数据库约束固定。
- [Issue #129](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/129)与[PR #192](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/192)已经在当前树实现：Intro方案查询和教师选择已成为唯一runtime API；公开投影、客户端类型、逐命令鉴权、跨租户、幂等、并发和待审/撤销/stale拒绝均由合同与PostgreSQL测试固定。
- [Issue #170](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/170)与[PR #190](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/190)已经在当前树实现：`ppt.pages.assemble`和`pptx.export`复用NodeRun、Attempt/Usage、owner租约、对象存储、Artifact/FileAsset、QualityReport与唯一Approval guard，能从正式页规格和每页exact背景生成可编辑PPTX并在取消、恢复、并发和事务故障下保持原子；该结果仍是deterministic运行时，不是完整真实PPT出口。
- [Issue #118](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/118)与[PR #196](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/196)已经关闭并合并：`material.scope_review.output`与human-gate Artifact绑定进入前向`1.4.0`候选；系统补齐锁定教材事实后，教师可继续编辑公开字段、提交和批准，且锁定字段仍由既有AuthoringPolicy拒绝篡改。
- [Issue #90](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/90)已经完成GenerationAttempt租约、心跳、过期恢复、并发安全序号、未知提交与取消协调；失去租约的Worker不能覆盖终态，历史未知提交不会自动重提或重复写入用量。
- [Issue #85](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/85)与[PR #98](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/98)已经把37个运行时操作与5个规划操作分层，生成客户端只保留真实可调用接口，CI会拒绝静态合同与FastAPI运行时双向漂移。
- [Issue #44](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/44)的实现已经提供TemplateDraft到结构化内容包的确定性编译入口、CompilationProfile、CLI和合同测试。
- [Issue #74](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/74)的#75至#79已经完成上一阶段复审、后端/数据/合同总审、协作防复发、项目记忆入口和仓库治理；遗留边界均由独立Issue承接，不在主线保留第二口径或任务日志。
- [Decision #97](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/97)与[PR #102](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/102)已经完成Linux开发环境、rootless Docker隔离、版本化workspace镜像、完整实机验证和任务闭环；阿里云Linux现为主要开发入口，Windows只保留应急回退。
- 当前后端基座使用真实PostgreSQL约束和迁移验证，普通CI继续使用确定性Fake，不访问真实Provider。
- 产品、前端、后端、数据和工作流仍以现行文档与`contracts/`为唯一当前口径，旧版并行设计不在当前树中保留。

## 当前工作

- [Decision #199](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/199)：当前唯一产品优先级是教师可见MVP纵向闭环；已合并可靠性能力继续复用，不再提前扩张与首条用户链无关的生产级合同和故障矩阵。
- [Issue #4](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/4)与Draft [PR #111](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/111)：生产前端源码与#179至#182整改的唯一载体；下一步只解决最新`main`同步、现有浏览器/治理门禁和首条MVP链所需页面，不继续扩张无关页面。
- [Decision #73](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/73)已经批准：PPT通常推荐10至20页，视频按故事和服务端价格事实推荐60至180秒，教师可以覆盖；TTS延后独立实施。
- [Issue #48](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/48)：全流程生成节点与可配置模型I/O绑定的父任务当前为`status:in-progress`；黄金内容包`1.0.0`已正式发布，#89通用执行器已经合并。
- [Issue #86](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/86)：已由PR #138合并关闭，统一ArtifactRelation类型、方向与stale影响语义。
- [Issue #131](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/131)：已由PR #161完成ContentDefinition字段级编辑权限、不可变策略来源、可信生成首写和窄化服务端provision守卫。
- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)：PR #111合并后的首个联调任务；只完成教材与物理页码选择、真实`newapi/deepseek`、课时划分、十二部分教案、三类九套、编辑/局部重生成、批准/唯一选择和刷新恢复，不得由Mock替代。
- [Issue #171](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/171)：保持为独立PPT轨道任务，不是首个教师页面的前置或完成门槛。

## 当前阻塞

- 阶段1整体产品出口仍缺少生产前端的真实API联调；后端轨道通过不代表完整阶段1产品完成。
- PR #111仍是唯一生产前端源码现场；在同步最新`main`、通过最终Head门禁并合并前，#11不能建立竞争`apps/web`分支。
- #48的机器合同和黄金数据已由#89接入通用执行器，#131字段级编辑权限、#133不可变质量报告、#134批准守卫、#125课时划分、#126教案运行时、#116 Intro合同、#127方案集运行时、#128不可变选择、#129 runtime API和#170 PPT确定性运行时已完成；不得把确定性Fake或可执行PPTX装配器冒充真实Provider与完整视觉出口。
- ShanHaiEdu已经具备Provider中立媒体基础层和Attempt租约恢复，但真实图片/视频Adapter、供应商私有状态映射与受控真实冒烟仍未实现，不能把确定性Fake或恢复基座描述为真实媒体出口。
- PPT真实文本/图片、10页黄金成片、PPTX实机打开、视频、TTS与实时价格计算均保持独立后续任务，不阻塞首个MVP。
- #175、#176和#189不再是#170之后的自动下一任务；它们的最终声明、逐镜头血缘和90秒全节点验收延后到首个MVP纵向闭环之后重新评估和拆分。

## 下一个阶段出口

唯一下一阶段出口是教师可见MVP纵向闭环，不再用更多后台合同、CLI门禁或媒体结果替代浏览器结果。资源固定为70%页面与教师体验、20%正式API联调、10%必要安全与回归。按以下顺序推进：

1. #4/PR #111同步最新`main`，关闭最终浏览器与治理门禁，只保留首条MVP链需要的生产页面并合并源码。
2. #11在该页面完成“选择已上传教材和物理页码 -> 真实`newapi/deepseek` -> 课时划分 -> 每课时十二部分教案 -> 三类九套 -> 编辑/局部重生成 -> 批准 -> 唯一选择 -> 刷新恢复”的正式API联调。
3. 使用一个受控真实小学数学项目完成浏览器复验；成功证据必须同时来自正式页面、正式API、PostgreSQL、真实Provider和真实保存，Fake、fixture与MSW只用于普通测试。
4. 由未参与实现的教学验收子智能体审查教师可用性与教学质量，并根据意见只优化一轮后复验完整链路。
5. 首个MVP关闭后再分别评估PPT/PPTX、图片、视频、TTS、失败重试与SSE hardening，不把这些任务倒灌为当前门槛。

以下事项不阻塞上述出口：新的Content Release扩张、完整音频权利声明、逐镜头lineage/stale、90秒视频全节点、真实TTS、生产扩容和全量可观测性。视频在首个MVP通过后另建最小短片纵向Issue，先验证生成、播放、采用和回写项目，再决定是否恢复#175/#176/#189原范围。

口径校准门禁必须按顺序满足：

- #56与PR #59已经合并，现行产品、工作流、后端和合同说明只保留#55批准的新口径。
- #57与PR #60已经完成OpenAPI、JSON Schema、生成客户端和Mock校准，通过兼容性与消费者合同测试并合并。
- #58与PR #63已经完成现有后端审查和最小运行时变更，通过迁移、后端、合同与仓库门禁并合并。
- #68与PR #71已经完成首套业务机器合同、黄金Fixture和分支入口校准并合并，#48字段阻塞已经解除。

阶段1后端轨道出口已经满足：

- #29已经明确只使用现有阶段1通用合同，不消费或猜测#48尚未确认的结构化业务字段。
- 真实PostgreSQL、Redis和MinIO上的项目、上传、教材解析、资产/课时/工作流、SSE续传与REST对账纵向E2E已经通过。
- Alembic空库升级、合同兼容、仓库治理、Worker恢复、Redis停启、失败重试、取消、幂等和跨租户检查已经通过。
- 普通CI继续使用确定性Fake；阶段出口已经在受控环境完成本次真实文本模型冒烟并记录脱敏证据。

阶段0整体出口仍必须满足：

- 生产前端工程达到Issue #4的阶段0范围并通过前端门禁，源码通过PR进入`main`。
- 前端通过#11消费当前OpenAPI、JSON Schema和SSE合同，完成真实API联调；Mock不能作为出口。

教材到Intro所需的#51、#88、#90、#112、#86、#123、#130、#146、#89、#131、#133、#134、#125、#126、#116、#127、#128和#129，以及PPT确定性运行时#170已经进入`main`。这些能力现在服务于MVP联调，不再自动解锁更多底座任务。任一时刻后端主任务不超过三个，修改同一合同或跨模块事务的任务不得并发；所有新任务使用仓库外隔离短worktree，同一Issue只保留一个任务分支和一个活动现场。

## 接手提示

新对话先阅读：

1. `README.md`
2. `AGENTS.md`
3. 本文件
4. 被分配的Issue和PR
5. 与任务直接相关的模块文档、合同、代码和测试

新对话先读取Decision #199与#201并从最新`main`核对#4/PR #111和#11的实时状态；唯一实现入口是PR #111的生产前端源码及其合并后的#11正式API联调，不自动启动#171、#108、#175、#176或#189。正式`1.0.0`、不可变`1.1.0`/`1.2.0`及既有项目绑定必须保持不变；新的`1.3.0`/`1.4.0`只由显式发布命令前向激活，不能把测试数据库发布冒充生产已执行。当前API客户端只从runtime合同生成，planned合同不可用于联调。不得从外部旧Skill恢复七部分教案、固定50秒视频、视频读取教案/PPT、第二套DTO或把TemplateDraft编译器当成模型执行运行时。
