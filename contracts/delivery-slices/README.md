# 纵向交付切片清单

每个改变生产页面、FastAPI 路由或 active OpenAPI 的 PR，都必须新增或更新一份与任务绑定的 YAML 清单：

```text
contracts/delivery-slices/<issue>-<slice>.yaml
```

清单遵守 `contracts/delivery-slice.schema.json`，并把同一条教师业务链的生产路由、真实导航地址、active API 请求、PostgreSQL 正式事实、后端集成测试和真实 API Playwright 测试绑定在同一行。PR 正文五类证据的并集必须与清单完全一致；清单中的 Issue 必须与 `Closes #<issue>` 和文件名前缀一致。

清单不是完成声明本身。CI 仍会运行精确测试选择器，独立评审仍需判断测试断言是否真正覆盖该行的业务因果关系。

CI 执行入口是 `scripts/run_delivery_slice_tests.py`；它会读取本目录全部 YAML 清单，逐个运行后端与真实 API 浏览器选择器，不允许用一次宽泛测试运行代替清单证据。
