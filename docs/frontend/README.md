# 前端设计与外包规格

状态：当前唯一前端基线
规格版本：2.0.0
目标：生产级独立React前端

实施责任：独立前端承接方负责`apps/web`、Storybook、MSW、前端测试和真实API联调；Codex负责Issue #2中的后端平台与共享合同，不代做生产界面。前端任务以GitHub Issue #4为入口。

## 1. 产品形态

教师端是创作台，不是臃肿的流程控制台。工作流、任务、版本和模型运行存在于系统内部，界面首先突出当前作品、当前任务和唯一主操作。

系统采用两种核心工作空间：

- 项目课时工作台：承载教材、课时、教案、PPT、课堂导入视频和交付。
- 通用创作中心：承载独立或项目导入的图片、视频和PPT创作。

二者不能合成一个巨型页面，也不能复制两套生成组件。

## 2. 固定技术栈

- React 19、TypeScript严格模式、Vite。
- React Router、Tailwind CSS、Radix UI/shadcn封装。
- TanStack Query管理服务端状态。
- Zustand只管理界面状态。
- React Hook Form＋Zod处理表单。
- Framer Motion处理克制动效。
- OpenAPI生成客户端；MSW用于无后端开发。
- Vitest、Testing Library、Playwright和Storybook。

不得引入浏览器直连模型、第二套业务数据库、固定十二字段教案组件或复制旧前端页面。

## 3. 阅读顺序

1. `00_产品范围与固定决策.md`
2. `../workflows/INTRO_ANCHORS.md`
3. `../workflows/PPT_PRODUCTION.md`
4. `../workflows/VIDEO_PRODUCTION.md`
5. `01_信息架构与主页.md`
6. `02_项目与课时工作台.md`
7. `03_通用创作中心.md`
8. `04_素材成果与管理端.md`
9. `05_视觉系统与动效.md`
10. `06_组件化与代码架构.md`
11. `07_路由状态与合同接入.md`
12. `08_测试验收与外包交付.md`
13. `../../contracts/`

设计令牌在 `design-tokens/`，逐页、逐组件和最终交付验收表在 `checklists/`。前端包元数据见 `manifest.json`。

## 4. 完成定义

只有源码、Storybook、视觉回归基线、Mock模式、真实API模式、自动化测试、生产构建和交接材料全部通过验收，才视为完成。截图、HTML原型和静态Mock不代表生产前端完成。
