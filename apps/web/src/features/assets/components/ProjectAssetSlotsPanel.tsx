import type { BindAssetRequest, ProjectAssetSlotDto } from "@/features/assets/api/assetsApi";
import { Button } from "@/shared/ui/Button";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export type SelectedProjectAsset = {
  fileAssetVersionId: string;
  label?: string;
  sourceArtifactVersionId?: string;
};

type ProjectAssetSlotsPanelProps = {
  busyId?: string;
  errorMessage?: string;
  onBind: (slotId: string, input: BindAssetRequest) => void;
  onUnbind: (bindingId: string) => void;
  selectedAsset?: SelectedProjectAsset;
  slots: readonly ProjectAssetSlotDto[];
  writeDisabled?: boolean;
};

const assetTypeLabels: Record<string, string> = {
  audio: "音频",
  document: "文档",
  image: "图片",
  presentation: "课件",
  video: "视频",
};

export function ProjectAssetSlotsPanel({
  busyId,
  errorMessage,
  onBind,
  onUnbind,
  selectedAsset,
  slots,
  writeDisabled = false,
}: ProjectAssetSlotsPanelProps) {
  if (!slots.length) {
    return (
      <p className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 text-sm text-[var(--sh-ink-muted)]">
        当前项目没有素材位置。
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {errorMessage ? (
        <p
          className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-3 text-sm text-[var(--sh-danger)]"
          role="alert"
        >
          {errorMessage}
        </p>
      ) : null}
      {selectedAsset ? (
        <p
          className="break-words rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] p-3 text-sm text-[var(--sh-brand-700)]"
          role="status"
        >
          已选择{selectedAsset.label || "一个素材"}，请选择要放入的位置。
        </p>
      ) : null}
      {slots.map((slot, slotIndex) => {
        const typeLabel = assetTypeLabels[slot.asset_type] ?? "素材";
        const slotTitle = `${typeLabel}位置 ${String(slotIndex + 1)}`;
        return (
          <article
            className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5"
            key={slot.id}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold text-[var(--sh-ink-strong)]">{slotTitle}</h2>
                <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                  {slot.cardinality === "one" ? "可放入一个素材" : "可放入多个素材"}
                  {slot.required ? " · 必需" : " · 可选"}
                </p>
              </div>
              <StatusBadge
                label={slot.status === "satisfied" ? "已有素材" : "尚未添加"}
                status={slot.status === "satisfied" ? "approved" : "not_ready"}
              />
            </div>

            {selectedAsset ? (
              <Button
                className="mt-4"
                disabled={writeDisabled || busyId === slot.id}
                onClick={() =>
                  onBind(slot.id, {
                    file_asset_version_id: selectedAsset.fileAssetVersionId,
                    position: null,
                    replace_mode: slot.cardinality === "one" ? "replace_active" : "append",
                    source_artifact_version_id: selectedAsset.sourceArtifactVersionId ?? null,
                  })
                }
                size="sm"
              >
                放入{slotTitle}
              </Button>
            ) : null}

            {slot.active_bindings.length ? (
              <div className="mt-5 border-t border-[var(--sh-line-subtle)] pt-4">
                <h3 className="text-sm font-semibold text-[var(--sh-ink-strong)]">当前素材</h3>
                <ul className="mt-2 grid gap-2">
                  {slot.active_bindings.map((binding, bindingIndex) => (
                    <li
                      className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-3 py-2"
                      key={binding.id}
                    >
                      <span className="text-sm text-[var(--sh-ink-muted)]">
                        {typeLabel}素材 {String(bindingIndex + 1)}
                      </span>
                      <Button
                        disabled={writeDisabled || busyId === binding.id}
                        onClick={() => onUnbind(binding.id)}
                        size="sm"
                        variant="quiet"
                      >
                        移除{typeLabel}素材 {String(bindingIndex + 1)}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>
        );
      })}
      {!selectedAsset ? (
        <p className="text-sm leading-6 text-[var(--sh-ink-muted)]">
          要添加新素材，请先从已生成或已上传的素材进入项目绑定流程。
        </p>
      ) : null}
    </div>
  );
}
