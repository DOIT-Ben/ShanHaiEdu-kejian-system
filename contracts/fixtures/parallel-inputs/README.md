# 并行开发输入

本目录只保存各并行轨道从冻结合同确定性投影出的开发输入，不保存真实Provider响应、媒体文件、密钥或运行时数据库事实。

- `mainline/`：教材、课时划分、教案和三类九套开发输入；
- `ppt/`：只从exact已批准教案和教材证据投影；
- `video/`：只从exact `IntroSelection`不可变快照投影，禁止注入完整教案、教材正文或PPT；

公共双课时来源是 `contracts/fixtures/contract-freeze/primary-math-two-lessons.json`。轨道可以新增从该文件确定性生成的输入，但不得手工创建语义不同的第二套DTO。