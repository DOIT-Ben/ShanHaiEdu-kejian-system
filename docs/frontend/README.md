# 前端设计与外包规格

状态：当前唯一前端基线

目标：生产级React教师创作台

当前交付决定：[Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)

## 1. 产品形态

教师端是创作台，不是流程控制台。长期产品包含：

- 项目课时工作台：教材、课时、教案、PPT、课堂导入视频和交付；
- 通用创作中心：独立或项目导入的图片、视频和PPT创作。

二者复用生成、审核、资产和任务组件，不能合成巨型页面，也不能复制两套业务状态。

## 2. 当前R1边界

长期设计不等于当前开工范围。R1只实现：

```text
会话
→ 项目
→ 教材PDF与物理页
→ 课时划分
→ 十二部分教案
→ 三类九套与唯一选择
→ 刷新恢复
```

R1入口是Issue #11；Session/CSRF前置是Issue #211。PPT、图片、视频、TTS和管理端等长期页面在R1关闭后由新的当前Issue激活。

PR #111已经合并，它提供生产前端工程和视觉基线，不代表R1真实业务联调完成。

## 3. 责任边界

前端承接方负责：

- `apps/web`；
- Storybook、MSW、前端测试和构建部署；
- active OpenAPI生成客户端的消费；
- 真实API联调和页面体验。

后端/合同所有者负责：

- `apps/api`、Worker、数据库、对象存储和模型网关；
- active OpenAPI、JSON Schema、SSE与错误语义；
- 业务状态、权限、CSRF服务端校验和正式持久化事实。

代码所有权分离，验收不分离。一个功能必须共享同一页面—API—事实—验收矩阵。

## 4. 固定技术栈

- React 19、TypeScript严格模式、Vite；
- React Router、Tailwind CSS、Radix UI/shadcn；
- TanStack Query管理服务端状态；
- Zustand只管理界面状态；
- React Hook Form与Zod；
- Framer Motion；
- OpenAPI生成客户端；
- Vitest、Testing Library、Playwright和Storybook。

不得引入浏览器直连模型、第二套DTO、第二套业务状态机、固定十二字段页面或生产Mock。

## 5. 页面与合同规则

- 页面只消费`contracts/api-surface.openapi.yaml`生成的客户端。
- `contracts/planned-api-surface.openapi.yaml`不得进入客户端或MSW运行时。
- 每个当前业务页面必须有正式列表/详情入口，不能依赖手工输入内部ID。
- 写操作必须通过生产Session、授权与CSRF；前端自带Token不能代替服务端校验。
- 长任务使用现有Job/Worker/SSE或明确的状态查询，不阻塞HTTP等待模型完成。
- 加载、空数据、权限失败、业务失败、409冲突和刷新恢复必须显式实现。
- Storybook和MSW用于组件与普通测试；真实联调必须使用正式API和PostgreSQL。

## 6. 阅读顺序

1. `../../README.md`
2. `../../AGENTS.md`
3. `../../CURRENT_STATUS.md`
4. Decision #210和当前Issue/PR
5. `00_产品范围与固定决策.md`
6. 当前切片需要的页面文档
7. `07_路由状态与合同接入.md`
8. `08_测试验收与外包交付.md`
9. `../../contracts/`

PPT和视频工作流文档只在对应Issue激活后进入当前阅读范围。

## 7. 完成定义

当前业务切片只有同时满足以下条件才完成：

- 生产页面实际消费active API；
- 生成客户端无漂移；
- 正式Session、权限和CSRF通过；
- 正式API与PostgreSQL保存通过；
- Playwright覆盖关键链路和刷新恢复；
- format、lint、typecheck、单元、Storybook build和production build通过；
- 生产构建不加载MSW；
- 独立只读子智能体审查绑定最终base/head，P0/P1清零。

Figma、截图、HTML、Storybook、MSW和预览链接都不能单独证明生产功能完成。
