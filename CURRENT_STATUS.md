# 当前项目状态

更新时间：2026-07-20

验证基线：`main`，实现事实以本文件所在提交的代码、迁移和测试为准；任务状态以链接的GitHub Issue和Pull Request为准

当前阶段：阶段0出口尚未关闭；阶段1通用口径校准、后端轨道、首套业务机器合同和后端治理审计已经关闭，阶段2后端已经关闭Prompt公共投影、Attempt恢复与Prompt合同收窄门禁，#130处于`status:in-progress`分支实现阶段，合并前#89仍保持阻塞

本文件只描述现在，不保存开发日志。任务细节、负责人、讨论和交接以GitHub Issue与Pull Request为准。

## 当前可演示成果

- 后端已经具备可运行的FastAPI模块化单体、PostgreSQL、Redis、MinIO、Alembic、Worker、Outbox、SSE和幂等基座。
- API和测试已经覆盖租户与用户边界、项目、课时与分支、上传、文件资产与不可变版本、内容发布、工作流运行、产物审核与依赖、Prompt与Context快照、教材PDF解析以及项目资产原子绑定。
- OpenAPI、JSON Schema、生成TypeScript客户端、确定性Mock/Fake和后端CI已经进入自动门禁；文本模型网关已经完成受控真实冒烟。
- 首套小学数学业务内容包已经为22个模型节点固定输入、Prompt、输出、投影和逻辑能力；三类九套由课程驱动单节点直接生成最终方案集。“1～5的认识”黄金Fixture可以分别启动教案、PPT和视频合同测试，但不代表真实模型或媒体生产完成。
- 已审核的Markdown TemplateDraft可以通过显式CompilationProfile确定性编译为同一套结构化内容包合同；该能力不替代内容发布服务或模型节点执行运行时。
- 当前可以通过自动化测试和API/CLI验证后端链路，但尚未完成浏览器到真实API的阶段1纵向演示，不得描述为阶段1产品完成。
- 生产前端仍由[Issue #4](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/4)独立负责；先前的PR #33已经关闭且未合并，当前没有可供#11联调的开放前端PR，任何本地前端分支或交付ZIP都不能替代远端源码交接。

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
- [Issue #88](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/88)与[PR #105](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/105)已经把纠偏后的黄金内容包、111个内容项、22个内容定义投影和47节点目录正式发布到数据库；新项目从追加式默认版本固定Release与工作流，旧项目保持原绑定。
- [Issue #61](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/61)与[PR #62](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/62)已经完成Provider中立文本、图片和视频合同、Port、路由、确定性Fake、统一错误、异步任务标识和用量审计；真实媒体Adapter与冒烟仍由后续独立任务负责。
- [Issue #112](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/112)与[PR #120](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/120)已经为#89合并最小应用接口和跨模块ORM、文件/函数增长门禁，没有扩大为#92全量重构。
- [Issue #51](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/51)与[PR #119](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/119)已经收窄教师公共Prompt投影；教师端只获得可编辑业务提示词与编辑元数据，完整Prompt、Context、Schema与Provider约束继续只保留在服务端快照中。
- [Issue #90](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/90)已经完成GenerationAttempt租约、心跳、过期恢复、并发安全序号、未知提交与取消协调；失去租约的Worker不能覆盖终态，历史未知提交不会自动重提或重复写入用量。
- [Issue #85](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/85)与[PR #98](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/98)已经把37个运行时操作与5个规划操作分层，生成客户端只保留真实可调用接口，CI会拒绝静态合同与FastAPI运行时双向漂移。
- [Issue #44](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/44)的实现已经提供TemplateDraft到结构化内容包的确定性编译入口、CompilationProfile、CLI和合同测试。
- [Issue #74](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/74)的#75至#79已经完成上一阶段复审、后端/数据/合同总审、协作防复发、项目记忆入口和仓库治理；遗留边界均由独立Issue承接，不在主线保留第二口径或任务日志。
- [Decision #97](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/97)与[PR #102](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/102)已经完成Linux开发环境、rootless Docker隔离、版本化workspace镜像、完整实机验证和任务闭环；阿里云Linux现为主要开发入口，Windows只保留应急回退。
- 当前后端基座使用真实PostgreSQL约束和迁移验证，普通CI继续使用确定性Fake，不访问真实Provider。
- 产品、前端、后端、数据和工作流仍以现行文档与`contracts/`为唯一当前口径，旧版并行设计不在当前树中保留。

## 当前工作

- [Decision #73](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/73)已经批准：PPT通常推荐10至20页，视频按故事和服务端价格事实推荐60至180秒，教师可以覆盖；TTS延后独立实施。
- [Issue #48](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/48)：全流程生成节点与可配置模型I/O绑定的父任务保持`status:ready`；黄金内容包已正式发布，通用执行器由#89承接。
- [Issue #86](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/86)：已由PR #138合并关闭，统一ArtifactRelation类型、方向与stale影响语义。
- [Issue #123](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/123)：Prompt领域从未实现的`append`教师修订模式已收窄；受控发布模板inventory为22条`replace_editable_layer`、0条Prompt `append`，下一门禁转为#130。
- [Issue #130](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/130)：在#123合并后串行补齐模型输出的Artifact/CreationPackage持久化投影；当前为`status:in-progress`，分支正在实现与验证，尚不代表投影合同已合并。
- [Issue #89](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/89)：继续保持`status:blocked`；#51、#90、#112、#86与#123已经完成，只有#130也合并并在最新`main`上对六项门禁完成新鲜复验后，才作为唯一后端主实现启动。
- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)：与生产前端完成真实合同联调；当前因Issue #4没有开放源码PR而等待，不以本地分支、ZIP或Mock代替。

## 当前阻塞

- 阶段1整体产品出口仍缺少生产前端的真实API联调；后端轨道通过不代表完整阶段1产品完成。
- #48已有机器合同和黄金数据，但主线尚无读取数据库已发布GenerationTemplate并完成Prompt/Context冻结、模型调用、结构校验和Artifact原子落库的通用执行器；#51、#90、#112、#86与#123已经完成，#130尚在收口纯投影合同，#89仍等待#130合并后在最新`main`上对六项门禁完成新鲜复验。
- ShanHaiEdu已经具备Provider中立媒体基础层和Attempt租约恢复，但真实图片/视频Adapter、供应商私有状态映射与受控真实冒烟仍未实现，不能把确定性Fake或恢复基座描述为真实媒体出口。
- TTS与实时价格计算当前不实现、不冒烟，也不阻塞教材到教案纵向链；PPTX装配、媒体生成和最终交付仍需独立Issue与真实阶段验收。

## 下一个阶段出口

通用口径校准、首套业务内容合同、#100课程驱动纠偏、#88黄金内容发布、阶段1后端轨道、#51 Prompt公共投影、#90 Attempt恢复、#86关系语义和#123 Prompt合同收窄门禁已经关闭；当前收口#130输出持久化投影，再复验#89。阶段0前端联调出口继续独立等待生产前端源码交接。

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

进入阶段2“教材到教案纵向链路”时，#51、#88、#90、#112、#86和#123已经完成，当前按[交付路线](docs/governance/DELIVERY_ROADMAP.md)推进#130。任一时刻后端主任务不超过三个，修改同一合同或跨模块事务的任务不得并发。#89通用执行器仅在#51、#90、#112、#86、#123和#130全部合并并从最新`main`完成新鲜复验后单独启动。随后基于已发布黄金输入交付课时/教案与三类九套/选择快照；PPT/图片和视频在阶段2运行时稳定后使用独立短分支并行推进。TTS继续延后，#11等待生产前端达到联调条件。所有新任务默认在阿里云Linux的仓库外短worktree中开发，Windows只作应急回退。

## 接手提示

新对话先阅读：

1. `README.md`
2. `AGENTS.md`
3. 本文件
4. 被分配的Issue和PR
5. 与任务直接相关的模块文档、合同、代码和测试

新对话从最新Linux `main`推进#130输出持久化投影门禁；#51、#90、#112、#86与#123已经完成，#89仍须等待#130合并并在最新`main`上对六项门禁完成新鲜复验。#88已完成正式内容发布，不得回退到Fixture常量或覆盖既有项目Release。当前API客户端只从runtime合同生成，planned合同不可用于联调。不得从外部旧Skill恢复七部分教案、固定50秒视频、视频读取教案/PPT、第二套DTO或把TemplateDraft编译器当成模型执行运行时。
