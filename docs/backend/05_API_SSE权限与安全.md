# API、SSE、权限与安全

## 1. API 总则

- 基础路径：`/api/v2`。
- JSON 使用 `snake_case`；时间为 ISO 8601 UTC；ID 为字符串形式 UUID。
- 成功响应：`{ "data": ..., "meta": {...}, "request_id": "..." }`。
- 失败响应：`{ "error": { "code": "...", "message": "...", "retryable": false, "details": {...} }, "request_id": "..." }`。
- 创建异步任务返回 `202 Accepted`，响应中给出 `job_id`、当前状态和事件订阅地址。
- 分页使用游标 `page[cursor]`、`page[limit]`；不向前端暴露数据库 offset。
- 写请求使用 `Idempotency-Key`；草稿和配置更新使用 `ETag` / `If-Match`。
- 删除默认为软删除或归档；永久清理仅由保留策略执行。

## 2. 资源端点

### 项目与教材

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/projects` | 创建单知识点项目 |
| `GET` | `/projects` | 查询项目列表 |
| `GET/PATCH` | `/projects/{project_id}` | 项目详情和设置 |
| `POST` | `/projects/{project_id}/archive` | 归档项目 |
| `POST` | `/projects/{project_id}/materials/uploads` | 创建预签名上传会话 |
| `POST` | `/projects/{project_id}/materials/{material_id}/confirm` | 确认上传并触发解析 |
| `GET` | `/projects/{project_id}/materials/{material_id}/file-asset` | 查询稳定文件身份和不含对象存储位置的当前版本元数据 |
| `GET` | `/projects/{project_id}/materials/{material_id}/parse-versions` | 查询解析版本与引用 |
| `GET/PATCH` | `/projects/{project_id}/lessons` | 查询或原子调整课时顺序、基本信息和归档状态 |
| `GET` | `/lessons/{lesson_id}` | 查询课时详情和四个分支配置 |
| `PATCH` | `/lessons/{lesson_id}/branches` | 开关导入设计、PPT和视频分支 |
| `GET` | `/lessons/{lesson_id}/intro-options` | 读取三类九套、打分和当前选择 |
| `POST` | `/lessons/{lesson_id}/intro-options/generate` | 启动独立创意与锚定两阶段生成 |
| `POST` | `/lessons/{lesson_id}/intro-selections` | 选择一个已批准导入方案 |

上传流程：API 创建会话 → 浏览器直传 S3 → 客户端带 ETag/大小确认 → 后端从私有对象流式核对 MIME、大小与 SHA-256 并入队扫描解析。短期预签名 URL 不持久化，确认前文件不得进入模型上下文。

### 工作流、节点与审核

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/projects/{project_id}/workflow` | 项目工作台聚合查询 |
| `GET` | `/node-runs/{node_run_id}` | 节点详情、输入和状态 |
| `POST` | `/node-runs/{node_run_id}/start` | 手动启动或恢复节点 |
| `POST` | `/node-runs/{node_run_id}/cancel` | 请求取消 |
| `POST` | `/node-runs/{node_run_id}/retry` | 基于原输入创建新运行 |
| `POST` | `/node-runs/{node_run_id}/skip` | 跳过可选节点 |
| `POST` | `/node-runs/{node_run_id}/accept-stale` | 确认沿用过期版本 |
| `GET/PATCH` | `/projects/{project_id}/automation-policy` | 查询或调整项目自动化策略 |
| `POST` | `/artifact-versions/{version_id}/submit` | 提交审核 |
| `POST` | `/artifact-versions/{version_id}/approve` | 批准版本 |
| `POST` | `/artifact-versions/{version_id}/request-changes` | 退回修改 |

