# 山海教育课件系统

面向小学数学教师的一站式AI课件创作平台。教师上传一个小知识点的教材材料后，在同一系统中完成课时划分、分课时教案、PPT、课堂导入视频、图片与视频创作、审核返修和最终交付。

系统不是模型网站聚合器。课时方法、动态教案结构、三类九套导入设计、PPT工作手册、视频故事与分镜流程、Prompt编译、质量规则、自动化策略和模型路由都由平台内置并版本化运行。

## 开始之前

不同文件只承担一种职责：

- [AGENTS.md](AGENTS.md)：所有开发者、外包和智能体必须遵守的仓库总则。
- [CURRENT_STATUS.md](CURRENT_STATUS.md)：当前里程碑、活跃任务、阻塞和下一阶段出口。
- [docs/START_HERE.md](docs/START_HERE.md)：按产品、前端、后端和测试角色提供最短阅读路径。
- GitHub Issues：任务范围、验收、决策和交接的唯一事实源。
- GitHub Pull Requests：代码变更、测试证据和合并记录的唯一事实源。

新任务不得通过复制旧文档开始。先领取Issue，再从最新`main`创建短分支。

## 产品边界

- 第一阶段闭环小学数学，一个项目对应一个小知识点教材。
- 一个项目包含多个课时，每个课时独立拥有教案，以及可选PPT和可选课堂导入视频。
- 完整课件项目是产品主入口；图片、视频和PPT创作台是项目节点的专业执行环境，也可作为次级入口独立使用。
- 一键生成与按步骤辅助创作只使用不同的`AutomationPolicy`，共享同一套工作流定义、项目、节点运行、任务、质量门禁和资产。
- 项目通过不可变创作任务包把来源、上下文和目标槽位带入创作台；保存提示词版本、生成候选、采用候选和正式写回项目是四个独立动作。
- 项目模式只能写回创作包固定的来源项目与目标槽位；独立创作保存到项目时必须显式选择目标并重新鉴权。
- 所有模型调用前展示可编辑业务生成指令；平台安全和输出约束保持只读。

## 现行设计入口

1. [需求分析](docs/product/REQUIREMENTS_ANALYSIS.md)
2. [产品规格](docs/product/PRODUCT_SPEC.md)
3. [端到端业务工作流](docs/workflows/END_TO_END_WORKFLOW.md)
4. [三类九套导入设计](docs/workflows/INTRO_ANCHORS.md)
5. [PPT生产流程与页级合同](docs/workflows/PPT_PRODUCTION.md)
6. [视频生产流程](docs/workflows/VIDEO_PRODUCTION.md)
7. [内置提示词、输入输出模板与黄金示例](docs/workflows/generation-guide/README.md)
8. [前端设计与外包规格](docs/frontend/README.md)
9. [后端与数据设计](docs/backend/README.md)
10. [前后端共享合同](contracts/README.md)
11. [团队协作流程](docs/governance/TEAM_WORKFLOW.md)
12. [文档生命周期](docs/governance/DOCUMENT_POLICY.md)
13. [渐进式交付路线](docs/governance/DELIVERY_ROADMAP.md)

仓库当前树只保留一套有效设计，不设置V1/V2并行目录。历史由Git提供；日常任务和讨论由Issue/PR提供。

## 技术基线

- 前端：React 19、TypeScript、Vite、React Router、Tailwind CSS、Radix UI、TanStack Query、Zustand。
- 后端：Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic。
- 数据：PostgreSQL 16、Redis 7、S3兼容对象存储。
- 异步任务：Dramatiq＋Redis，媒体处理使用FFmpeg/ffprobe。
- 协议：REST `/api/v2`、SSE、OpenAPI 3.1、JSON Schema。
- 模型：文本、图片、视频和TTS全部经过服务端模型网关。

## 后端基座快速开始

需要 Python 3.12、uv 和 Docker Desktop。首次启动：

```powershell
Copy-Item .env.example .env
uv sync --frozen
docker compose -f infra\compose.yaml up -d postgres redis minio
uv run alembic upgrade head
uv run python scripts\smoke_local_stack.py
uv run python -m workers.main --check
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

容器使用 `GET /health/live` 和 `GET /health/ready`；共享API合同中的兼容路径是 `GET /api/v2/health/live` 和 `GET /api/v2/health/ready`。停止本地依赖但保留数据：

```powershell
docker compose -f infra\compose.yaml down
```

本地 `.env`、数据库、缓存和对象存储数据不得提交。普通测试和CI不连接真实模型Provider。

真实文本模型只通过显式冒烟命令调用。先在受控环境中注入密钥变量，不把密钥写入`.env`、命令历史或参数；再配置非敏感路由并运行：

```powershell
$env:SHANHAI_TEXT_PROVIDER_NAME="openrouter"
$env:SHANHAI_TEXT_PROVIDER_BASE_URL="https://openrouter.ai/api/v1"
$env:SHANHAI_TEXT_PROVIDER_MODEL="<approved-model>"
$env:SHANHAI_TEXT_PROVIDER_SECRET_ENV="OPENROUTER_API_KEY"
uv run python -m apps.api.cli model-smoke --capability text.smoke --real
```

命令只输出脱敏Provider/模型、request ID、UTC、耗时、用量、成本和结论，不输出密钥、提示词或模型正文。

## 目标代码结构

```text
apps/web/              React教师端与管理端
apps/api/              FastAPI模块化单体
workers/               生成、媒体和导出Worker
workflow/              工作流、Prompt、Schema和规则包
contracts/             前后端共享合同
docs/                  唯一有效产品与工程设计
infra/                 本地和生产基础设施
scripts/               可重复执行的仓库与开发工具
deliverables/          当前明确需要对外发送的交付包
```

不得用Mock、占位图片、静态视频或不可编辑整页截图宣称业务闭环完成。
