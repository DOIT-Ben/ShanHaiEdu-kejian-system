# 山海教育课件系统统一阅读入口

本仓库当前树只保留一套有效口径。不要从Git历史、旧聊天记录或外部压缩包复制需求。

## 产品和项目负责人

1. `docs/product/REQUIREMENTS_ANALYSIS.md`
2. `docs/product/PRODUCT_SPEC.md`
3. `docs/workflows/END_TO_END_WORKFLOW.md`
4. `docs/workflows/INTRO_ANCHORS.md`
5. `docs/workflows/PPT_PRODUCTION.md`
6. `docs/workflows/VIDEO_PRODUCTION.md`
7. `docs/frontend/README.md`
8. `docs/backend/README.md`

## 前端团队

1. `docs/product/REQUIREMENTS_ANALYSIS.md`
2. `docs/frontend/README.md`
3. `docs/workflows/INTRO_ANCHORS.md`
4. `docs/workflows/PPT_PRODUCTION.md`
5. `docs/workflows/VIDEO_PRODUCTION.md`
6. `docs/frontend/00_产品范围与固定决策.md`
7. `docs/frontend/01_信息架构与主页.md`
8. `docs/frontend/02_项目与课时工作台.md`
9. `docs/frontend/03_通用创作中心.md`
10. `docs/frontend/04_素材成果与管理端.md`
11. `docs/frontend/05_视觉系统与动效.md`
12. `docs/frontend/06_组件化与代码架构.md`
13. `docs/frontend/07_路由状态与合同接入.md`
14. `docs/frontend/08_测试验收与外包交付.md`
15. `contracts/`

## 后端团队

1. `docs/product/REQUIREMENTS_ANALYSIS.md`
2. `docs/backend/README.md`
3. `docs/workflows/INTRO_ANCHORS.md`
4. `docs/workflows/PPT_PRODUCTION.md`
5. `docs/workflows/VIDEO_PRODUCTION.md`
6. `docs/backend/00_系统架构.md`
7. `docs/backend/01_领域模型与资产版本.md`
8. `docs/backend/02_工作流与创作引擎.md`
9. `docs/backend/03_内容运行时与模型网关.md`
10. `docs/backend/04_数据库设计.md`
11. `docs/backend/05_API_SSE权限与安全.md`
12. `docs/backend/06_测试迁移与交付.md`
13. `contracts/`

## 事实来源优先级

1. `docs/product`和`docs/workflows`定义业务语义与流程。
2. `contracts`定义跨前后端的机器边界。
3. `docs/backend`与`docs/frontend`定义各自工程实现。
4. 已合并到`main`的迁移、生成OpenAPI、代码和测试必须实现以上设计；冲突视为缺陷。

发现冲突必须修改现行源文档、合同和实现，不得增加“补充说明”“临时兼容说明”继续叠加口径。
