# 完整视频并行输入

视频轨道只接受公共双课时Fixture投影出的exact `IntroSelection`：

- `project_id`；
- `lesson_id`；
- `intro_selection_id`；
- `intro_option_set_version_id`；
- `selected_option_key`；
- 选项快照哈希；
- 视频时长、画幅、语言、视觉风格和声音偏好。

禁止注入完整教案、教材正文、教材解析内容、PPT大纲或PPT页面。完整视频节点顺序只从 `contracts/full-chain-freeze.json` 的 `video` 分支读取，不在本目录复制第二份节点清单。视频内部必须实现母版剧本、粗分镜、视觉母图、四类图片资产、细分镜、shot候选、clip选择、真实TTS、字幕、时间线、最终MP4、课堂质量、技术质量和最终批准。
