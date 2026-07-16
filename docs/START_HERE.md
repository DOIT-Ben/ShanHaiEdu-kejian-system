# 统一材料入口

## 0. 原始业务需求基线

在阅读经过整理的产品和技术方案前，先阅读：

- 当前基线：`docs/requirements/2026-07-16-original-business-requirements-v2.md`
- 历史基线：`docs/requirements/2026-07-16-original-business-requirements-v1.md`

V2保存教材、课时、教案、PPT、视频、自动化、半自动化及通用图片/视频创作台的当前原始业务意图，并明确项目通过创作任务包导入创作台、创作结果保存回项目资产包。后续规格不得静默覆盖这份基线。

## 1. 先确认哪些决定已经锁定

- 产品：先闭环小学数学，保留学科、年级、教材版本和工作流模板扩展能力。
- 形态：教师创作工作台，不是传统表格化管理后台。
- 模式：手动、半自动、全自动三种推进模式；所有模式都允许教师暂停、修改输入、查看提示词、返修和确认。
- 资产：每个节点的输入、提示词、输出、版本、审核状态、模型参数和费用都进入项目资产与运行记录。
- 前端：完全重做，采用独立 React SPA，不复用旧前端视觉代码。
- 后端：迁移并改造既有 FastAPI 基座，先做模块化单体和异步 worker，不直接拆微服务。
- 模型：文本、图片、视频、语音和 PPT 统一称为模型能力，全部由后端模型网关路由。
- 安全：Provider 密钥只存在服务端密钥系统，绝不进入浏览器、仓库、日志或导出文件。

## 2. 不同角色的阅读顺序

### 产品、项目负责人

1. `docs/frontend-outsourcing/v1.0/00_范围边界与固定决策.md`
2. `docs/frontend-outsourcing/v1.0/01_产品信息架构与用户流程.md`
3. `docs/frontend-outsourcing/v1.0/11_外包交付物与验收标准.md`
4. `docs/frontend-outsourcing/v1.0/12_里程碑付款与变更管理.md`

### 前端承接方

1. `docs/vendor/FRONTEND_KICKOFF_INSTRUCTION.md`
2. `docs/frontend-outsourcing/v1.0/README.md`
3. `docs/frontend-outsourcing/v1.0/02_页面与路由规格.md`
4. `docs/frontend-outsourcing/v1.0/03_教师工作台与节点画布规格.md`
5. `docs/frontend-outsourcing/v1.0/04_视觉系统与组件规范.md`
6. `docs/frontend-outsourcing/v1.0/06_前端技术架构与代码规范.md`
7. `docs/frontend-outsourcing/v1.0/contracts/`

### 后端承接方

1. `docs/architecture/BACKEND_ARCHITECTURE.md`
2. `docs/architecture/BASELINE_MIGRATION_PLAN.md`
3. `docs/frontend-outsourcing/v1.0/07_API_SSE与文件接入规范.md`
4. `docs/frontend-outsourcing/v1.0/08_模型网关前端规格.md`
5. `docs/frontend-outsourcing/v1.0/contracts/frontend-api-requirements.openapi.yaml`

### 测试与验收人员

1. `docs/frontend-outsourcing/v1.0/10_测试性能安全与可访问性.md`
2. `docs/frontend-outsourcing/v1.0/checklists/`
3. `docs/frontend-outsourcing/v1.0/11_外包交付物与验收标准.md`

## 3. 事实来源优先级

发生冲突时按以下顺序处理：

1. 已合并到 `main` 的正式 OpenAPI、数据库迁移和工作流 Schema。
2. 本仓库的 ADR、架构文档与产品规格。
3. Figma 已标记为 Ready for Dev 的页面与组件。
4. 会议记录、聊天内容和口头说明。

前端包中的 OpenAPI 是需求草案。正式联调开始后，后端生成并提交的 OpenAPI 是唯一接口事实来源；任何破坏性修改必须同时给出迁移说明。

## 4. 当前提交不代表什么

- 不代表生产前端已经开发完成。
- 不代表旧后端已经迁入新仓库。
- 不代表模型 Provider 已完成真实联调。
- 不代表 PDF、PPTX、图片或视频占位产物可以作为正式交付。

这些项目必须在后续里程碑中以源码、测试、可运行环境和真实产物逐项验收。
