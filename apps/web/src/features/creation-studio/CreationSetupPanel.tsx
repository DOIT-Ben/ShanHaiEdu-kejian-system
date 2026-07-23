import { Image, Presentation, Video } from "lucide-react";
import type { CreationSettings, StudioType } from "@/features/creation-studio/model";

export function CreationSetupPanel({
  settings,
  type,
}: {
  settings: CreationSettings;
  type: StudioType;
}) {
  const Icon = type === "image" ? Image : type === "video" ? Video : Presentation;
  const label = type === "image" ? "图片创作" : type === "video" ? "视频创作" : "PPT 创作";
  return (
    <section
      aria-label="作品展示区"
      className="mx-auto flex h-full min-h-[240px] w-full max-w-[980px] items-start pt-[min(12vh,96px)]"
      data-testid="creation-output-region"
    >
      <div className="flex max-w-md items-center gap-3 text-[var(--sh-ink-muted)]">
        <span className="grid size-9 shrink-0 place-items-center rounded-full border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)]">
          <Icon aria-hidden="true" className="size-4" />
        </span>
        <p className="text-sm">
          {label} · {settings.ratio === "auto" ? "自动比例" : settings.ratio}
        </p>
      </div>
    </section>
  );
}
