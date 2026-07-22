import type { MockRuntimeState, MockRuntimeStore } from "@/shared/api/mockClient";
import { mockRuntime } from "@/shared/api/mockClient";
import { markDependentsStale } from "@/features/workbench/lib/invalidateDependents";

const dependentNodes = [
  ["master-script", "编写母版剧本"],
  ["rough-storyboard", "安排故事镜头"],
  ["video-style", "确定画面风格"],
  ["video-assets", "制作镜头图片"],
  ["fine-storyboard", "选择关键帧参考"],
  ["final-video", "生成课堂导入视频"],
] as const;

export function markIntroDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markDependentsStale(runtime, projectId, lessonId, dependentNodes, "课堂导入已改用新方案", store);
}
