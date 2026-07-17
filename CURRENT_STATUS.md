# 当前项目状态

更新时间：2026-07-17

验证基线：`main`，提交以本文件所在版本为准

当前阶段：阶段0出口尚未关闭；阶段1后端轨道按Decision #18受控并行

本文件只描述现在，不保存开发日志。任务细节、负责人、讨论和交接以GitHub Issue与Pull Request为准。

## 当前可演示成果

- 已形成小学数学课件平台的统一产品、前端、后端、数据和工作流设计。
- 已定义教材、课时、教案、三类九套导入、PPT、视频、创作中心和项目资产的端到端关系。
- 已提供自动校验的OpenAPI、核心JSON Schema、Mock场景和生成客户端合同。
- 已建立可运行的FastAPI、PostgreSQL、Redis、对象存储和Worker工程基座。
- 已通过API和测试建立项目、上传会话、上传确认和任务持久化路径。
- 已通过确定性Fake贯通事务Outbox、Worker租约、任务状态、SSE续传和命令幂等。
- 已建立供应商解耦的文本模型网关、确定性Fake、配置驱动适配器和显式真实冒烟入口。
- 已建立内置内容Release、不可变定义、项目固定版本和工作流运行/节点快照骨架。
- 已建立项目内容产物草稿、不可变版本、审核动作和真实依赖过期传播。
- 已建立教材PDF隔离解析Worker、不可变证据包和可恢复任务链路。
- 已冻结Schema驱动生成模板内容包V1及其类型化合同、引用和校验工具。
- 已提供当前前端外包交付包。

当前尚无可运行的端到端业务应用，不得把设计文档或静态原型描述为MVP完成。

## 已完成

- 产品与工作流现行口径统一。
- 前端设计和外包验收口径统一。
- 后端架构、领域、工作流、模型网关和数据库设计统一。
- 旧版并行设计目录从当前树清除。
- GitHub Issue/PR任务事实源、交接、分支、文档生命周期和里程碑规则已初始化。
- Issue/PR模板、CODEOWNERS和仓库治理检查已加入当前基线。
- Issue #6、#7、#8、#9、#10、#21、#22、#23、#24、#25、#27和#38已合并，阶段0后端基础设施、数据、合同、异步可靠性、文本模型网关、身份授权、课时/分支、文件资产/解析版本、内容/工作流运行时、产物版本/审核、教材PDF证据包以及Schema驱动生成模板合同进入`main`。

## 当前责任分工

- Codex负责除生产前端之外的平台开发：API、数据库、Worker、工作流、模型网关、对象存储、基础设施、合同和CI。
- 独立前端承接方只负责`apps/web`、Figma、Storybook、MSW、前端测试与真实API联调。
- 双方通过OpenAPI、JSON Schema、SSE、错误合同和Mock场景协作，不越过目录和职责边界。

## 当前活跃任务

- [Issue #4：重新外包生产级前端实现](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/4)
- [Issue #19：完成阶段1最小可运行后端基座](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/19)
- [Issue #42：实现Markdown TemplateDraft解析与规范化V1](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/42)

## 下一实施任务

- [Issue #26：实现上下文白名单、提示词快照和模型调用审计](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/26)
- [Issue #28：实现项目资产槽位与原子绑定](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/28)

Issue #38已冻结Decision #37批准的Schema驱动生成模板内容包V1，Issue #26可直接消费现行Prompt、Context、输出和投影引用合同；Issue #42的内容包编译集成在其核心适配器完成后继续。

## 等待中的联调任务

- [Issue #11：与Issue #4完成合同联调](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)

## 受控并行边界

[Decision #18](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/18)只调整实施时序，不改变阶段定义或出口：

- Issue #2和Issue #11继续保持阶段0未完成事实；没有前端Draft PR时不启动#11，也不用后端临时页面替代联调。
- 不依赖前端的阶段1后端任务按父Issue #19及其子Issue推进；先完成#21，再按依赖开放后续波次。
- 同时处于实施、评审或仍有未合并Draft PR的后端主任务不超过三个。
- 普通CI和业务测试使用确定性Fake；Provider适配变更和阶段出口使用受控真实冒烟。
- Codex不修改或代写`apps/web`；阶段1后端通过不等于阶段1教师端或产品里程碑完成。

## 当前限制

- 新前端承接方尚未从Issue #4建立Draft PR和工程预览。
- 图片、视频和TTS供应商的真实开发凭据尚未进入受控环境。

这些限制不阻塞普通CI、确定性Fake和阶段1后端基础任务，但会阻止前端真实联调以及图片、视频和TTS阶段出口验收。

## 下一个阶段出口

阶段0完成必须同时满足：

- 团队治理文档、Issue/PR模板和仓库清洁校验合并到`main`。
- 后端平台目录、基础CI和本地依赖能够启动。
- 前端承接方建立`apps/web`工程、Storybook、MSW和可访问预览。
- OpenAPI与JSON Schema进入自动校验。
- 后端可以通过测试或命令行完成项目、上传、异步任务和SSE的最小贯通。
- 前端可以基于合同完成对应Mock路径，并开始真实API联调。

阶段1后端轨道已完成身份授权、课时/分支、文件资产/解析版本、内容/工作流运行时、产物版本/审核、教材PDF解析和Schema驱动生成模板合同；当前#42推进Markdown模板适配器，#26恢复Prompt/Context/用量审计，#28继续作为已解锁的项目资产槽位任务。完整依赖、测试和回退要求以父Issue #19为准。

## 接手提示

新对话先阅读：

1. `README.md`
2. `AGENTS.md`
3. 本文件
4. 被分配的Issue和PR
5. 与任务直接相关的模块文档、合同、代码和测试

不要先通读Git历史或全部设计文档。
