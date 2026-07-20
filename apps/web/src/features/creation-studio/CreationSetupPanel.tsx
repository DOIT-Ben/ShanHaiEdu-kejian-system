import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import type { CreationSettings, StudioType } from "@/features/creation-studio/model";

export function CreationSetupPanel({
  settings,
  type,
}: {
  settings: CreationSettings;
  type: StudioType;
}) {
  const visualWidth =
    type === "image"
      ? "w-[min(100%,360px)] md:w-[clamp(420px,46vw,560px)]"
      : "w-full max-w-[720px]";
  const workspaceWidth = type === "image" ? "max-w-[760px]" : "max-w-[1040px]";

  return (
    <section
      aria-label="作品展示区"
      className={`mx-auto flex h-full min-h-0 w-full ${workspaceWidth} items-center justify-center`}
      data-testid="creation-output-region"
    >
      <div
        className="flex h-full min-h-0 w-full items-center justify-center py-2"
        data-testid="creation-preview-panel"
      >
        <div className={`relative mx-auto ${visualWidth}`} data-testid="creation-main-visual">
          <div className="overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)]">
            <CreativeResultVisual ratio={settings.ratio} type={type} variant={0} />
          </div>
        </div>
      </div>
    </section>
  );
}
