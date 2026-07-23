# 给生产前端承接方的开工与续接指令

本文件只说明生产前端的长期工程边界和当前续接方式。当前交付顺序由[Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)、`CURRENT_STATUS.md`、`docs/governance/DELIVERY_ROADMAP.md`和当前Issue共同决定。

## 当前状态

- 生产前端基线已经通过[PR #111](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/111)合并进入`main`。
- 不再创建新的`feat/4-production-frontend`或长期前端重构分支。
- 当前唯一前端业务任务是[Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11) / Draft PR #208中的R1真实纵向联调。
- [Issue #211](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/211)负责生产Session与CSRF前置。
- PPT、图片、视频、TTS、管理端扩张和完整创作中心不属于当前R1开工范围；长期设计继续保留，但不能据此自行实现。

## 可直接发送的当前指令

> 接手仓库：`https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system`
>
> 开始前依次阅读`README.md`、`AGENTS.md`、`CURRENT_STATUS.md`、Decision #210、当前分配的Issue/PR、`docs/frontend/`和与该切片相关的active合同。不要从旧聊天、历史分支、planned API或本文件的长期产品章节自行恢复范围。
>
> 你负责`apps/web`、Storybook、MSW、前端测试、前端构建部署和真实API消费。不得修改`apps/api`、`workers`、`workflow`、`infra`、数据库、模型网关、服务端任务队列或OpenAPI/JSON Schema业务语义。
>
> 前端与后端保持代码所有权分离，但必须共享同一个功能Issue、页面—API—事实—验收矩阵和最终Playwright结果。发现合同缺口时，在当前Issue提交复现、影响、建议operationId和页面阻塞；由合同所有者修改active OpenAPI。不得手写第二套DTO或私有状态机。
>
> 当前R1页面必须完成：
>
> ```text
> 建立受控教师会话
> → 新建或打开项目
> → 上传/选择教材PDF
> → 选择物理页范围
> → 生成、编辑并批准课时划分
> → 逐课时生成、编辑、局部重生成并批准十二部分教案
> → 生成、编辑并批准三类九套
> → 完成每课时唯一选择
> → 刷新后从正式API和PostgreSQL恢复
> ```
>
> Session和CSRF不得由sessionStorage测试值、手工Cookie或生产Mock代替。所有写操作必须通过服务端会话、授权和CSRF校验。
>
> active API类型只从`contracts/api-surface.openapi.yaml`生成。`planned-api-surface.openapi.yaml`只用于查看方向，不得生成客户端、MSW运行时接口或冒充可联调能力。
>
> 每个页面状态必须覆盖加载、空数据、权限失败、业务错误、409冲突、长任务进度和刷新恢复。不得因为端点缺失而保留“即将开放”、固定error状态、只读壳或必须手工输入内部ID的页面作为完成结果。
>
> 普通前端测试可以使用MSW；真实联调验收必须使用生产构建或等价真实运行时、正式API和PostgreSQL。生产构建不得加载MSW、供应商密钥、调试后门或浏览器直连模型代码。
>
> 修改生产页面时，必须与切片所有者共同改变`contracts/delivery-slices/<issue>-<slice>.yaml`。每行写明生产路由、具体导航地址、active API方法/路径、SQLAlchemy正式事实、后端集成测试和`apps/web/e2e/real-api/`精确测试标题；PR正文证据并集必须与清单一致。前端代码所有权分离不等于允许前端单独宣告功能完成。

## 代码边界

前端唯一代码范围：

- `apps/web`；
- Storybook与视觉回归；
- 前端MSW测试场景；
- 前端单元、组件和Playwright测试；
- 前端构建、部署配置和生成客户端消费封装。

明确禁止：

- 服务端业务、数据库、Worker、任务队列或Provider调用；
- 修改OpenAPI和JSON Schema业务语义；
- 私有DTO、私有业务状态机或复制后端校验；
- 使用localStorage、静态JSON、定时器假进度或Fixture冒充正式保存；
- 创建第二套前端、长期frontend分支或不可评审的一次性代码包。

## 固定技术栈

React 19、TypeScript严格模式、Vite、React Router、Tailwind CSS、Radix UI/shadcn、TanStack Query、Zustand仅管理UI状态、React Hook Form、Zod、Framer Motion、Vitest、Testing Library、Playwright和Storybook。

不得改用Next.js、低代码平台或浏览器直连模型的框架。

## R1交付清单

- 登录、会话恢复、过期和登出界面。
- 项目列表、新建项目和项目恢复。
- 教材上传/选择、解析状态和物理页范围。
- 课时划分生成、编辑、批准和刷新恢复。
- 每课时十二部分教案生成、字段编辑、局部重生成、批准和历史状态。
- 三类九套生成、编辑、批准、唯一选择和刷新恢复。
- active OpenAPI生成客户端消费，不维护重复DTO。
- Storybook覆盖关键组件状态。
- 真实API Playwright覆盖完整R1和刷新恢复。
- 1440、1280、1024和390关键页面回归。
- format、lint、typecheck、Vitest、Storybook build和production build通过。
- 删除被本次实现替代的占位、固定error、known-ID入口和生产Mock路径。

## 长期产品边界

完整产品仍包含项目课时工作台、通用图片/视频/PPT创作中心、PPT/PPTX、课堂导入视频、任务、资产、交付和管理端。相关设计保留在`docs/frontend/`和`docs/workflows/`。

这些内容只有在R1关闭并由新的当前Issue激活后才能实施。承接方不得把长期页面清单当作当前并行任务，也不得因为长期页面尚未接入而阻塞R1。

## 完成定义

R1前端只有同时满足以下条件才算完成：

- 页面真实操作使用active API；
- 正式Session、授权和CSRF通过；
- PostgreSQL保存与刷新恢复通过；
- 真实API Playwright通过；
- 生产构建不包含Mock；
- 生成客户端无漂移；
- 所有前端必需检查为绿色；
- 当前Issue验收完成；
- 独立只读子智能体审查绑定最终base/head，P0/P1清零。

截图、录屏、Figma、Storybook、MSW、ZIP或预览链接都不能单独替代上述证据。