### 产物、草稿、提示词与项目资产

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/artifacts/{artifact_id}` | 逻辑产物和当前指针 |
| `GET/PATCH` | `/artifacts/{artifact_id}/draft` | 获取和保存可编辑草稿 |
| `POST` | `/artifacts/{artifact_id}/versions` | 从草稿创建不可变版本 |
| `GET` | `/artifact-versions/{version_id}` | 读取指定版本 |
| `GET` | `/artifact-versions/{version_id}/dependencies` | 来源和影响关系 |
| `GET` | `/node-runs/{node_run_id}/prompt-preview` | 获取可见业务提示词 |
| `POST` | `/node-runs/{node_run_id}/prompt-revisions` | 保存教师修改后的提示词 |
| `GET` | `/projects/{project_id}/asset-package` | 项目资产包聚合视图 |
| `GET` | `/projects/{project_id}/asset-slots` | 槽位及当前绑定 |
| `POST` | `/asset-slots/{slot_id}/bindings` | 手工绑定已有资产 |

草稿 PATCH 必须带 `If-Match`。冲突返回 `409 EDIT_CONFLICT` 和服务器当前版本摘要，前端提供合并而不是覆盖。

### 通用创作中心

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/node-runs/{node_run_id}/creation-packages` | 从项目节点导出不可变创作包 |
| `GET` | `/creation-packages/{package_id}` | 读取创作包和过期提示 |
| `POST` | `/creation-batches` | 独立创建或从包实例化批次 |
| `GET/PATCH` | `/creation-batches/{batch_id}` | 批次详情和设置 |
| `POST` | `/creation-batches/{batch_id}/items` | 新增创作条目 |
| `POST` | `/creation-items/{item_id}/revisions` | 保存提示词、资产和规格修订 |
| `POST` | `/creation-items/{item_id}/generate` | 生成单项候选 |
| `POST` | `/creation-batches/{batch_id}/generate` | 并发生成选定条目 |
| `POST` | `/generation-jobs/{job_id}/cancel` | 取消任务 |
| `POST` | `/generation-results/{result_id}/select` | 选中候选 |
| `POST` | `/generation-results/{result_id}/save-to-project` | 原子保存到项目槽位 |

`save-to-project` 必须明确 `project_id`、`slot_key`、`replace_mode` 和 `Idempotency-Key`。后台不得依据最近访问项目猜测目标。

