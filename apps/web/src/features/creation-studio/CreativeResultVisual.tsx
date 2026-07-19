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
      <div
        aria-label="课堂导入关键帧示意，视频尚未生成"
        className="group relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-player)]"
        role="img"
      >
        <img
          alt=""
          aria-hidden="true"
          className="size-full object-cover transition-transform duration-[var(--sh-duration-slow)] group-hover:scale-[1.015]"
          decoding="async"
          src={creationVideoShotAssets[variant % creationVideoShotAssets.length]}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[var(--sh-surface-inverse)]/36 via-transparent to-transparent" />
        <span className="absolute bottom-2 left-2 rounded-full bg-[var(--sh-surface-elevated)]/92 px-2 py-1 text-[10px] font-semibold text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-card)] backdrop-blur-sm">
          关键帧示意 · 视频尚未生成
        </span>
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
