import { useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { ExternalLink, ImageIcon, Plus, X } from "lucide-react";
import type { NodeWorkspace } from "@/shared/api/types";
import { useAssetDetail } from "@/features/assets";
import { getNodeDef } from "@/entities/workflow/nodes";
import type { NodeStatus } from "@/shared/lib/status";
import {
  Button,
  Input,
  NodeStatusBadge,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
  Textarea,
} from "@/shared/ui";
import { AssetPicker } from "@/widgets";

const inputFieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  type: z.enum(["select", "number", "textarea", "text", "switch"]).default("text"),
  options: z.array(z.string()).optional(),
  placeholder: z.string().optional(),
});
const inputSchemaSchema = z.object({ fields: z.array(inputFieldSchema).default([]) });

/** 输入页签：结构化输入字段 + 上游引用。保存后重新组装提示词。 */
export function InputsTab({
  workspace,
  saving,
  onSave,
  onOpenUpstream,
}: {
  workspace: NodeWorkspace;
  saving?: boolean;
  onSave: (inputValues: Record<string, unknown>) => void;
  onOpenUpstream: (nodeKey: string) => void;
}) {
  const parsed = useMemo(() => inputSchemaSchema.safeParse(workspace.input_schema), [workspace.input_schema]);
  const fields = parsed.success ? parsed.data.fields : [];
  const [values, setValues] = useState<Record<string, unknown>>(workspace.input_values ?? {});
  useEffect(() => {
    setValues(workspace.input_values ?? {});
  }, [workspace.input_values]);

  const dirty = JSON.stringify(values) !== JSON.stringify(workspace.input_values ?? {});

  return (
    <div className="space-y-4">
      {fields.length === 0 ? (
        <p className="rounded-control bg-surface-2 px-3 py-3 text-sm text-ink-2">本步骤没有可配置的输入项。</p>
      ) : (
        <div className="space-y-3">
          {fields.map((field) => (
            <div key={field.key} className="space-y-1">
              <label className="text-xs font-medium text-ink-2" htmlFor={`input-${field.key}`}>
                {field.label}
              </label>
              {field.type === "select" ? (
                <Select value={String(values[field.key] ?? "")} onValueChange={(value) => setValues((prev) => ({ ...prev, [field.key]: value }))}>
                  <SelectTrigger id={`input-${field.key}`}>
                    <SelectValue placeholder="请选择" />
                  </SelectTrigger>
                  <SelectContent>
                    {(field.options ?? []).map((option) => (
                      <SelectItem key={option} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : field.type === "number" ? (
                <Input
                  id={`input-${field.key}`}
                  type="number"
                  value={String(values[field.key] ?? "")}
                  onChange={(event) => setValues((prev) => ({ ...prev, [field.key]: Number(event.target.value) }))}
                />
              ) : field.type === "switch" ? (
                <div>
                  <Switch
                    id={`input-${field.key}`}
                    checked={Boolean(values[field.key])}
                    onCheckedChange={(checked) => setValues((prev) => ({ ...prev, [field.key]: checked }))}
                  />
                </div>
              ) : (
                <Textarea
                  id={`input-${field.key}`}
                  rows={2}
                  placeholder={field.placeholder}
                  value={String(values[field.key] ?? "")}
                  onChange={(event) => setValues((prev) => ({ ...prev, [field.key]: event.target.value }))}
                />
              )}
            </div>
          ))}
          {dirty ? (
            <Button size="sm" className="w-full" loading={saving} onClick={() => onSave(values)}>
              保存输入并更新提示词
            </Button>
          ) : null}
        </div>
      )}

      <section>
        <h4 className="mb-1.5 text-xs font-semibold text-ink-muted">上游引用</h4>
        {(workspace.upstream_references ?? []).length === 0 ? (
          <p className="text-xs text-ink-muted">本步骤不依赖上游产物。</p>
        ) : (
          <ul className="space-y-1.5">
            {(workspace.upstream_references ?? []).map((reference) => (
              <li key={reference.node_key}>
                <button
                  type="button"
                  onClick={() => onOpenUpstream(reference.node_key)}
                  className="flex w-full items-center gap-2 rounded-control border border-line px-3 py-2 text-left transition-colors hover:bg-surface-hover"
                >
                  <span className="min-w-0 flex-1 truncate text-sm text-ink-1">{reference.title}</span>
                  {reference.stale ? <span className="text-xs text-warning">已更新</span> : null}
                  {reference.version_number ? <span className="text-xs text-ink-muted">V{reference.version_number}</span> : null}
                  <NodeStatusBadge status={reference.status as NodeStatus} />
                  <ExternalLink className="size-3.5 shrink-0 text-ink-muted" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function SelectedAssetRow({ assetId, onRemove }: { assetId: string; onRemove: () => void }) {
  const detail = useAssetDetail(assetId);
  const asset = detail.data?.asset;
  return (
    <li className="flex items-center gap-2 rounded-control border border-line px-2.5 py-2">
      {asset?.thumbnail_url ? (
        <img src={asset.thumbnail_url} alt="" className="size-9 rounded-control object-cover" />
      ) : (
        <span className="flex size-9 items-center justify-center rounded-control bg-surface-2 text-ink-muted">
          <ImageIcon className="size-4" aria-hidden />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-ink-1">{asset?.name ?? assetId}</p>
        <p className="text-[10px] text-ink-muted">
          {asset?.source_node_key ? (getNodeDef(asset.source_node_key)?.title ?? asset.source_node_key) : ""}
        </p>
      </div>
      <Button size="sm" variant="ghost" onClick={onRemove} aria-label="移除该资产">
        <X className="size-3.5" aria-hidden />
      </Button>
    </li>
  );
}

/** 资产页签：本节点选用的参考/输入资产，可从资产库添加（图片一键入视频节点）。 */
export function AssetsTab({
  workspace,
  projectId,
  saving,
  onChangeSelected,
}: {
  workspace: NodeWorkspace;
  projectId: string;
  saving?: boolean;
  onChangeSelected: (assetIds: string[]) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const selected = workspace.selected_asset_ids ?? [];
  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted">选用的资产会作为本步骤生成的参考输入。</p>
      {selected.length === 0 ? (
        <p className="rounded-control bg-surface-2 px-3 py-3 text-sm text-ink-2">尚未选用资产。</p>
      ) : (
        <ul className="space-y-1.5">
          {selected.map((assetId) => (
            <SelectedAssetRow key={assetId} assetId={assetId} onRemove={() => onChangeSelected(selected.filter((id) => id !== assetId))} />
          ))}
        </ul>
      )}
      <Button size="sm" variant="secondary" className="w-full" onClick={() => setPickerOpen(true)} loading={saving}>
        <Plus className="size-4" aria-hidden />
        从资产库选择
      </Button>
      <AssetPicker
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        projectId={projectId}
        title="选择参考资产"
        confirmLabel="加入本步骤"
        onConfirm={(asset) => {
          if (!selected.includes(asset.asset_id)) onChangeSelected([...selected, asset.asset_id]);
        }}
      />
    </div>
  );
}
