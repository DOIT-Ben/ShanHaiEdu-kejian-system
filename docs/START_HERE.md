# 山海教育课件系统最短阅读入口

当前树只保留一套有效口径。不要从Git历史、旧聊天记录或外部压缩包复制需求。

## 所有人先读

1. `README.md`：项目是什么。
2. `AGENTS.md`：必须怎样工作。
3. `docs/governance/项目记忆与接手索引.md`：稳定原则、事实入口和验证路径在哪里。
4. `CURRENT_STATUS.md`：现在做到哪里。
5. 被分配的GitHub Issue和Pull Request：本次具体做什么。

完成以上步骤后，只读取与任务直接相关的部分。不要把“接手项目”理解为通读所有文档。

## 产品与工作流任务

按任务选择：

- `docs/product/REQUIREMENTS_ANALYSIS.md`：用户问题、范围和业务规则。
- `docs/product/PRODUCT_SPEC.md`：现行产品能力和验收口径。
- `docs/workflows/END_TO_END_WORKFLOW.md`：整个项目链路。
- `docs/workflows/INTRO_ANCHORS.md`：三类九套与锚定隔离。
- `docs/workflows/PPT_PRODUCTION.md`：PPT生产。
- `docs/workflows/VIDEO_PRODUCTION.md`：视频生产。
- `docs/workflows/generation-guide/README.md`：逐节点查看教师输入、系统Context、完整提示词、输出字段和黄金示例。

只修改某一工作流时，不需要先读取全部前后端设计。

## 前端任务

1. `docs/frontend/README.md`
2. 当前功能对应的`docs/frontend/0x_*.md`
3. 当前功能对应的工作流文档
4. `contracts/README.md`及实际使用的Schema/OpenAPI路径
5. 当前Feature代码与测试

不要手写后端DTO，不要从旧外包包复制实现，不要为了一个新节点在页面堆叠类型判断。

## 后端任务

1. `docs/backend/README.md`
2. 当前模块对应的`docs/backend/0x_*.md`
3. 当前模块对应的工作流文档
4. `contracts/README.md`及实际修改的合同
5. 当前模块代码、迁移和测试

不要因为任务涉及模型就通读所有Provider或视频设计。以模块边界和应用接口缩小范围。

## 数据库与合同任务

1. `docs/backend/01_领域模型与资产版本.md`
2. `docs/backend/04_数据库设计.md`
3. `docs/backend/05_API_SSE权限与安全.md`
4. `contracts/`
5. 当前Alembic迁移、消费者和合同测试

任何破坏性变更先建立Decision Issue，并在一个PR同步迁移、消费者、测试和回退策略。

## 测试与验收任务

1. Issue验收标准和PR风险说明
2. 对应产品或工作流文档
3. `docs/frontend/08_测试验收与外包交付.md`或`docs/backend/06_测试迁移与交付.md`
4. 相关合同和测试代码
5. `docs/governance/DELIVERY_ROADMAP.md`中的当前阶段出口

MVP和里程碑验收必须使用真实黄金项目，Mock和截图只用于开发辅助。

## 团队治理任务

- `docs/governance/TEAM_WORKFLOW.md`：Issue、分支、PR、交接和关闭。
- `docs/governance/DOCUMENT_POLICY.md`：信息放置、替换和删除。
- `docs/governance/DELIVERY_ROADMAP.md`：阶段、并行策略和MVP出口。
- `docs/governance/协作机制复盘与防复发.md`：已证实的协作踩坑、现行防复发机制和残余风险。
- `docs/governance/项目记忆与接手索引.md`：项目稳定记忆、权威路由和外部记忆边界。

## 冲突处理

- 产品与工作流文档描述预期行为。
- 合同描述跨模块机器边界。
- 代码、迁移和测试描述已实现行为。

三者不一致时，它们共同构成一个阻塞缺陷。停止扩展功能，创建或更新Issue，并在同一变更中统一口径。禁止增加补充说明让团队自行选择。

历史只在调查回归、责任审计或当前资料无法解释的决定时定向读取。
外部长期记忆只用于定位本仓库和项目记忆索引；分支、提交、Pull Request、端口和运行结果必须从 live 项目复核。
