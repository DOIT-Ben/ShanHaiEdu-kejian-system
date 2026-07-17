# API 约定

## 请求与响应

- 基础路径：`/api/v2`；媒体类型：`application/json`。
- 成功：`data` 必填，`meta` 可选，`request_id` 必填。
- 失败：使用 `error-envelope.schema.json`。
- 列表：`data.items` 与 `meta.next_cursor`；请求参数 `page[cursor]`、`page[limit]`。
- 创建普通资源返回 201；创建长任务返回 202；成功删除或无正文操作返回 204。
- 日期时间使用 UTC ISO 8601；金额用十进制字符串；ID 为 UUID 字符串。

## 并发与幂等

- 草稿和配置 GET 返回 `ETag`，更新必须带 `If-Match`。
- 版本冲突返回 409 `EDIT_CONFLICT`，不允许后写覆盖先写。
- 创建资源、生成、重试、批准和保存回项目带 `Idempotency-Key`。
- 同一幂等键和同一请求摘要返回原结果；同键不同摘要返回 409 `IDEMPOTENCY_CONFLICT`。

## 认证与授权

- 除健康检查外，API使用服务端签发的`shanhai_session`安全Cookie，经认证端口解析为`ActorContext`。
- 浏览器不得通过组织、用户或主体Header选择身份；组织作用域来自可信认证结果和数据库成员关系。
- 缺少认证器、会话或有效身份返回401 `AUTHENTICATION_REQUIRED`；禁用身份或角色权限不足返回403 `PERMISSION_DENIED`。
- 跨组织或非项目成员访问项目资源统一返回404，不泄露资源是否存在。
- Worker和自动化使用可区分的系统主体，但仍按目标任务的组织作用域读取和写入业务数据。

## 异步任务

202 响应包含：

```json
{
  "data": {
    "job_id": "01900000-0000-7000-8000-000000000001",
    "status": "queued",
    "events_url": "/api/v2/generation-jobs/01900000-0000-7000-8000-000000000001/events/stream"
  },
  "request_id": "req_01"
}
```

页面刷新不影响任务。客户端以 GET 查询为真，以 SSE 触发刷新。

## 文件

上传：创建上传会话 → 直传私有对象存储 → 确认 → 后端扫描/解析。下载：每次申请短期签名 URL。前端不得持久化签名 URL 或供应商 URL。

## 兼容性

- 新增可选字段为兼容变更；消费者须忽略未知字段。
- 删除、改名、改变枚举语义、从可选改必填、收窄类型为破坏性变更。
- 对未知节点状态，前端展示“状态待升级”并允许刷新，不能误判为成功。
