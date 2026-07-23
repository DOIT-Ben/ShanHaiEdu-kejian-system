## 关联任务

Closes #

## 结果

本PR交付：

本PR明确不包含：

## 关键决定

- 说明关键决定；没有则写“无”。

## 影响

- [ ] 前端
- [ ] 后端
- [ ] 数据库或Alembic迁移
- [ ] OpenAPI或JSON Schema
- [ ] 工作流、Prompt或内容包
- [ ] 模型或媒体Provider
- [ ] 现行文档
- [ ] 无外部行为变化

## 验证证据

```text
命令：
结果：
```

真实界面或产物：

## 纵向切片交付

以下两项必须且只能勾选一项。修改`apps/web/src`生产页面、FastAPI路由或active OpenAPI的PR不得退出纵向交付。

- [ ] `vertical-slice-required`：本PR改变生产页面、API路由或active OpenAPI；下列页面—API—事实—测试证据均已填写并可由机器验证。
- [ ] `vertical-slice-not-required`：本PR只修改内部实现、治理、文档或测试，不改变生产页面、API路由或active OpenAPI。

Page routes：

Active operationIds：

Formal facts：

Backend tests：

Real API Playwright：

## 子智能体审查

- [ ] `subagent-review-pending`：仅Draft PR可用；尚未完成独立审查。
- [ ] `subagent-review-approved`：同一独立只读子智能体已完成初审、findings修复复核和最终base/head diff确认，P0/P1全部关闭，P2/P3已修复或显式接受；审查后HEAD未变化。

审查子智能体：

审查engagement：

初审Head SHA：

Base SHA：

Head SHA：

审查范围：

Findings及处置：

残余风险：

审查证据链接：

## 变更规模

以下两项必须且只能勾选一项。机器以全部变更的原始文件数、净新增行数和二进制或未知统计项触发保守门禁；生成物、Schema和迁移例外由评审导航解释。

- [ ] `pr-size-within-limit`：原始变更不超过20个文件、净新增不超过800行，且不含二进制或未知统计项。
- [ ] `pr-size-review-map-required`：原始变更触发文件数、行数或二进制门禁；已提供评审导航和不可继续拆分的理由。

原始规模：

评审导航：

不可继续拆分的理由：

生成物、Schema和迁移例外：

## CURRENT_STATUS新鲜度

以下两项必须且只能勾选一项：

- [ ] `status-update-required`：本PR导致进入新里程碑、可演示能力实质变化、新增或解除阶段阻塞，或下一阶段出口改变；已同步`CURRENT_STATUS.md`。
- [ ] `status-update-not-required`：本PR不改变上述状态事实。

判断依据：

## 迁移与回退

数据或合同兼容方式：

回退或前向修复方式：

## 清理

- [ ] 已删除失效代码、文档和入口
- [ ] 未引入版本副本、补充说明或无归属TODO
- [ ] 临时Feature Flag已关联删除Issue和目标里程碑
- [ ] 未提交密钥、用户素材、模型敏感响应或媒体中间文件

## 交接

下一步唯一动作：

已知失败或阻塞：

后续独立Issue：
