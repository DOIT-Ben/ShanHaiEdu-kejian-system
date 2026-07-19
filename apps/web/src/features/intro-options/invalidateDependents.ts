import type { MockRuntimeState, MockRuntimeStore } from "@/shared/api/mocks/runtime";
import { mockRuntime } from "@/shared/api/mocks/runtime";
import { markDependentsStale } from "@/features/workbench/lib/invalidateDependents";

const dependentNodes = [
  ["master-script", "编写母版剧本"],
  ["rough-storyboard", "安排故事镜头"],
  ["video-style", "确定画面风格"],
  ["video-assets", "制作镜头图片"],
  ["fine-storyboard", "制作视频片段"],
  ["final-video", "合成完整视频"],
] as const;

export function markIntroDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markDependentsStale(runtime, projectId, lessonId, dependentNodes, "课堂导入已改用新方案", store);
}
