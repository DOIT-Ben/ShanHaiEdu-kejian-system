import { registerNodeCanvas } from "./registry";
import { LessonPlanCanvas } from "./canvases/lesson-plan-canvas";
import { IntroDesignCanvas } from "./canvases/intro-design-canvas";
import { PptExportCanvas, PptOutlineCanvas, PptPagesCanvas } from "./canvases/ppt-canvases";
import { PptAssetsCanvas, PptPreviewCanvas } from "./canvases/ppt-assets-preview-canvases";
import { MasterImageCanvas, MasterScriptCanvas, VisualDirectionCanvas } from "./canvases/video-creative-canvases";
import {
  FineStoryboardCanvas,
  ImageAssetsCanvas,
  RoughStoryboardCanvas,
  ShotPromptsCanvas,
} from "./canvases/video-storyboard-canvases";
import { AudioSubtitleCanvas, ClipsCanvas, FinalCutCanvas } from "./canvases/video-production-canvases";
import { DeliveryCanvas } from "./canvases/delivery-canvas";

/** 注册全部 18 个节点画布（按 nodes.ts 的 rendererKey）。 */
export function registerAllCanvases(): void {
  registerNodeCanvas("lesson-plan", LessonPlanCanvas);
  registerNodeCanvas("intro-design", IntroDesignCanvas);
  registerNodeCanvas("ppt-outline", PptOutlineCanvas);
  registerNodeCanvas("ppt-pages", PptPagesCanvas);
  registerNodeCanvas("ppt-assets", PptAssetsCanvas);
  registerNodeCanvas("ppt-preview", PptPreviewCanvas);
  registerNodeCanvas("ppt-export", PptExportCanvas);
  registerNodeCanvas("video-master-script", MasterScriptCanvas);
  registerNodeCanvas("video-visual-direction", VisualDirectionCanvas);
  registerNodeCanvas("video-master-image", MasterImageCanvas);
  registerNodeCanvas("video-rough-storyboard", RoughStoryboardCanvas);
  registerNodeCanvas("video-image-assets", ImageAssetsCanvas);
  registerNodeCanvas("video-fine-storyboard", FineStoryboardCanvas);
  registerNodeCanvas("video-shot-prompts", ShotPromptsCanvas);
  registerNodeCanvas("video-clips", ClipsCanvas);
  registerNodeCanvas("video-audio-subtitle", AudioSubtitleCanvas);
  registerNodeCanvas("video-final-cut", FinalCutCanvas);
  registerNodeCanvas("delivery", DeliveryCanvas);
}

registerAllCanvases();
