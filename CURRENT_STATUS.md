# 当前项目状态

更新时间：2026-07-23  
验证基线：`main@4ff6f90af304e7521576b34b77de95044bc6f1bc`  
当前收口决定：[Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)

本文件只记录当前事实、阻塞和下一出口，不保存开发历史。历史由Git、Issue和Pull Request保存。

## 当前阶段

当前唯一里程碑是R1“教材到教案纵向闭环”：

```text
建立受控教师会话
→ 新建或打开项目
→ 上传/选择教材PDF
→ 选择物理页范围
→ 生成课时划分
→ 编辑并批准
→ 为每课时生成十二部分教案
→ 编辑、局部重生成并批准
→ 生成三类九套
→ 批准并完成唯一选择
→ 刷新后从正式API和PostgreSQL恢复
```

R1必须由生产前端、active OpenAPI、FastAPI运行时、PostgreSQL和受控真实文本Provider共同证明。Mock、Fixture、CLI、截图或孤立API测试不能替代浏览器出口。

## 已确认完成

- 后端公共基座已经具备FastAPI、PostgreSQL、Redis、对象存储、Alembic、Worker、Outbox/SSE、幂等、模型网关、内容发布、工作流运行时、Artifact版本/审核、课时划分、十二部分教案、三类九套和唯一选择等基础能力。
- OpenAPI、JSON Schema、生成TypeScript客户端、确定性Fake和相关CI门禁已经建立。
- 受控真实文本模型冒烟已经完成；普通CI继续使用确定性Fake。
- 生产前端基线已经通过[PR #111](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/111)合并进入`main`。它是工程和视觉基线，不代表真实业务联调已经完成。
- 正式内容Release与既有项目绑定保持不可变；任何后续Release只能前向发布，不能修改历史快照。

## 当前活动任务

### P0身份前置

[Issue #211](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/211)负责生产Session、Authenticator、CSRF签发/校验、前端会话恢复和真实写请求。它是#11合并前的强制前置。

### R1纵向联调

[Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)是唯一R1跨栈实现入口；[PR #208](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/208)保持Draft。

PR #208当前不能合并，已确认存在：

- 没有`apps/web`真实消费者，尚未交付其声明的教师页面结果；
- 生成OpenAPI/TypeScript产物漂移；
- active/planned合同分区测试失败；
- 集成测试调用不存在的审核路由并返回404；
- 跨模块ORM导入和文件/函数增长门禁失败；
- 真实Provider、真实浏览器和刷新恢复尚未验证。

### 暂停任务

[Issue #205](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/205)与[PR #209](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/209)暂停，不得以Phase A或后端局部完成合并。

PR #209当前还存在历史Release校验漂移、跨模块ORM依赖、文件规模和PostgreSQL集成失败。只有#11合并并完成R1黄金项目复验后，才允许从最新`main`重新定界和恢复。

PPT/PPTX、完整图片链、完整视频链、TTS、管理端扩张、自动重试和SSE hardening均不属于当前R1。

## 当前阻塞

1. 生产前端没有可用的Session与CSRF启动闭环，正常用户无法完成正式写请求。
2. #208的合同、后端实现、生成客户端、生产页面和浏览器验收尚未形成同一条链。
3. 教材范围重新选择必须形成可追溯新版本，不能因固定Artifact键阻塞合法修订。
4. 长模型调用必须通过现有Job/Worker/SSE运行，不得用同步HTTP长请求形成第二套执行路径。
5. 所有必需CI和独立只读子智能体审查尚未通过。

## 当前唯一执行顺序

1. 完成并合并#211；验证真实页面可以建立会话、刷新恢复并成功创建项目。
2. #208从最新`main`同步，只修复R1页面真实需要的最窄合同和运行时缺口。
3. 在#208中完成`apps/web`真实消费：教材、物理页、课时划分、教案、三类九套、编辑/局部重生成、批准、唯一选择和刷新恢复。
4. 通过后端质量、PostgreSQL、合同、前端质量、Storybook、production build和真实API Playwright。
5. 使用一个受控小学数学PDF和真实文本Provider完成黄金项目复验。
6. 由未参与实现的只读子智能体绑定最终base/head审查；P0/P1清零后合并#208并关闭#11。
7. R1关闭后再重新评估并恢复短视频，然后是PPT/PPTX和完整媒体链。

## R1出口门禁

- [ ] #211已合并，Session和CSRF服务端校验通过。
- [ ] active OpenAPI与FastAPI运行时双向一致。
- [ ] 生成TypeScript客户端无漂移。
- [ ] 生产页面实际消费正式API，不加载生产Mock。
- [ ] PostgreSQL集成、租户、权限和CSRF负测通过。
- [ ] 真实API Playwright完成全链并验证刷新恢复。
- [ ] 受控真实教材和真实文本Provider出口通过。
- [ ] 所有必需CI为绿色。
- [ ] 独立只读子智能体审查绑定最终base/head，P0/P1清零。
- [ ] 本文件已经更新为合并后的真实结果。

## 并发与文件所有权

R1关闭前只允许两条活动实现线：

1. #211身份前置；
2. #11 / PR #208纵向联调。

前置未合并时，#208只能修复不竞争身份入口、active OpenAPI公共生成物和`apps/web`启动入口的既有失败。共享OpenAPI、生成客户端、身份依赖、Artifact审核和内容Release不得由多个分支并发修改。

前后端保持代码所有权分离，但不再分开验收。页面、合同、后端实现、正式事实和浏览器结果必须在同一个业务切片中共同关闭。

## 接手顺序

1. `README.md`
2. `AGENTS.md`
3. 本文件
4. Decision #210
5. 当前分配的Issue与PR
6. 与该切片直接相关的文档、合同、代码和测试

不要从旧聊天、历史分支、planned API或已关闭Issue恢复范围。
