# 山海教育课件系统

面向小学数学教师的一站式课件创作工作台。教师在一个项目中完成教材导入、课时划分、分课时教案、PPT、导入视频、图片与视频资产生成、审核返修和最终交付，不再往返多个模型网站复制提示词和素材。

## 当前仓库定位

本仓库是后续产品、前端、后端、工作流和交付材料的唯一主仓库，活动分支统一使用 `main`。

当前仓库已经形成经确认的产品与运行时设计基线：

- 前端完全重做，不继承旧前端的布局和视觉实现。
- 后端不从零重写，以 `DOIT-Ben/shanhaiedu-v1.0.0` 的 FastAPI、状态机、任务、产物和 Provider adapter 为迁移基座。
- 第一阶段只闭环小学数学，但领域、节点模板和模型 Provider 均预留扩展能力。
- 所有模型调用必须经过后端模型网关；前端不得保存或直接调用 Provider 密钥。
- 教案十二部分是内置默认内容结构，不是写死的程序结构；管理员可以导入新结构包。
- 图片、视频和 PPT 创作台是平台级通用能力，通过创作包导入和结果保存与项目双向通信。

## 从这里开始

1. [当前正式运行时与后端业务设计](docs/superpowers/specs/2026-07-17-shanhai-courseware-platform-runtime-design.md)
2. [统一材料入口](docs/START_HERE.md)
3. [前端已确认业务口径修订](docs/frontend-outsourcing/v1.0/15_已确认业务口径修订_2026-07-17.md)
4. [给前端外包团队的开工指令](docs/vendor/FRONTEND_KICKOFF_INSTRUCTION.md)
5. [后端构建蓝图](docs/architecture/BACKEND_ARCHITECTURE.md)
6. [既有后端迁移计划](docs/architecture/BASELINE_MIGRATION_PLAN.md)
7. [分支、合同与变更规则](docs/governance/BRANCH_AND_CONTRACT_RULES.md)

## 产品主线

```text
教材上传
  -> 课时划分
  -> 每课时动态结构教案
  -> [可选] PPT：大纲 -> 逐页规格 -> 封面 -> 视觉契约 -> 正文 -> PPTX
  -> [可选] 视频：三类九套锚点 -> 母版故事 -> 粗分镜 -> 视觉母图
             -> 图片资产 -> 细分镜 -> shot候选 -> 合格clip -> 合成
  -> 交付
```

PPT 与导入视频都是已批准教案的可选下游分支，但二者在生产链路上互不依赖。锚点选择不读取知识点、教材或教案，只通过已定义的创意类型与锚点库建立；锚点批准后，后续故事节点才使用受控课程知识摘要完成适配。

## 目标技术栈

- 前端：React 19、TypeScript、Vite、React Router、Tailwind CSS、Radix UI、TanStack Query、Zustand。
- 后端：Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic。
- 数据：PostgreSQL 16、Redis 7、S3 兼容对象存储。
- 异步任务：Dramatiq + Redis；模型回调与轮询统一落入任务状态机。
- 媒体：FFmpeg worker；图片、视频、PPTX 和教案文件统一进入资产系统。
- 协议：REST `/api/v2`、SSE 任务事件、OpenAPI 合同。

## 目录规划

```text
apps/
  web/                 新前端
  api/                 FastAPI 应用
workers/               模型、媒体和导出任务消费者
packages/              共享类型、客户端和设计令牌
workflow/              节点、模板、Prompt、Schema 和规则
docs/                  产品、架构、外包和治理材料
infra/                 Docker、部署与可观测性
deliverables/          对外可发送的版本化交付包
```

源码迁入前，不得用占位代码、Mock 结果或空文件宣称业务闭环完成。
