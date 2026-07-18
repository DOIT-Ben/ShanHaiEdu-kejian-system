# 当前项目状态

更新时间：2026-07-18

验证基线：`main`，实现事实以本文件所在提交的代码、迁移和测试为准；任务状态以链接的GitHub Issue和Pull Request为准

当前阶段：阶段0出口尚未关闭；阶段1后端轨道正在完成产品、合同和实现口径校准

本文件只描述现在，不保存开发日志。任务细节、负责人、讨论和交接以GitHub Issue与Pull Request为准。

## 当前可演示成果

- 后端已经具备可运行的FastAPI模块化单体、PostgreSQL、Redis、MinIO、Alembic、Worker、Outbox、SSE和幂等基座。
- API和测试已经覆盖租户与用户边界、项目、课时与分支、上传、文件资产与不可变版本、内容发布、工作流运行、产物审核与依赖、Prompt与Context快照、教材PDF解析以及项目资产原子绑定。
- OpenAPI、JSON Schema、生成TypeScript客户端、确定性Mock/Fake和后端CI已经进入自动门禁；文本模型网关已经完成受控真实冒烟。
- 当前可以通过自动化测试和API/CLI验证后端链路，但尚未完成浏览器到真实API的阶段1纵向演示，不得描述为阶段1产品完成。
- 生产前端仍在[Issue #4](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/4)与[Draft PR #33](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/33)中独立推进，尚未合并到`main`。

## 已完成

- [Issue #2](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/2)的后端平台子任务#6至#10已经合并：目录与本地基础设施、数据模型与Alembic、Worker与可靠性、合同与CI、模型网关与真实文本冒烟。
- [Issue #19](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/19)的#20至#28已经实际完成：阶段路线、身份授权、课时分支、文件资产、内容与工作流运行时、产物版本审核、Prompt与Context审计、教材解析和项目资产绑定。
- [Issue #49](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/49)与[PR #52](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/52)已经合并：模型生成、确定性执行和人工门禁使用统一节点绑定合同，完整节点目录进入主线。
- [Decision #55](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/55)已经批准：以后统一采用一个标准工作流内核、`automatic/guided`两种用户执行方式、项目/独立创作判别合同和四个独立创作动作。
- [Issue #56](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/56)与[PR #59](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/59)已经合并：产品、工作流、前后端数据语义和合同说明只保留#55批准的新口径。
- 当前后端基座使用真实PostgreSQL约束和迁移验证，普通CI继续使用确定性Fake，不访问真实Provider。
- 产品、前端、后端、数据和工作流仍以现行文档与`contracts/`为唯一当前口径，旧版并行设计不在当前树中保留。

## 当前工作

- [Issue #44](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/44)与[PR #46](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/46)：Markdown TemplateDraft确定性编译的五项CI已通过，但当前与`main`存在合并冲突，需重新rebase后继续评审。
- [Issue #57](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/57)与[Draft PR #60](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/60)：OpenAPI、JSON Schema、生成客户端、Mock和兼容测试已经按新口径实现，等待CI、评审和合并；这不代表数据库或后端运行时已经实现新合同。
- [Issue #58](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/58)：审查并修正必要的后端模型、服务、迁移和回归测试，等待#57与PR #60合并后启动。
- [Issue #48](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/48)：全流程生成节点与可配置模型I/O绑定的父任务；已标记`status:blocked`，结构化业务字段确认前不继续扩展实现。
- [Issue #29](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/29)：阶段1后端纵向贯通与真实文本出口；已标记`status:blocked`，恢复前必须先确认只使用现有通用合同，或等待其所需结构化字段定稿。
- [Issue #51](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/51)：教师端只展示可编辑业务提示词并隐藏内部结构合同，尚未启动。
- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)：与生产前端完成真实合同联调，等待前端达到联调条件。

## 当前阻塞

- 教案、PPT、视频等具体业务结构化字段仍由产品负责人设计。#48后续任务不得提前固化这些字段；#56至#58只统一通用工作流、创作生命周期和保存边界，不猜测具体字段。
- #44仍在评审；它负责通用Markdown模板编译，不代表具体业务字段已经批准。
- PR #60已经定义新OpenAPI与机器合同，但当前数据库和后端运行时仍使用旧执行枚举与创作端点；#58负责兼容迁移。在#58合并前不得把本轮目标描述为已实现运行时行为。
- 阶段1完整出口仍缺少后端纵向E2E与阶段真实文本冒烟，以及生产前端的真实API联调。
- 图片、视频和TTS真实Provider适配与凭据属于后续媒体阶段前置条件，不用Mock替代阶段验收。

## 下一个阶段出口

当前先关闭一个口径校准门禁，再恢复两个受控出口。

口径校准门禁必须按顺序满足：

- #56与PR #59已经合并，现行产品、工作流、后端和合同说明只保留#55批准的新口径。
- #57与PR #60完成OpenAPI、JSON Schema、生成客户端和Mock校准，通过兼容性与消费者合同测试并合并。
- #58审查现有后端实现，只增加维持新合同所需的最小模型、迁移、服务和测试变更。

阶段1后端轨道出口必须满足：

- 先明确#29只使用现有阶段1通用合同，或等待并确认它实际需要的结构化字段；不得用猜测字段完成出口。
- 启动#29，使用真实PostgreSQL、Redis和MinIO完成项目、上传、教材解析、资产/课时/工作流、SSE续传与REST对账的纵向E2E。
- 普通CI使用确定性Fake，阶段出口另外完成受控真实文本模型冒烟并记录脱敏证据。
- Alembic空库升级、合同兼容、仓库治理、失败重试、取消和幂等检查全部通过。

阶段0整体出口仍必须满足：

- 生产前端工程达到Issue #4的阶段0范围并通过前端门禁，源码通过PR进入`main`。
- 前端通过#11消费当前OpenAPI、JSON Schema和SSE合同，完成真实API联调；Mock不能作为出口。

口径校准门禁和两个出口均关闭后，才进入阶段2“教材到教案纵向链路”，交付第一个真实教师价值闭环。#44、#51和#48属于后续合同准备工作，不得在未经过对应Issue决策时自动扩大#29或阶段出口范围。

## 接手提示

新对话先阅读：

1. `README.md`
2. `AGENTS.md`
3. 本文件
4. 被分配的Issue和PR
5. 与任务直接相关的模块文档、合同、代码和测试

结构化字段未确认前，不扩展#48后续实现，也不把#44的工程检查通过解释为具体业务字段已经批准。当前先按#56 → #57 → #58完成通用口径校准；恢复#29前再确认其E2E严格限定为已合并合同。
