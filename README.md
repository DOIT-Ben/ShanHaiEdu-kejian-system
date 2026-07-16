# 山海教育课件系统

面向小学数学教师的一站式AI课件创作平台。教师上传一个小知识点的教材材料后，在同一系统中完成课时划分、分课时教案、PPT、课堂导入视频、图片与视频创作、审核返修和最终交付。

系统不是模型网站聚合器。课时方法、动态教案结构、三类九套锚点、PPT工作手册、视频故事与分镜流程、Prompt编译、质量规则、自动化策略和模型路由都由平台内置并版本化运行。

## 唯一入口

1. [统一阅读入口](docs/START_HERE.md)
2. [需求分析](docs/product/REQUIREMENTS_ANALYSIS.md)
3. [产品规格](docs/product/PRODUCT_SPEC.md)
4. [端到端业务工作流](docs/workflows/END_TO_END_WORKFLOW.md)
5. [三类九套导入设计](docs/workflows/INTRO_ANCHORS.md)
6. [PPT生产流程与页级合同](docs/workflows/PPT_PRODUCTION.md)
7. [视频生产流程](docs/workflows/VIDEO_PRODUCTION.md)
8. [前端设计与外包规格](docs/frontend/README.md)
9. [后端与数据设计](docs/backend/README.md)
10. [前后端共享合同](contracts/README.md)

仓库当前树只保留一套有效设计，不设置V1/V2并行目录。版本号记录在各模块Manifest和Git提交中；需要追溯旧口径时查看Git历史。

## 产品边界

- 第一阶段闭环小学数学，一个项目对应一个小知识点教材。
- 一个项目包含多个课时，每个课时独立拥有教案，以及可选PPT和可选课堂导入视频。
- 图片、视频和PPT创作台是平台级通用能力，可以脱离项目独立使用。
- 项目通过创作任务包把内容导入创作台；选中的结果通过原子保存操作写回项目。
- 手动、半自动、全自动使用同一套工作流、数据、任务和资产引擎。
- 所有模型调用前展示可编辑业务生成指令；平台安全和输出约束保持只读。

## 技术基线

- 前端：React 19、TypeScript、Vite、React Router、Tailwind CSS、Radix UI、TanStack Query、Zustand。
- 后端：Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic。
- 数据：PostgreSQL 16、Redis 7、S3兼容对象存储。
- 异步任务：Dramatiq＋Redis，媒体处理使用FFmpeg/ffprobe。
- 协议：REST `/api/v2`、SSE、OpenAPI 3.1、JSON Schema。
- 模型：文本、图片、视频和TTS全部经过服务端模型网关。

## 代码目标结构

```text
apps/web/              React教师端与管理端
apps/api/              FastAPI模块化单体
workers/               生成、媒体和导出Worker
workflow/              工作流、Prompt、Schema和规则包
contracts/             前后端共享合同
docs/                  唯一有效产品与工程设计
infra/                 本地和生产基础设施
deliverables/          对外发送的当前交付包
```

不得用Mock、占位图片、静态视频或不可编辑整页截图宣称业务闭环完成。
