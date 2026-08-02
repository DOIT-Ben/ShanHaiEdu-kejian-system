# 当前项目状态

当前阶段：阶段1后端基座和R1教师可见小学数学MVP已经进入`main`；公网IP HTTPS生产基础设施、回退、监控和认证流已经完成验证。正式发布Decision [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244)仍未关闭，因为其验收标准要求的公网十二部分教案完整教师流尚无通过证据；阶段5尚未开始。
> 最后核验：2026-08-03。
> 生产运行`main@8ec831072c643c7bc9b4cdcf2d240fd3f469bedd`，入口为`https://121.40.117.240`；首次开放范围仍是access code受控内测，#244保持`status:in-progress`。普通开发与CI继续只使用确定性Fake。

## 当前可演示成果

- 教师可从公网生产前端`/login`通过真实FastAPI和PostgreSQL建立Session；Session与CSRF可刷新恢复，登出后原Session和CSRF失效。
- 教师可以在本地真实API/PostgreSQL与确定性Fake Worker验收环境完成教材物理页范围确认、异步课时划分、十二部分教案生成与编辑、质量检查、exact ArtifactVersion批准、三类九套生成、唯一IntroSelection和刷新恢复；该证据不等于公网生产验收。
- 同一Project下多个LessonUnit按exact project/lesson/version隔离；跨租户、错误版本、重复生成和登出后写入均有PostgreSQL与真实API浏览器负测。
- 教师可以从exact已采用IntroSelection和同课时正式关键帧启动约6秒视频生成，查看进度或失败原因，播放、exact采用并刷新恢复LessonUnit视频槽位。
- 真实文本黄金项目已通过`NewAPI -> deepseek`受控验收；真实视频黄金项目只提交一次NewAPI请求且零重试，生成6.041667秒H.264 MP4并完成文件、血缘、采用和刷新恢复校验。
- 生产发布具备exact SHA镜像来源、IP TLS、独立Compose/卷/Secret、PostgreSQL与MinIO备份恢复、五分钟健康监控及应用回退；公网真实Chrome已验证登录、项目创建、刷新恢复和登出负测。

## 已完成

- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)及R1纵向结果已经关闭；#231、#234、#235和#241分别交付十二部分教案、教材范围与课时划分、三类九套和受控真实文本Provider验收。
- [Issue #205](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/205)由[PR #247](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/247)Squash Merge并关闭，完成约6秒真实视频教师黄金切片。
- [Issue #248](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/248)由[PR #252](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/252)Squash Merge并关闭，完成staging校验、幂等晋升、PostgreSQL final-only血缘和保守GC。
- [Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)定义的五个教师可见R1结果、纵向合并门禁和exact base/head审查要求已经落实；历史Draft PR #222与#230均已关闭，不再是当前实现入口。

## 当前工作

- [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244)当前为`status:in-progress`。PR #254 至 #268已经交付生产拓扑、来源校验、IP HTTPS入口、健康检查、发布互斥和exact环境切换；生产`current`、环境文件与运行容器均绑定当前exact SHA，应用回退演练通过。
- #244的Alembic、内容与身份初始化、PostgreSQL/MinIO pre/post备份与独立恢复、六容器健康、HTTP到HTTPS跳转、IP证书、monitor和公网认证流均已复验；详细脱敏证据保存在Issue。
- #244验收标准第5条剩余公网十二部分教案教师流：打开真实LessonUnit、启动异步生成、查看进度、编辑保存、质量检查、批准exact ArtifactVersion、刷新恢复，以及登出后写入失败。现有公网证据只覆盖认证流；2026-07-28的完整教案浏览器证据来自本地确定性Fake环境，不能替代公网生产验收。
- 当前收口变更只修正现行状态与治理断言；在上述公网验收完成或Issue正式修改验收标准前，不得使用`Closes #244`或关闭Issue。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)和[Issue #237](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/237)为`status:ready`技术债，不代表下一产品里程碑，也不阻塞当前MVP或生产运行。
- [Issue #165](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/165)仍以`status:blocked`独立跟踪视频relay迁移；它不是生产应用发布或下一产品切片的默认入口。

## 当前阻塞

- [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244)的公网十二部分教案验收被生产模型路由边界阻塞：首次发布未配置文本Provider，生产Worker遇到生成任务会得到不可用路由；生产Compose的internal网络也按批准合同禁止应用容器主动访问公网。测试专用Fake Worker只允许`SHANHAI_ENVIRONMENT=test`，不得接入生产数据冒充正式运行。
- 生产与其他服务共享同一ECS的资源争用和共同故障域风险已在#244明确接受。一次高负载窗口中的Redis readiness超时已由下一轮timer自然恢复；生产容器无OOM或重启，后续继续由五分钟monitor暴露同类风险。
- 阶段5产品方向尚未决定且不得先于#244收口。PPT/PPTX、完整图片链、完整视频链和TTS不得并行铺开，也不得直接恢复历史`status:blocked`实现。

## 下一个阶段出口

1. 在 [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244) 明确选择并批准唯一收口路径：为生产配置受控文本Provider、Secret和最小出网边界后执行公网十二部分教案完整教师流，或正式修改与当前无Provider首次发布相冲突的验收标准；不得静默用测试Fake替代。
2. 按批准路径完成公网十二部分教案验收、脱敏证据、required CI和独立reviewer final exact base/head复核，再关闭#244。
3. #244关闭后创建并批准一个阶段5 Decision Issue，只选择PPT/PPTX、完整图片链、完整视频链或TTS中的一条最小教师纵向切片；先写失败测试，再复用现有Session/CSRF、项目、节点运行、任务、资产、采用、对象存储、OpenAPI和生成客户端。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件，再实时fetch并核验Issue、PR、分支、生产SHA与工作区。
2. R1和约6秒视频黄金切片已经完成；#244只完成了生产基础设施与公网认证部分，完整教案公网验收仍待决策和执行。不得恢复#222、#230或按技术层严格串行的#223至#229旧执行方式。
3. 生产部署继续遵循`infra/prod/README.md`，保留独立目录、Compose项目、卷、网络、Secret、备份、监控和可回退exact SHA；不得把共享ECS描述为物理隔离。
4. 测试专用确定性Fake不能接入生产；真实Provider、生产网络或Secret边界变化必须先由#244记录明确决定。新产品方向必须回到阶段5 Decision Issue；历史blocked Issue只能作为只读输入，不能自行授予实施范围。
