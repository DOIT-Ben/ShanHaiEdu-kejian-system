import { FileText, Music2 } from "lucide-react";
import type { ComponentType, ReactNode } from "react";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { PercentSlidePreview } from "@/features/home/components/PercentSlidePreview";
import type { MockSavedResultPreview } from "@/shared/api/mocks/savedResults";

export type ArtifactType = "image" | "video" | "ppt_page" | "document" | "audio";

type ArtifactPreviewProps = {
  preview?: MockSavedResultPreview;
};

function PreviewFrame({
  children,
  preview,
  ratio,
}: {
  children: ReactNode;
  preview?: MockSavedResultPreview;
  ratio: string;
}) {
  const mediaClass =
    ratio === "1:1"
      ? "h-full max-w-full aspect-square"
      : ratio === "4:3"
        ? "h-full max-w-full aspect-[4/3]"
        : "w-full max-w-[284px] aspect-video";
  return (
    <div
      className="flex h-36 items-center justify-center overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] sm:h-40"
      data-slot="artifact-preview"
    >
      <div
        className={mediaClass}
        data-preview-candidate={preview?.candidate}
        data-preview-generation={preview?.generation}
        data-preview-ratio={ratio}
        data-slot="artifact-preview-media"
      >
        {children}
      </div>
    </div>
  );
}

const visualVariant = (preview?: MockSavedResultPreview) =>
  preview ? (preview.candidate + preview.generation) % 3 : 0;

const ImagePreview = ({ preview }: ArtifactPreviewProps) => (
  <PreviewFrame preview={preview} ratio={preview?.ratio ?? "1:1"}>
    <CreativeResultVisual
      loading="lazy"
      ratio={preview?.ratio}
      type="image"
      variant={visualVariant(preview)}
    />
  </PreviewFrame>
);
const VideoPreview = ({ preview }: ArtifactPreviewProps) => (
  <PreviewFrame preview={preview} ratio={preview?.ratio ?? "16:9"}>
    <CreativeResultVisual loading="lazy" type="video" variant={visualVariant(preview)} />
  </PreviewFrame>
);
const PptPreview = ({ preview }: ArtifactPreviewProps) => (
  <PreviewFrame preview={preview} ratio={preview?.ratio ?? "16:9"}>
    <PercentSlidePreview compact loading="lazy" variant={visualVariant(preview)} />
  </PreviewFrame>
);
const DocumentPreview = () => (
  <div
    className="grid h-36 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] sm:h-40"
    data-slot="artifact-preview"
  >
    <div className="text-center">
      <FileText aria-hidden="true" className="mx-auto size-10 text-[var(--sh-brand-600)]" />
      <p className="mt-2 text-xs font-semibold text-[var(--sh-ink-strong)]">教案文档</p>
    </div>
  </div>
);
const AudioPreview = () => (
  <div
    className="flex h-36 items-center justify-center gap-1 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] sm:h-40"
    data-slot="artifact-preview"
  >
    {[18, 34, 26, 44, 30, 20, 38, 24].map((height, index) => (
      <span className="w-1.5 rounded-full bg-[var(--sh-success)]" key={index} style={{ height }} />
    ))}
    <Music2 aria-hidden="true" className="ml-2 size-5 text-[var(--sh-success)]" />
  </div>
);

export const artifactPreviewRegistry: Record<ArtifactType, ComponentType<ArtifactPreviewProps>> = {
  image: ImagePreview,
  video: VideoPreview,
  ppt_page: PptPreview,
  document: DocumentPreview,
  audio: AudioPreview,
};
