# 渐进式开发与交付路线

本路线描述当前交付顺序，不是所有产品能力的并行开工清单。长期产品行为见`docs/product/`和`docs/workflows/`；当前执行范围由[Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)、当前父Issue和本文件共同约束。

## 1. 当前唯一R1

当前先交付教材到教案的真实教师闭环：

```text
受控教师会话
→ 新建或打开项目
→ 上传/选择教材PDF
→ 选择物理页范围
→ 生成、编辑并批准课时划分
→ 逐课时生成十二部分教案
→ 编辑、局部重生成并批准
→ 生成、编辑并批准三类九套
→ 完成每课时唯一选择
→ 刷新后从正式API和PostgreSQL恢复
```

R1不包含PPT/PPTX、图片生成、视频生成、TTS、完整管理端、自动重试和SSE hardening。这些能力没有被取消，只在R1通过后按独立纵向切片恢复。

## 2. 交付原则

- 先交付能改变教师行为的纵向业务链，再补被真实使用证明必要的共享能力。
- 前后端可以分开实现，但不能分开定义完成；每个业务切片共享同一页面行为、API映射、正式事实和浏览器验收。
- active OpenAPI是当前可调用合同；planned OpenAPI只记录方向，不能生成客户端或作为联调依据。
- 普通CI使用确定性Fake；里程碑出口使用真实文件、真实数据库和受控真实Provider。
- Mock、Fixture、CLI、截图、静态HTML和孤立后端测试不能证明产品完成。
- 已发布Workflow、Prompt、内容Release、Schema和既有项目绑定保持不可变；变化只能前向发布。
- 连续投入后台底层却没有让当前页面更接近可用时，立即停止扩张并回到当前父Issue。
- 一个功能只有在生产页面、合同、后端实现、数据库事实和刷新恢复共同通过后才算完成。

## 3. 当前事实来源

冲突按以下顺序解决：

1. 产品负责人当前明确指令和已批准Decision Issue；
2. 当前父Issue的范围、非范围和验收；
3. 本路线的当前阶段；
4. active OpenAPI、JSON Schema与SSE合同；
5. 当前代码、迁移和测试；
6. `CURRENT_STATUS.md`的当前快照；
7. 长期产品和完整前端设计。

长期设计不自动授权当前开工。发现冲突时直接修改现行来源，不建立V2、最新版、补充说明或兼容性旁路。

## 4. 当前执行顺序

