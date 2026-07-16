# 跨前后端合同

本目录保存前端、后端和内容运行时共同依赖的唯一现行机器合同。设计说明见 `docs/backend/05_API_SSE权限与安全.md`，本目录文件优先用于代码生成、Mock 和 CI 校验。

## 文件

- `api-conventions.md`：HTTP、分页、并发、幂等和错误约定。
- `api-surface.openapi.yaml`：当前核心联调面；后端实现须生成更完整 OpenAPI，且不得违背此处语义。
- `error-envelope.schema.json`：统一错误响应。
- `sse-event.schema.json`：统一事件信封。
- `workflow-node-status.schema.json`：节点状态枚举。
- `intro-option-set.schema.json`：三类九套导入设计、最小课程锚点和选择交接。
- `ppt-page-spec.schema.json`：PPT逐页四层结构、白底和可编辑内容合同。
- `video-shot.schema.json`：细分镜、垫图引用和10/15秒生成合同。
- `creation-package.schema.json`：项目导入通用创作中心的不可变包。
- `content-definition.schema.json`：动态内容字段树。
- `mock-scenarios.json`：前端必须覆盖的关键 Mock 场景。
- `fixtures/stage0/`：阶段0项目、上传、任务、错误和SSE的确定性合同样例。
- `generated/`：由当前OpenAPI确定性生成的bundle和TypeScript类型，不是第二份手工合同。
- `typescript/client.ts`：基于生成paths和openapi-fetch的共享客户端工厂。

## 使用规则

1. 前端从 OpenAPI 生成 API 类型，不手写第二套 DTO。
2. 后端 CI 校验响应和事件符合 Schema。
3. 破坏性变更必须同时修改调用方、测试、迁移和本文档，不另建补丁说明。
4. 未在合同中定义的供应商字段只能停留在后端适配层，不能泄漏为前端依赖。
5. Schema ID 和枚举值一经发布不得改变语义。

## 本地命令

```powershell
pnpm install --frozen-lockfile
pnpm contracts:lint
pnpm contracts:generate
pnpm contracts:typecheck
pnpm contracts:test
pnpm contracts:check-generated
```

首次更新依赖锁时运行 `pnpm install`。修改OpenAPI后必须重新生成并提交 `contracts/generated/`；CI会拒绝生成漂移和未声明的破坏性变更。
