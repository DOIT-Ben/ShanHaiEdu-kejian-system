import type { LucideIcon } from "lucide-react";

export type StudioType = "image" | "video" | "presentation";
export type CreationStage =
  | "adopted"
  | "cancelled"
  | "draft"
  | "failed"
  | "paused"
  | "queued"
  | "ready"
  | "running"
  | "saved";

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

const modelSummaryLabels: Record<StudioType, Record<string, string>> = {
  image: { balanced: "课堂插画", detail: "细节增强", fast: "快速草图" },
  video: { balanced: "课堂视频", detail: "动作稳定", fast: "快速预览" },
  presentation: { balanced: "课堂课件", detail: "图文增强", fast: "快速排版" },
};

const styleSummaryLabels: Record<string, string> = {
  clay: "柔和黏土",
  illustration: "清透插画",
  paper: "纸艺微缩",
};

export function getCreationRatioLabel(ratio: string) {
  return ratio === "auto" ? "自动比例" : ratio;
}

export function getCreationSettingsSummary(type: StudioType, settings: CreationSettings) {
  const itemLabel = type === "image" ? "张" : type === "video" ? "段" : "套";
  const parts = [
    modelSummaryLabels[type][settings.model] ?? settings.model,
    getCreationRatioLabel(settings.ratio),
    styleSummaryLabels[settings.style] ?? settings.style,
    `${settings.candidateCount} ${itemLabel}`,
  ];
  if (type === "video") parts.push(`${settings.duration} 秒`);
  return parts.join(" · ");
}

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
