<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->

# 内置生成提示词与模板说明

本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。

- **Owner：** 工作流与内容包维护者。
- **Audience：** 产品负责人、内容管理员、后端/前端开发与测试人员。
- **机器权威源：** `workflow/builtin/primary_math_courseware/generation-source.json` 和黄金 Fixture；本目录不是第二套可手改事实。
- **更新规则：** 修改权威源后运行渲染脚本；测试会逐字检查生成结果。
- **替换/删除规则：** 内容包退役或生成方式变化时，由同一 PR 替换入口并删除本目录。

当前内容包：`shanhai.primary_math.courseware@1.1.0`，共 22 个模型节点。

## 怎么看

每个节点都按同一顺序说明：教师填写 → 系统自动带入 → 实际四层提示词 → 结构化输出字段 → 教师可读投影模板。

- **Task：** 教师可以在创作台修改的业务指令。
- **Role / Method / Quality Gate：** 平台固定，教师不能用改 Prompt 的方式绕过结构和教学边界。
- **Context：** 上游批准快照，不要求教师复制粘贴。
- **输出字段：** 系统内部结构；教师看到的是投影后的教案、PPT 设计稿或视频生产包。

## 分册

1. [课时划分与十二部分教案](LESSON.md)
2. [课程驱动的三类九套导入方案](INTRO.md)
3. [PPT 内容分析、大纲与逐页设计](PPT_DESIGN.md)
4. [PPT 封面与正文图片](PPT_IMAGES.md)
5. [视频剧本、粗分镜与视觉母图](VIDEO_SCRIPT_AND_STYLE.md)
6. [视频四类图片资产](VIDEO_ASSETS.md)
7. [视频细分镜与逐镜头生成](VIDEO_SHOTS.md)
8. [音频、TTS 与课堂质量验收](AUDIO_AND_QUALITY.md)
9. [“1～5的认识”黄金测试示例](GOLDEN_CASE.md)

## 重新生成与检查

```powershell
uv run python scripts\render_builtin_generation_guide.py
uv run python scripts\render_builtin_generation_guide.py --check
uv run pytest tests\contract\test_generation_guide.py -q
```