1. [Issue #211](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/211)完成生产Session、Authenticator、CSRF服务端校验和前端会话恢复。
2. [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)与[PR #208](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/208)从最新`main`完成教材到教案的跨栈纵向闭环。
3. 使用一个受控真实小学数学PDF、正式页面、正式API、PostgreSQL和真实文本Provider完成黄金项目复验。
4. 未参与实现的教学验收与工程审查子智能体分别完成一次审查；修复后绑定最终base/head复验。
5. #11关闭后，重新评估[Issue #205](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/205)与[PR #209](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/209)，从最新`main`恢复一个真实短片纵向切片。
6. 短片闭环稳定后，再分别启动PPT/PPTX、完整图片链、完整视频链和TTS。

## 5. 阶段地图

阶段编号表示能力依赖，不表示可以同时开工。

### 阶段0：协作与工程基线

目标：统一Issue、PR、短分支、CI、合同生成和交接规则。

出口：

- 新成员可以从当前Issue接手；
- OpenAPI、JSON Schema、生成客户端、格式、类型和基础测试进入CI；
- `main`保持可审查、可回退和无历史副本文档。

### 阶段1：公共运行基座

目标：打通浏览器、API、PostgreSQL、Worker、对象存储和模型网关。

已具备的公共能力继续复用，不再以新增底座作为当前交付结果。R1必须补齐真实Session/CSRF入口。

出口：

- 空库Alembic升级；
- 上传任务和正式文件事实可运行；
- Provider密钥只存在服务端；
- 正式页面能够安全发起写请求并刷新恢复会话。

### 阶段2 / R1：教材到教案

目标：交付第一个真实教师价值闭环。

要求：

- 真实教材和真实文本Provider；
- 教材物理页范围可合法修订并版本化；
- 默认十二部分由内容定义驱动，不写死在页面或数据库列；
- 每课时教案独立生成、编辑、局部重生成、批准和保留历史；
- 三类九套是独立版本化成果，并形成每课时唯一选择；
- 所有结果从正式API和PostgreSQL恢复。

出口：

- 一个黄金教材在生产页面完成全链；
- 结构化JSON、教师投影和正式资产版本一致；
- Playwright真实API流程与刷新恢复通过；
- 所有CI和独立审查通过。

### 阶段3 / R2：真实短片

R1关闭后才恢复。

稳定切片：

```text
exact已选导入方案 + 一个正式关键帧
→ 真实视频Provider
→ MP4文件事实校验
→ 页面轮询和播放
→ 教师采用
→ 项目视频槽位
→ 刷新恢复
```

不得以Phase A、内容Release、内部runtime、Fixture或历史MP4单独合并并宣称产品完成。旧Release和既有项目绑定不得改写。

### 阶段4 / R3：PPT与完整媒体

PPT首个纵向切片：

```text
批准教案 + 教材证据 + 可选页数
→ PPT内容分析与页级规划
→ 每页无文字16:9背景
→ 原生可编辑文字、公式和内容型图形
→ PPTX装配、导出、预览和批准
→ 刷新恢复
```

之后再扩展完整图片链、完整视频链、音频字幕、TTS和多镜头合成。所有分支复用同一NodeRun、Job、Artifact/FileAsset、Approval和项目槽位，不建立第二套状态机。

### 阶段5：自动化与产品化

在真实纵向切片通过后再增加：

- 完全自动审批策略；
- 多模型路由、限流和故障切换；
- 预算、质量与风险自动暂停；
- 内容包、提示词和工作流管理端；
- 批量生成、生产扩容和完整可观测性；
- 更多学科和教材。

完全自动只是同一工作流上的策略，不是第二套工作流。

## 6. 页面级交付合同

每个业务父Issue必须维护页面—API—正式事实—验收矩阵，至少回答：

- 教师在哪个页面执行什么操作；
- 页面调用哪个active operationId；
- 服务端写入或读取什么正式事实；
- 加载、失败、冲突、权限和刷新如何表现；
- 哪个PostgreSQL集成测试和真实API Playwright证明完成。

缺少任一项时，任务不能进入`in-progress`。前端不得猜接口，后端不得新增没有当前消费者的业务端点来代替页面结果。

PR中的页面路由必须已经注册到`apps/web/src/app/RuntimeApp.tsx`；正式事实必须是当前持久化模型文件中的精确类名，不能使用服务或DTO类；后端和Playwright证据必须填写存在的精确测试选择器。真实API测试固定放在`apps/web/e2e/real-api/`，由`apps/web/playwright.real-api.config.ts`、`test:e2e:real-api`和`.github/workflows/r1-real-api.yml`运行。

## 7. 合并门禁

业务PR转Ready和合并前必须同时满足：

- 当前Issue范围、非范围、依赖和验收明确；
- active OpenAPI与FastAPI运行时双向一致；
- 生成TypeScript客户端无漂移；
- 生产页面实际消费正式API；
- PostgreSQL集成、租户、权限和必要安全负测通过；
- 真实API Playwright通过专用配置与CI启动FastAPI、PostgreSQL和Redis，覆盖关键链路和刷新恢复；MSW、请求拦截和浏览器伪造会话不构成该证据；
- 普通CI Fake与里程碑真实Provider证据分别成立；
- `CURRENT_STATUS.md`更新为最终事实；
- 独立只读子智能体审查绑定最终base/head，P0/P1清零；
- 所有必需检查为绿色。

API、CLI、数据库记录、前端Mock或截图中的任意单项都不能独立关闭业务功能。

## 8. 并发策略

R1关闭前只允许两条活动实现线：

1. #211生产Session/CSRF；
2. #11 / PR #208教材到教案纵向联调。

#211未合并时，#208只能处理不竞争身份入口、active OpenAPI公共生成物和`apps/web`启动入口的既有失败。

以下边界不得被多个活动分支并发修改：

- active OpenAPI和生成客户端；
- Session、Authenticator、CSRF与前端启动入口；
- Artifact审核与质量事实；
- 内容Release与历史快照；
- 统一NodeRun、Job和项目写回状态。

#205/#209、PPT、图片、视频、音频和新的可靠性扩张保持暂停。黄金手册和Fixture可以帮助独立开发，但不能消除共享合同、数据库状态和页面验收之间的依赖。

## 9. 阶段验收与调整

每个阶段结束必须具备：

- 可运行软件和可演示用户结果；
- 自动化测试和真实出口证据；
- 现行文档、合同、实现与状态一致；
- 已知风险和下一阶段Issue；
- 独立审查和最终head复验。

路线调整必须通过Decision Issue。批准后直接修改本文件和受影响的现行来源，不追加版本历史。
