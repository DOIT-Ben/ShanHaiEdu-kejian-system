# 当前项目状态

更新时间：2026-07-18

验证基线：`main`，实现事实以本文件所在提交的代码、迁移和测试为准；任务状态以链接的GitHub Issue和Pull Request为准

当前阶段：阶段0出口尚未关闭；阶段1通用口径校准门禁、后端轨道和首套业务机器合同已经关闭，#48已解锁并等待通用模型节点执行运行时

本文件只描述现在，不保存开发日志。任务细节、负责人、讨论和交接以GitHub Issue与Pull Request为准。

## 当前可演示成果

- 后端已经具备可运行的FastAPI模块化单体、PostgreSQL、Redis、MinIO、Alembic、Worker、Outbox、SSE和幂等基座。
- API和测试已经覆盖租户与用户边界、项目、课时与分支、上传、文件资产与不可变版本、内容发布、工作流运行、产物审核与依赖、Prompt与Context快照、教材PDF解析以及项目资产原子绑定。
- OpenAPI、JSON Schema、生成TypeScript客户端、确定性Mock/Fake和后端CI已经进入自动门禁；文本模型网关已经完成受控真实冒烟。
- 首套小学数学业务内容包已经为23个模型节点固定输入、Prompt、输出、投影和逻辑能力；“1～5的认识”黄金Fixture可以分别启动教案、PPT和视频合同测试，但不代表真实模型或媒体生产完成。
- 已审核的Markdown TemplateDraft可以通过显式CompilationProfile确定性编译为同一套结构化内容包合同；该能力不替代内容发布服务或模型节点执行运行时。
- 当前可以通过自动化测试和API/CLI验证后端链路，但尚未完成浏览器到真实API的阶段1纵向演示，不得描述为阶段1产品完成。
- 生产前端仍在[Issue #4](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/4)与[Draft PR #33](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/33)中独立推进，尚未合并到`main`。

## 已完成

- [Issue #2](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/2)的后端平台子任务#6至#10已经合并：目录与本地基础设施、数据模型与Alembic、Worker与可靠性、合同与CI、模型网关与真实文本冒烟。
- [Issue #19](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/19)的#20至#29已经完成：阶段路线、身份授权、课时分支、文件资产、内容与工作流运行时、产物版本审核、Prompt与Context审计、教材解析、项目资产绑定和阶段1后端纵向E2E。
- [Issue #29](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/29)与[PR #66](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/66)已经合并并从`origin/main`复验：真实PostgreSQL、Redis、MinIO、Alembic、Worker纵向E2E、完整后端门禁和受控`newapi/deepseek`真实文本冒烟均已通过。
- [Issue #49](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/49)与[PR #52](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/52)已经合并：模型生成、确定性执行和人工门禁使用统一节点绑定合同，完整节点目录进入主线。
- [Decision #55](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/55)已经批准：以后统一采用一个标准工作流内核、`automatic/guided`两种用户执行方式、项目/独立创作判别合同和四个独立创作动作。
- [Issue #56](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/56)与[PR #59](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/59)已经合并：产品、工作流、前后端数据语义和合同说明只保留#55批准的新口径。
- [Issue #57](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/57)与[PR #60](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/60)已经合并：OpenAPI、JSON Schema、生成客户端、Mock和兼容测试已经统一到新口径。
- [Issue #58](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/58)与[PR #63](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/63)已经合并：`automatic/guided`策略快照、项目/独立创作来源、不可变创作包、四个独立动作、Outbox/SSE、原子写回和真实依赖stale传播已经进入主线。
- [Issue #68](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/68)与[PR #71](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/71)已经合并：首套内置内容包、黄金Fixture、三条独立分支入口和内部链校验已经进入主线，#48字段阻塞已经解除。
- [Issue #44](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/44)的实现已经提供TemplateDraft到结构化内容包的确定性编译入口、CompilationProfile、CLI和合同测试。
- 当前后端基座使用真实PostgreSQL约束和迁移验证，普通CI继续使用确定性Fake，不访问真实Provider。
- 产品、前端、后端、数据和工作流仍以现行文档与`contracts/`为唯一当前口径，旧版并行设计不在当前树中保留。

## 当前工作

- [Decision #73](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/73)已经批准：PPT通常推荐10至20页，视频按故事和服务端价格事实推荐60至180秒，教师可以覆盖；TTS延后独立实施。
- [Issue #48](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/48)：全流程生成节点与可配置模型I/O绑定的父任务已经恢复`status:ready`；下一子任务需实现已发布GenerationTemplate的通用执行运行时。
- [Issue #61](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/61)与[Draft PR #62](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/62)：原阻塞依赖#58已经满足；恢复实现前需从最新`main`重新rebase并复核统一模型网关上线后的Provider边界。
- [Issue #51](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/51)：教师端只展示可编辑业务提示词并隐藏内部结构合同，尚未启动。
- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)：与生产前端完成真实合同联调，等待前端达到联调条件。

## 当前阻塞

- #61的历史阻塞事实已经变化，但必须通过其独立Issue/PR完成rebase、范围复核和状态变更，不在#68中静默恢复实现。
- 阶段1整体产品出口仍缺少生产前端的真实API联调；后端轨道通过不代表完整阶段1产品完成。
- #48已有机器合同和黄金数据，但主线尚无读取已发布GenerationTemplate并完成Prompt/Context冻结、模型调用、结构校验和Artifact落库的通用执行器。
- 统一模型网关已经提供文本、图片和视频上游能力；ShanHaiEdu的Provider中立媒体基础层、Adapter、异步恢复和真实冒烟仍属于#61及后续适配任务。
- TTS与实时价格计算当前不实现、不冒烟，也不阻塞教材到教案纵向链；PPTX装配、媒体生成和最终交付仍需独立Issue与真实阶段验收。

## 下一个阶段出口

通用口径校准门禁和阶段1后端轨道已经关闭，接下来依次关闭业务内容合同与阶段0前端联调出口。

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

进入阶段2“教材到教案纵向链路”时，先完成#51教师Prompt公共投影和#61 Provider中立基础层，再实现#48通用模型节点执行运行时；随后基于#68黄金输入分别交付课时/教案与三类九套/选择快照。PPT/图片和视频在阶段2运行时稳定后使用独立短分支并行推进；TTS继续延后，#11等待生产前端达到联调条件。

## 接手提示

新对话先阅读：

1. `README.md`
2. `AGENTS.md`
3. 本文件
4. 被分配的Issue和PR
5. 与任务直接相关的模块文档、合同、代码和测试

新对话以#68合并后的内容包和黄金Fixture为机器基线；先核对#51、#61和#48运行时子Issue的实时状态，不得从外部旧Skill恢复七部分教案、固定50秒视频、视频读取教案/PPT、第二套DTO或把TemplateDraft编译器当成模型执行运行时。
