# PPT并行输入

PPT轨道只接受公共双课时Fixture投影出的以下exact事实：

- `project_id`；
- `lesson_id`；
- `approved_lesson_plan_version_id`及内容哈希；
- `material_parse_version_id`；
- `material_scope_artifact_version_id`；
- PPT画幅、页数和风格偏好。

PPT轨道不得自行查找“项目最新教案”，不得读取其他课时教案，也不得修改公共ContentRelease、Workflow Binding、active OpenAPI或生成客户端。