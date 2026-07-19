import { Play } from "lucide-react";
import { creationImageAssets, creationVideoShotAssets } from "@/assets/creation/catalog";
import type { StudioType } from "@/features/creation-studio/model";
import { PercentSlidePreview } from "@/features/home/components/PercentSlidePreview";

export function CreativeResultVisual({
  page,
  ratio = "1:1",
  type,
  variant = 0,
}: {
  page?: number;
  ratio?: string;
  type: StudioType;
  variant?: number;
}) {
  if (type === "presentation") return <PercentSlidePreview page={page} variant={variant} />;
  if (type === "video")
    return (
      <div className="group relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-player)]">
        <img
          alt="课堂导入视频作品画面"
          className="size-full object-cover transition-transform duration-[var(--sh-duration-slow)] group-hover:scale-[1.015]"
          decoding="async"
          src={creationVideoShotAssets[variant % creationVideoShotAssets.length]}
        />
        <div className="absolute inset-0 bg-[var(--sh-surface-inverse)]/10" />
        <div className="absolute inset-0 grid place-items-center">
          <span className="grid size-12 place-items-center rounded-full bg-[var(--sh-surface-elevated)]/94 text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-floating)] backdrop-blur-sm">
            <Play aria-hidden="true" className="ml-0.5 size-5 fill-current" />
          </span>
        </div>
      </div>
    );
  return (
    <div
      className={`group relative overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] ${ratio === "16:9" ? "aspect-video" : ratio === "4:3" ? "aspect-[4/3]" : "aspect-square"}`}
    >
      <img
        alt="小学数学课堂教学插画作品"
        className="size-full object-cover transition-transform duration-[var(--sh-duration-slow)] group-hover:scale-[1.015]"
        decoding="async"
        src={creationImageAssets[variant % creationImageAssets.length]}
      />
    </div>
  );
}
