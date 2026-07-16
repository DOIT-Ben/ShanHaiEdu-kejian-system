# 既有后端基座迁移计划

> 当前迁移边界受`docs/superpowers/specs/2026-07-17-shanhai-courseware-platform-runtime-design.md`约束。旧状态枚举、固定十二列教案、项目挂载创作台和旧API响应包不得直接迁入。

## 1. 迁移原则

源基座：`DOIT-Ben/shanhaiedu-v1.0.0` 的 `main`。

目标仓库：`DOIT-Ben/ShanHaiEdu-kejian-system` 的 `main`。

采用“能力迁移与合同收敛”，不把旧仓库整个工作树无审查复制过来。旧前端明确不迁入；历史归档、WIP、运行数据、密钥和本地生成文件也不迁入。

## 2. 可复用能力

根据既有仓库当前结构，优先迁移：

- `apps/api` 中的 FastAPI 应用、认证、项目、教材、教案、任务、产物和路由。
- 工作流服务、状态存储、项目初始化和版本能力。
- Prompt registry、Prompt store、规则控制面和审计基础。
- 文本、图片、视频、TTS 和 PPT Provider adapter。
- Provider readiness、脱敏错误封装和幂等相关实现。
- `workflow/` 中仍与当前产品主线一致的 Schema、Prompt 和验证器。
- 定向测试、真实 Provider smoke 和产物真实性校验。

## 3. 不直接迁移

- `apps/web` 旧前端。
- `history/` 和仅用于恢复证据的归档。
- SQLite 数据库文件、`storage/`、缓存、日志和用户上传文件。
- `.env`、API key、Token、Provider 原始敏感响应。
- 与当前“小学数学工作台”无关的 Agent 实验入口和重复运行时。
- 将“尚未选型”标记、占位视频或 Fake provider 输出当成正式能力的代码路径。

## 4. 分阶段迁移

### 阶段 A：建立可运行基线

- 在目标仓库创建 `apps/api`、`workflow`、`tests` 和 `scripts`。
- 迁入最小 FastAPI 启动、统一错误、健康检查和认证。
- 保留 SQLite 作为测试适配器，增加 PostgreSQL 配置入口。
- 固化 `/api/v2` 和正式 OpenAPI 生成。

退出条件：API 可启动，健康检查、登录、创建项目和权限隔离测试通过。

### 阶段 B：项目、工作流和版本

- 迁移项目、课时、分支配置、工作流定义/运行、正式状态机、版本、审批和精确过期。
- 将文件目录型状态逐步迁到 SQLAlchemy repository。
- 增加工作流 definition/run 分离，项目绑定不可变工作流版本。
- 建立Artifact、ArtifactVersion、FileAsset、ProjectAssetSlot和AssetBinding。

退出条件：固定课例可从教材到教案确认，刷新后状态不丢失。

### 阶段 C：内容运行时、Prompt 与模型网关

- 迁移 Prompt registry 和 Provider adapter。
- 建立内容包导入、验证、发布和固定版本机制。
- 建立Content Definition Schema通用结构，默认导入十二部分教案包。
- 建立ContextBinding白名单、Prompt编译器和结构化输出校验。
- 增加逻辑模型、能力、路由策略、密钥引用、健康检查和 usage record。
- 保存每次真实发送的 Prompt snapshot。
- 接入 Dramatiq/Redis，把长任务从 API 进程移出。

退出条件：文本和图片任务可异步运行、取消、重试和审计。

### 阶段 D：通用创作引擎和创作台

- 建立CreationPackage、CreationBatch、GenerationJob/Attempt/Result。
- 支持批量生成、部分成功、单项重试、候选选择和StyleContract。
- 建立SaveToProjectOperation原子保存事务。
- 提供项目导入创作台和创作台独立使用两种入口。

退出条件：项目任务包可导入图片创作台，候选可保存回来源或其他有权限项目，未保存候选不污染项目资产。

### 阶段 E：PPT、视频和交付

- 增加 S3/MinIO 资产存储和预签名上传。
- 建立PPT大纲、逐页规格、封面门禁、视觉契约、正文资产和可编辑混合PPTX装配。
- 迁移视频Provider，按锚点、母版故事、粗分镜、视觉母图、图片资产和细分镜生成shot候选。
- 候选通过技术校验、被选择并保存后才创建正式clip_id。
- 增加 FFmpeg 合成、ffprobe 校验、TTS 和交付包。
- 将所有模型输出注册为资产并建立派生关系。

退出条件：真实图片可作为输入生成真实视频片段，并合成可播放成品。

### 阶段 F：生产化

- PostgreSQL/Alembic 完成，SQLite 只留给单元测试。
- 建立配额、限流、费用、审计、备份、恢复和告警。
- 完成前后端合同测试与端到端验收。

退出条件：MVP 完成定义全部通过，部署和恢复文档齐全。

## 5. 数据迁移

旧基座的 SQLite 数据默认不自动带入生产。若必须保留现有演示项目：

1. 先冻结源实例写入。
2. 导出为版本化 JSON 中间格式，不直接复制数据库文件。
3. 校验项目、节点、任务、产物和引用完整性。
4. 通过一次性导入命令写入 PostgreSQL。
5. 对比数量、校验和和关键业务状态。
6. 保留导入报告与回滚点。

Provider 密钥不得进入导出文件；新系统只迁移配置元数据和新的 `secret_ref`。

## 6. 代码迁移方式

为了保留审计性，推荐在目标仓库通过专用迁移分支完成：

```text
main
  <- migration/backend-baseline
  <- feature/postgres-repositories
  <- feature/model-gateway
  <- feature/asset-pipeline
```

每个 PR 必须列出：源提交 SHA、迁入文件、主动删除内容、合同变化、数据库变化和验证证据。不要直接复制后一次性提交几万行且无法审查。

## 7. 第一批后端任务

1. 输出源基座可复用模块清单和依赖图。
2. 建立目标目录、Python 依赖锁定和 Docker Compose。
3. 迁入 FastAPI 启动、认证和项目 API。
4. 按正式规格建立PostgreSQL核心数据模型与第一版Alembic。
5. 建立内容包、动态教案Schema和Prompt编译最小闭环。
6. 对齐前端需求草案，形成正式`/api/v2`合同和生成客户端。
7. 建立任务、SSE、Outbox、幂等和资产上传最小闭环。
8. 接入一个真实文本模型和一个真实图片模型。
9. 用固定教材完成“上传—课时划分—动态结构教案—确认”的后端验收。

前端可以并行使用 MSW 开发，但联调前必须冻结第一版正式 OpenAPI。
