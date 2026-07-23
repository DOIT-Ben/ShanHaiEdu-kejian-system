# 主链并行输入

主链轨道负责教材、课时划分、十二部分教案、三类九套和唯一选择的真实运行时接线。它只消费冻结的公共节点合同，并为下游形成：

- exact已批准 `lesson_plan` ArtifactVersion，供PPT使用；
- exact可消费 `IntroSelection`不可变快照，供完整视频使用。

主链不得改变PPT或视频内部节点，不得直接修改active OpenAPI、生成客户端、公共Workflow Binding或Artifact/Job语义；需要变更时先提交Contract Change。