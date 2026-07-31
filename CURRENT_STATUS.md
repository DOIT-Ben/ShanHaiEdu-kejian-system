# 当前项目状态

当前阶段：阶段1后端基座、R1教材到教案链、三类九套和约6秒课堂导入短片已经形成教师可见MVP并进入`main`；真实文本与视频Provider黄金项目、对象生命周期加固、独立审查和合并后复验均已完成。当前正在执行[P0 Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244)正式环境部署。
> 最后核验：2026-08-01。
> 当前 #244 为 `status:in-progress`；PR #254 至 #260 已合并，当前在 `hotfix/244-loopback-ingress-network` 修复首次发布暴露的宿主回环入口；普通开发与CI继续只使用确定性Fake。

## 当前可演示成果

- 生产前端`/login`通过真实FastAPI和PostgreSQL使用受控access code建立Session；Session与CSRF可刷新恢复，登出后原Session和CSRF失效。
- 教师可以在真实页面完成教材物理页范围确认、异步课时划分、十二部分教案生成与编辑、质量检查、exact ArtifactVersion批准、三类九套生成、唯一IntroSelection和刷新恢复。
- 同一Project下多个LessonUnit按exact project/lesson/version隔离；跨租户、错误版本、重复生成和登出后写入均有PostgreSQL与真实API浏览器负测。
- 教师可以从exact已采用IntroSelection和同课时正式关键帧启动约6秒视频生成，查看进度或失败原因，播放、exact采用并刷新恢复LessonUnit视频槽位。
- 真实文本黄金项目已经通过`NewAPI -> deepseek`受控验收；真实视频黄金项目只提交一次NewAPI请求且零重试，生成6.041667秒H.264 MP4并完成文件、血缘、采用和刷新恢复校验。

## 已完成

- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)及R1纵向结果已经关闭；#231、#234、#235和#241分别交付十二部分教案、教材范围与课时划分、三类九套和受控真实文本Provider验收。
- [Issue #205](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/205)已经由[PR #247](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/247)Squash Merge并关闭，完成约6秒真实视频教师黄金切片。
- [Issue #248](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/248)已经由[PR #252](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/252)Squash Merge并关闭；merge commit `67b4d00c`完成staging校验、幂等晋升、PostgreSQL final-only血缘和保守GC，main上的治理、合同、Python质量、PostgreSQL/Alembic和真实API workflow全部通过。
- [Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)定义的五个教师可见R1结果、纵向合并门禁和exact base/head审查要求已经落实；历史Draft PR #222与#230均已关闭，不再是当前实现入口。

## 当前工作

- [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244)当前为`status:in-progress`。PR #254 至 #260 已合并，最新生产基线为`main@0f6a8477ce0d17496e6f5eeb71a81a6bd9d330be`。
- exact基线首次发布已完成Alembic、内容发布、身份初始化、PostgreSQL/MinIO备份与恢复校验，并确认API、Worker和Web容器内部健康；随后因internal Docker网络不发布宿主端口而安全失败，`current`与Nginx均未切换，旧公网入口仍保留。
- 当前`hotfix/244-loopback-ingress-network`仅让不挂载Secret的Web/Caddy额外挂载非NAT loopback网络，在internal网络内反代API与MinIO；进入再次发布前仍须完成Draft PR、CI和exact base/head独立审查。
- [Issue #165](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/165)以`status:blocked`独立跟踪视频relay安全迁移；第三次迁移已回滚，生产仍运行迁移前relay，第四次尝试需要新的明确生产授权且不得调用真实Provider。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)和[Issue #237](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/237)为`status:ready`技术债，不代表下一产品里程碑，也不阻塞当前MVP事实。

## 当前阻塞

- #244原先的八项生产决定（主机身份、所有权、操作系统和可用资源；域名、DNS、TLS证书和反向代理；Web、API、Worker、PostgreSQL、Redis、对象存储拓扑与持久化边界；Session/CSRF/CORS/Cookie、访问码、Provider和对象存储密钥的受控注入与轮换；Alembic迁移、迁移前备份、恢复验证和不可逆迁移处置；健康检查、结构化日志、错误率、延迟、队列深度、磁盘和数据库连接监控；精确版本发布、回退触发条件、旧版本保留和回退演练；首次发布采用受控内测或公开开放及其访问控制边界）已获批准，当前不再构成阻塞。
- ECS exact release确认`production`网络的`internal: true`使Compose声明的API/MinIO宿主端口在运行态没有端口映射；旧入口未切换且应用层已停止，数据依赖保持健康。当前最小修复已通过本机临时Compose入口验证，仍待PR、CI、独立审查、合并后新SHA重建与ECS复验。
- #165缺少第四次受控迁移的独立授权和发布窗口；任何门禁失败必须自动回滚并停止，不自动重试。
- 当前没有已知Session/CSRF、PostgreSQL、Worker、active OpenAPI、生产页面、真实文本/视频黄金验收或视频对象生命周期实现阻塞。

## 下一个阶段出口

1. 完成当前 [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244) 回环入口热修复的Draft PR、CI和独立审查，合并后绑定新的 exact `main` SHA。
2. 将合并后的 exact SHA 上传到 `/opt/shanhaiedu-production/releases/<sha>`，执行空库迁移、备份/恢复、服务健康检查和可回退发布。
3. 配置 IP HTTPS 入口并完成公网真实 API Playwright；不执行 #165 迁移、不调用任何真实 Provider。
4. 若正式部署继续延期，Issue #244 不应退回 `status:blocked`；应新建或更新独立Decision Issue，在PPT/PPTX、完整图片链、完整视频链和TTS中只选择一个教师纵向切片；不得直接恢复历史blocked实现。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件，再实时fetch并核验Issue、PR、分支与工作区。
2. R1与约6秒视频黄金切片已经完成；不得恢复#222、#230或按技术层严格串行的#223至#229旧执行方式。
3. #244是生产部署Decision；生产部署必须继续保留独立目录、Compose 项目、卷、网络、密钥和资源限制。
4. 普通CI使用确定性Fake。任何真实Provider、生产迁移、生产GC、密钥轮换或不可逆数据操作都必须遵守对应Issue的明确授权和停止条件。
