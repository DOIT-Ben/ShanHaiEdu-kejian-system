# 当前项目状态

当前阶段：阶段1后端基座、R1教师可见小学数学MVP和公网IP HTTPS生产验收已经完成；正式发布Decision [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244)要求的公网十二部分教案完整教师流已经通过并关闭。阶段5产品实现尚未开始。
> 最后核验：2026-08-04。
> 生产运行`main@23d6db80951348fb74057401e3aec524038b7ca8`，入口为`https://121.40.117.240`；首次开放范围仍是access code受控内测。普通开发与CI继续只使用确定性Fake，真实Provider只用于Issue明确批准的里程碑验收。

## 当前可演示成果

- 教师可从公网生产前端`/login`通过真实FastAPI和PostgreSQL建立Session；Session与CSRF可刷新恢复，登出后原Session和CSRF失效。
- 教师已在公网真实FastAPI、PostgreSQL、Worker、SSE和受控真实文本Provider上完成十二部分教案的单次异步生成、编辑保存、质量检查、exact ArtifactVersion批准和刷新恢复；登出后写请求返回401。
- 同一Project下多个LessonUnit按exact project/lesson/version隔离；跨租户、错误版本、重复生成和登出后写入均有PostgreSQL与真实API浏览器负测。
- 教师可以从exact已采用IntroSelection和同课时正式关键帧启动约6秒视频生成，查看进度或失败原因，播放、exact采用并刷新恢复LessonUnit视频槽位。
- 真实文本黄金项目和公网生产十二部分教案流均已通过`NewAPI -> deepseek`受控验收；公网成功请求只有一个Attempt且没有自动重试。真实视频黄金项目只提交一次NewAPI请求且零重试，生成6.041667秒H.264 MP4并完成文件、血缘、采用和刷新恢复校验。
- 生产发布具备exact SHA镜像来源、IP TLS、独立Compose/卷/Secret、PostgreSQL与MinIO备份恢复、五分钟健康监控及应用回退；调用后公网verify、monitor和六容器健康复验通过，容器重启数均为0。

## 已完成

- [Issue #11](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/11)及R1纵向结果已经关闭；#231、#234、#235和#241分别交付十二部分教案、教材范围与课时划分、三类九套和受控真实文本Provider验收。
- [Issue #205](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/205)由[PR #247](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/247)Squash Merge并关闭，完成约6秒真实视频教师黄金切片。
- [Issue #248](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/248)由[PR #252](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/252)Squash Merge并关闭，完成staging校验、幂等晋升、PostgreSQL final-only血缘和保守GC。
- [Decision #210](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/210)定义的五个教师可见R1结果、纵向合并门禁和exact base/head审查要求已经落实；历史Draft PR #222与#230均已关闭，不再是当前实现入口。
- [Issue #244](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/244)完成exact生产发布、备份恢复、监控、应用回退和公网真实教师流；[PR #275](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/pull/275)修正教师编辑版本的课时划分血缘继承后，最终生产验收确认一条失败事实和一条单Attempt成功事实保持不可变，批准、刷新恢复和登出负测均通过。

## 当前工作

- R1与正式生产发布已经收口。下一项产品工作必须先由一个新的阶段5 Decision Issue只选择PPT/PPTX、完整图片链、完整视频链或TTS中的一条最小教师纵向切片；当前没有已获准实施的阶段5功能分支。
- [Issue #233](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/233)和[Issue #237](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/237)为`status:ready`技术债，不代表下一产品里程碑，也不阻塞当前MVP或生产运行。
- [Issue #165](https://github.com/DOIT-Ben/ShanHaiEdu-kejian-system/issues/165)仍以`status:blocked`独立跟踪视频relay迁移；它不是生产应用发布或下一产品切片的默认入口。

## 当前阻塞

- 当前没有阻塞R1教师闭环或公网受控内测的已知P0/P1问题。
- 生产与其他服务共享同一ECS的资源争用和共同故障域风险已在#244明确接受；继续由五分钟monitor暴露容器、数据库、队列、磁盘、证书和公网入口异常，不得把该部署描述为物理隔离。
- 阶段5产品方向尚未决定。PPT/PPTX、完整图片链、完整视频链和TTS不得并行铺开，也不得直接恢复历史`status:blocked`实现；方向缺口由新的Decision Issue解决，不影响当前生产运行。

## 下一个阶段出口

1. 创建并批准一个阶段5 Decision Issue，只选择PPT/PPTX、完整图片链、完整视频链或TTS中的一条最小教师纵向切片；历史blocked Issue只作为只读输入。
2. 在Decision中固定教师可见出口、范围、非范围、真实验收预算、风险和回退，再创建唯一实现Issue、短分支与Draft PR。
3. 实现必须先写失败测试，复用现有Session/CSRF、项目、LessonUnit、NodeRun、GenerationJob、Worker、Model Gateway、ArtifactVersion、FileAssetVersion、对象存储、采用、active OpenAPI和生成客户端；不得建立第二套状态机或DTO。
4. 按风险完成required CI和真实教师流，再由未参与实现的独立reviewer绑定final exact base/head；P0/P1清零且P2/P3修复或明确接受后才进入下一门禁。

## 接手提示

1. 先读`README.md`、`AGENTS.md`、`docs/governance/项目记忆与接手索引.md`和本文件，再实时fetch并核验Issue、PR、分支、生产SHA与工作区。
2. R1、约6秒视频黄金切片和#244公网十二部分教案完整教师流已经完成；不得恢复#222、#230或按技术层严格串行的#223至#229旧执行方式。
3. 生产部署继续遵循`infra/prod/README.md`，当前exact运行SHA为`23d6db80951348fb74057401e3aec524038b7ca8`；保留独立目录、Compose项目、卷、网络、Secret、备份、监控和可回退版本，不得把共享ECS描述为物理隔离。
4. 测试专用确定性Fake不能接入生产；后续真实Provider调用、生产网络或Secret边界变化必须由当前Issue重新明确批准。新产品方向必须回到阶段5 Decision Issue；历史blocked Issue只能作为只读输入，不能自行授予实施范围。
