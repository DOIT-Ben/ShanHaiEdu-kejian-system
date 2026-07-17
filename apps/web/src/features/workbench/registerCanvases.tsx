import { nodeRendererRegistry } from "@/entities/registry";
import { LessonPlanGenerateCanvas } from "./canvases/LessonPlanGenerateCanvas";
import { LessonPlanConfirmCanvas } from "./canvases/LessonPlanConfirmCanvas";
import { IntroOptionsCanvas } from "./canvases/IntroOptionsCanvas";
import { IntroSelectionCanvas } from "./canvases/IntroSelectionCanvas";
import { PptOutlineCanvas } from "./canvases/PptOutlineCanvas";
import { PptCoverCanvas } from "./canvases/PptCoverCanvas";
import { PptBodyCanvas } from "./canvases/PptBodyCanvas";
import { PptExportCanvas } from "./canvases/PptExportCanvas";
import { VideoDocumentCanvas } from "./canvases/VideoDocumentCanvas";
import { VideoStyleCanvas } from "./canvases/VideoStyleCanvas";
import { VideoAssetsCanvas } from "./canvases/VideoAssetsCanvas";
import { VideoClipsCanvas } from "./canvases/VideoClipsCanvas";
import { VideoComposeCanvas } from "./canvases/VideoComposeCanvas";

/** stepKey → 画布组件注册（06 §4 nodeRendererRegistry）。 */

function VideoScriptCanvas() {
  return (
    <VideoDocumentCanvas
      title="编写母版剧本"
      description="以选中的导入方案为唯一依据，写出完整的故事剧本。"
      notReadyHint="先选择一套导入方案，才能编写剧本。"
      runningLabel="正在编写母版剧本"
    />
  );
}

function VideoStoryboardCanvas() {
  return (
    <VideoDocumentCanvas
      title="安排故事镜头"
      description="把剧本拆成 10–15 秒的镜头，每个镜头一句话说清楚发生什么。"
      notReadyHint="剧本确认后，才能安排镜头。"
      runningLabel="正在安排故事镜头"
    />
  );
}

let registered = false;

export function registerWorkbenchCanvases(): void {
  if (registered) return;
  registered = true;
  nodeRendererRegistry.register("lesson-plan", LessonPlanGenerateCanvas);
  nodeRendererRegistry.register("lesson-plan-confirm", LessonPlanConfirmCanvas);
  nodeRendererRegistry.register("intro-options", IntroOptionsCanvas);
  nodeRendererRegistry.register("intro-selection", IntroSelectionCanvas);
  nodeRendererRegistry.register("ppt-outline", PptOutlineCanvas);
  nodeRendererRegistry.register("ppt-cover", PptCoverCanvas);
  nodeRendererRegistry.register("ppt-body", PptBodyCanvas);
  nodeRendererRegistry.register("ppt-export", PptExportCanvas);
  nodeRendererRegistry.register("video-script", VideoScriptCanvas);
  nodeRendererRegistry.register("video-storyboard", VideoStoryboardCanvas);
  nodeRendererRegistry.register("video-style", VideoStyleCanvas);
  nodeRendererRegistry.register("video-assets", VideoAssetsCanvas);
  nodeRendererRegistry.register("video-clips", VideoClipsCanvas);
  nodeRendererRegistry.register("video-compose", VideoComposeCanvas);
}
