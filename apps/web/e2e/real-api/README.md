# Real API Playwright

本目录只保存连接真实FastAPI、PostgreSQL和Redis的浏览器验收，不使用MSW、请求拦截、静态响应或浏览器内伪造Session/CSRF。

- `runtime-auth.spec.ts`由Issue #211交付生产会话、刷新恢复、登出和真实创建项目。
- `r1-teacher-flow.spec.ts`由Issue #11 / PR #208交付教材到三类九套及刷新恢复。
- `harness.spec.ts`只验证专用浏览器通道能到达FastAPI和生产登录路由，不能作为业务切片完成证据。

测试使用`../../playwright.real-api.config.ts`和根工作流`.github/workflows/r1-real-api.yml`。任何PR声明本目录中的测试时，必须填写文件路径和精确Playwright标题；本README不是完成证据。

每个测试通过`support/observedApi.ts`只读监听浏览器真实请求，并在完成教师操作后用`expectObservedApi`断言清单声明的方法与路径。监听器不得响应、改写或拦截请求。