### PPT、视频和交付

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/lessons/{lesson_id}/ppt` | PPT 文档、页面和审核状态 |
| `PATCH` | `/ppt-pages/{page_id}` | 编辑单页设计草稿 |
| `POST` | `/ppt-documents/{id}/render` | 生成预览或可编辑 PPTX |
| `GET` | `/lessons/{lesson_id}/video` | 视频项目、分镜和镜头状态 |
| `PATCH` | `/video-shots/{shot_id}` | 编辑细分镜和提示词 |
| `POST` | `/video-shots/{shot_id}/select-clip` | 选定合格片段 |
| `POST` | `/video-projects/{id}/assemble` | 创建合成任务 |
| `GET` | `/projects/{project_id}/deliveries` | 交付清单 |
| `POST` | `/projects/{project_id}/deliveries` | 生成交付包 |

管理端资源统一在 `/admin` 下，包括内容包导入/校验/发布、工作流发布、内容发布组合、模型配置、路由测试、预算、用量和审计。管理端接口仍受组织或平台作用域约束，不能仅凭隐藏菜单保护。

## 3. SSE 事件

提供三种订阅范围：

- `/api/v2/events/stream`：当前用户的任务和通知；
- `/api/v2/projects/{project_id}/events/stream`：项目工作台；
- `/api/v2/generation-jobs/{job_id}/events/stream`：单生成任务。

事件采用标准 SSE：

```text
id: 1842
event: generation.job.progress
data: {"event_id":"...","project_id":"...","resource":{"type":"generation_job","id":"..."},"occurred_at":"...","payload":{"status":"running","progress":42}}
```

统一字段：`event_id`、`sequence_no`、`event_type`、`occurred_at`、`project_id`、`resource`、`payload`、`request_id`。浏览器用 `Last-Event-ID` 续传；服务器发送心跳；超过保留窗口返回专用错误，前端重新拉取 REST 快照。

SSE 只用于提示状态变化。任何关键操作完成后，前端以资源 GET 结果为真，不能仅凭某个事件拼装业务状态。

## 4. 错误码

错误码稳定、机器可读，不把供应商错误原样暴露给前端：

- `VALIDATION_FAILED`
- `EDIT_CONFLICT`
- `IDEMPOTENCY_CONFLICT`
- `PRECONDITION_NOT_MET`
- `NODE_NOT_RUNNABLE`
- `CONTENT_RELEASE_INCOMPATIBLE`
- `ASSET_CONTRACT_MISMATCH`
- `MODEL_ROUTE_UNAVAILABLE`
- `PROVIDER_RATE_LIMITED`
- `GENERATION_REJECTED`
- `BUDGET_CONFIRMATION_REQUIRED`
- `STALE_SOURCE_CONFIRMATION_REQUIRED`
- `AUTHENTICATION_REQUIRED`
- `PERMISSION_DENIED`
- `UPLOAD_REJECTED`
- `PDF_MIME_UNSUPPORTED`
- `PDF_SIZE_LIMIT_EXCEEDED`
- `PDF_SIZE_MISMATCH`
- `PDF_SIGNATURE_INVALID`
- `PDF_CHECKSUM_MISMATCH`
- `PDF_ENCRYPTED`
- `PDF_DANGEROUS_STRUCTURE`
- `PDF_PAGE_LIMIT_EXCEEDED`
- `PDF_TEXT_LIMIT_EXCEEDED`
- `PDF_TEXT_BLOCK_LIMIT_EXCEEDED`
- `PDF_IMAGE_REFERENCE_LIMIT_EXCEEDED`
- `PDF_PARSE_TIMEOUT`
- `PDF_DAMAGED`
- `PDF_EVIDENCE_INVALID`
- `PDF_SOURCE_UNAVAILABLE`
- `PDF_PARSE_CANCELLED`
- `PDF_PARSE_INTERNAL_ERROR`

`details` 只返回安全且能帮助用户纠正的问题；供应商完整错误进入受限日志和 Attempt 记录。

## 5. 权限模型

| 动作 | Owner | Editor | Reviewer | Viewer |
| --- | --- | --- | --- | --- |
| 查看项目/资产 | 是 | 是 | 是 | 是 |
| 编辑草稿/提示词 | 是 | 是 | 否 | 否 |
| 启动生成/创作 | 是 | 是 | 否 | 否 |
| 提交审核 | 是 | 是 | 否 | 否 |
| 批准/退回 | 是 | 可配置 | 是 | 否 |
| 开关分支/改自动化 | 是 | 可配置 | 否 | 否 |
| 成员管理/归档 | 是 | 否 | 否 | 否 |

管理端细分 `content_admin`、`workflow_admin`、`model_admin`、`cost_admin`、`audit_viewer`、`platform_admin`。内容发布和生产模型路由修改建议支持双人复核。

## 6. 安全基线

### 鉴权与会话

- 首选 OIDC/OAuth2；Web 使用 Secure、HttpOnly、SameSite Cookie。
- 认证供应商通过服务端端口接入；未配置认证器或缺少有效会话时，受保护接口默认拒绝。
- 可信身份解析为统一 `ActorContext`；测试身份只通过FastAPI依赖覆盖注入，不存在运行时测试Header旁路。
- Cookie 写请求必须有 CSRF 防护；CORS 只允许明确来源。
- 高风险管理操作要求近期重新认证或 MFA。
- API 每次按组织、项目成员和资源归属校验，不能信任前端传入的组织 ID。
- 跨组织或非成员访问项目资源返回404；同项目内角色不足返回403。
- Worker和自动化保留系统主体用于审计，但数据访问仍使用目标任务所属组织作为租户作用域。

### 文件与对象存储

- 上传限制 MIME、扩展名、大小、页数、像素和时长，并进行恶意文件扫描。
- Office/PDF 解析在无网络、低权限容器运行；禁止宏和嵌入脚本。
- 本地 PDF 适配器使用独立隔离解释器、环境变量白名单、禁用 socket 入口、超时强杀和内容数量上限；生产部署仍必须在非 root、无外网、只挂载单个输入文件且配置 CPU/内存配额的媒体 Worker 容器中运行，应用级隔离不替代操作系统沙箱。
- 预签名上传绑定对象键、大小和过期时间；确认时验证哈希和元数据。
- 下载地址短期有效；私有桶禁止公开列目录。
- 远程参考图只接受已上传资产；如支持 URL 导入，必须经 SSRF 防护代理，拦截内网和元数据地址。

### 模型和提示词

- 教材、教案和用户提示词都视为不可信数据，不能覆盖平台安全层或工具权限。
- 上下文按白名单装配，锚点节点执行禁止上下文检查。
- 模型不直接调用数据库、对象存储或任意 URL；工具调用走受限应用服务。
- 密钥保存在 Secret Manager，数据库只保存引用；日志和错误响应必须脱敏。
- 记录供应商的数据保留政策和区域，路由前进行租户政策检查。

### 资源与滥用保护

- 按用户、组织、IP、端点、模型供应商实施不同速率和并发限制。
- 生成前预估成本；长视频、批量生图和大文件需要配额。
- Webhook 校验签名、时间窗和重放；回调载荷大小受限。
- FFmpeg 和渲染进程设 CPU、内存、磁盘、时长和输出限制。

## 7. 审计与隐私

登录、成员/权限变化、项目归档删除、内容/工作流发布、模型路由变化、预算放行、批准撤销、资产覆盖和交付下载必须审计。

日志与监控不得采集完整教材正文、完整提示词、模型密钥、长期下载 URL 或不必要的个人信息。排查内容时通过受权限保护的快照页面访问，并再次留审计。
