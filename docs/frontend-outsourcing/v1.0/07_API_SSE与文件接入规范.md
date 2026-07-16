# 07 API、SSE与文件接入规范

> 当前业务修订见`15_已确认业务口径修订_2026-07-17.md`。本文件描述前端要求，正式联调仍以后端OpenAPI为准。

## 1. 基础约定

- 正式业务API前缀：`/api/v2`。
- 请求和响应使用UTF-8 JSON，文件上传除外。
- 浏览器使用HttpOnly会话Cookie。
- 非安全方法携带CSRF Token。
- 创建模型运行、上传会话和交付打包必须支持幂等键。
- 时间使用ISO 8601 UTC。
- 金额由后端返回字符串或最小货币单位，前端不得使用浮点自行结算。

## 2. 统一响应

成功：

```json
{
  "data": {},
  "meta": {},
  "request_id": "req_01"
}
```

失败：

```json
{
  "error": {
    "code": "BUDGET_AUTHORIZATION_REQUIRED",
    "message": "本次生成预计超出项目预算，需要确认后继续。",
    "retryable": false,
    "details": {}
  },
  "request_id": "req_01"
}
```

## 3. HTTP状态处理

| 状态 | 前端行为 |
|---|---|
| 400 | 请求不合法，显示节点级错误 |
| 401 | 清理会话缓存并跳转登录 |
| 403 | 权限页或操作权限提示 |
| 404 | 不泄露无权资源详情 |
| 409 | 打开版本冲突或幂等冲突处理 |
| 413 | 文件过大提示 |
| 422 | 映射字段校验错误 |
| 429 | 显示限流和建议重试时间 |
| 500–599 | 持久错误面板并显示Trace ID |

## 4. 前端所需业务域

- Auth：登录、退出、当前会话。
- Projects：项目创建、列表、详情和设置。
- Sources：上传会话、教材解析和证据。
- Lesson Division：划分版本、编辑和批准。
- Lessons：课时列表和详情。
- Workflows：实例、节点和投影步骤。
- Prompts：草稿、版本、编译预览和差异。
- Node Runs：费用估算、提交、取消和重试。
- Artifacts：产物、版本、批准和失效。
- Assets：列表、引用、预览和下载授权。
- Content Definitions：动态结构、UI Schema、字段权限和版本。
- Creation Packages：从项目准备并导入创作台的不可变任务包。
- Creation Batches：通用创作批次、任务项、候选、选择和保存回项目。
- Studios：图片、视频和PPT平台级创作入口。
- Tasks：任务列表和详情。
- Delivery：清单、打包和下载。
- Templates：模板列表、导入、试运行、发布和回滚。
- Model Gateway：Provider、模型、路由、预算、健康和调用记录。

`contracts/frontend-api-requirements.openapi.yaml`是前端需求草案，后端发布的正式OpenAPI为联调唯一事实来源。

## 5. SSE

标准端点：

```text
GET /api/v2/events/stream
GET /api/v2/projects/{projectId}/events/stream
GET /api/v2/jobs/{jobId}/events/stream
```

事件：

- `workflow.node.*`
- `generation.job.*`
- `creation.batch.*`
- `artifact.*`
- `asset.*`
- `ppt.*`
- `video.*`
- `delivery.*`
- `system.notification`

规则：

- 每个事件具有event_id、event_type、occurred_at、project_id、node_run_id、job_id、status、progress、message和最小安全data。
- EventSource断开后指数退避重连。
- 使用最后事件ID恢复。
- 连续失败后退化为低频轮询。
- 收到事件后刷新正式Query数据。
- 事件不得直接覆盖Query缓存中的完整业务对象。

## 6. 上传

推荐流程：

```text
创建上传会话
→ 前端分片或直传对象存储
→ 完成上传会话
→ 后端校验和扫描
→ 创建FileObject
→ 启动解析任务
```

前端要求：

- 类型和大小预检查。
- SHA-256由可选Web Worker增量计算，不能阻塞主线程。
- 上传进度和取消。
- 网络恢复后续传。
- 完成前不得宣称上传成功。
- 等待后端校验、扫描和解析状态。

## 7. 下载

- 前端请求短期下载授权。
- 后端返回一次性或短期URL。
- 前端不拼接私有对象存储地址。
- 下载失败显示文件版本、错误和重新授权操作。
- 已失效产物仍可下载历史版本，但必须标明不是当前批准版本。

## 8. 请求取消

- 页面请求使用AbortController。
- 取消浏览器请求不等于取消后端模型任务。
- 模型任务取消必须调用专用取消端点并等待后端确认。
- 已提交且不支持取消的Provider任务必须明确提示可能继续计费。
