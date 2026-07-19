import type { LucideIcon } from "lucide-react";

export type StudioType = "image" | "video" | "presentation";
export type CreationStage = "draft" | "running" | "ready" | "adopted" | "saved";

export function buildCreationResultId(type: StudioType, generation: number, candidate: number) {
  return `creation-${type}-generation-${String(generation)}-candidate-${String(candidate + 1)}`;
}

export function clampCreationCandidate(candidate: number, candidateCount: string | number) {
  const parsedCount =
    typeof candidateCount === "number" ? candidateCount : Number.parseInt(candidateCount, 10);
  const maximum = Math.max(0, (Number.isFinite(parsedCount) ? parsedCount : 1) - 1);
  return Math.min(Math.max(0, candidate), maximum);
}

export type CreationSettings = {
  candidateCount: string;
  duration: string;
  model: string;
  ratio: string;
  referenceName: string;
  style: string;
};

export const presentationPreviewPages = [
  "封面",
  "生活中的百分数",
  "百格图里的 37%",
  "百分数表示什么",
  "课堂回望",
] as const;

export type StudioConfig = {
  type: StudioType;
  path: string;
  title: string;
  entryTitle: string;
  description: string;
  primaryLabel: string;
  icon: LucideIcon;
};
