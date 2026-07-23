import type { CreationAdvancedSettings } from "@/features/creation-studio/CreationAdvancedPanel";
import type { CreationSettings, StudioType } from "@/features/creation-studio/model";

export const studioTypeByPath: Record<string, StudioType> = {
  images: "image",
  presentations: "presentation",
  videos: "video",
};

export const initialCreationSettings: CreationSettings = {
  candidateCount: "3",
  duration: "10",
  model: "balanced",
  ratio: "16:9",
  referenceName: "",
  style: "illustration",
};

export const initialAdvancedSettings: CreationAdvancedSettings = {
  composition: "主体清晰，留出课堂讲解空间",
  negativePrompt: "水印、乱码、无关装饰",
  referenceStrength: 50,
};

export type GenerationIntent = {
  batchKey: string;
  fingerprint: string;
  generateKey: string;
  promptKey: string;
};

export class CreationItemUnavailableError extends Error {}

export function generationProfile(model: string) {
  if (model === "detail") return "quality" as const;
  if (model === "fast") return "speed" as const;
  return "balanced" as const;
}
