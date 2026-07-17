import { Plus, Trash2, TriangleAlert } from "lucide-react";
import type { ContentField } from "@/entities/content";
import { contentFieldRegistry, type ContentFieldRendererProps } from "@/entities/registry";
import { Button, Checkbox, Input, Textarea } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

/**
 * 13 种内容字段渲染器（07 §5 内容定义驱动）。
 * 全部注册进 contentFieldRegistry：新增字段类型 = 注册新渲染器，页面零改动。
 */

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(asString) : [];
}

function TextField({ value, onChange, readOnly }: ContentFieldRendererProps) {
  return (
    <Input
      value={asString(value)}
      readOnly={readOnly}
      onChange={(e) => onChange(e.target.value)}
      className={cn(readOnly && "border-transparent bg-transparent px-0 shadow-none")}
    />
  );
}

function RichTextField({ value, onChange, readOnly, field }: ContentFieldRendererProps) {
  const text = asString(value);
  if (readOnly) {
    return <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{text || "—"}</p>;
  }
  return (
    <Textarea
      value={text}
      rows={Math.min(12, Math.max(3, text.split("\n").length + 1))}
      placeholder={`填写${field.label}`}
      onChange={(e) => onChange(e.target.value)}
      className="text-[15px] leading-7"
    />
  );
}

function NumberField({ value, onChange, readOnly }: ContentFieldRendererProps) {
  return (
    <Input
      type="number"
      value={typeof value === "number" ? value : ""}
      readOnly={readOnly}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      className="max-w-32"
    />
  );
}

function BooleanField({ value, onChange, readOnly, field }: ContentFieldRendererProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-ink">
      <Checkbox
        checked={value === true}
        disabled={readOnly}
        onCheckedChange={(checked) => onChange(checked === true)}
      />
      {field.label}
    </label>
  );
}

function ListField({ value, onChange, readOnly, field }: ContentFieldRendererProps) {
  const items = asStringArray(value);
  if (readOnly) {
    return items.length ? (
      <ul className="list-disc space-y-1 pl-5 text-[15px] leading-7 text-ink">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    ) : (
      <p className="text-sm text-ink-faint">—</p>
    );
  }
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={index} className="flex items-start gap-2">
          <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-ink-faint" aria-hidden />
          <Textarea
            value={item}
            rows={1}
            aria-label={`${field.label} 第 ${index + 1} 条`}
            onChange={(e) => onChange(items.map((v, i) => (i === index ? e.target.value : v)))}
            className="min-h-9 flex-1 py-1.5 text-[15px] leading-7"
          />
          <Button
            variant="ghost"
            size="sm"
            aria-label={`删除第 ${index + 1} 条`}
            onClick={() => onChange(items.filter((_, i) => i !== index))}
          >
            <Trash2 className="size-4 text-ink-muted" aria-hidden />
          </Button>
        </div>
      ))}
      <Button variant="ghost" size="sm" onClick={() => onChange([...items, ""])}>
        <Plus className="size-4" aria-hidden />
        添加一条
      </Button>
    </div>
  );
}

function TableField({ value, onChange, readOnly }: ContentFieldRendererProps) {
  const table = (value ?? {}) as { columns?: string[]; rows?: string[][] };
  const columns = table.columns ?? [];
  const rows = table.rows ?? [];
  return (
    <div className="overflow-x-auto rounded-md border border-line-subtle">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-surface-soft">
            {columns.map((col, i) => (
              <th key={i} className="border-b border-line-subtle px-3 py-2 text-left font-medium text-ink-strong">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-b border-line-subtle last:border-0">
              {columns.map((_, ci) => (
                <td key={ci} className="px-3 py-1.5 align-top">
                  {readOnly ? (
                    <span className="text-ink">{row[ci] ?? ""}</span>
                  ) : (
                    <Input
                      value={row[ci] ?? ""}
                      aria-label={`第 ${ri + 1} 行 ${columns[ci]}`}
                      onChange={(e) =>
                        onChange({
                          columns,
                          rows: rows.map((r, i) =>
                            i === ri ? r.map((cell, j) => (j === ci ? e.target.value : cell)) : r,
                          ),
                        })
                      }
                      className="h-8 border-transparent px-1.5"
                    />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!readOnly ? (
        <div className="flex gap-2 border-t border-line-subtle p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange({ columns, rows: [...rows, columns.map(() => "")] })}
          >
            <Plus className="size-4" aria-hidden />
            添加一行
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function ReferenceField({ value }: ContentFieldRendererProps) {
  const ref = (value ?? {}) as { label?: string; detail?: string };
  return (
    <p className="rounded-md bg-surface-soft px-3 py-2 text-sm text-ink">
      {ref.label ?? "引用内容"}
      {ref.detail ? <span className="text-ink-muted">（{ref.detail}）</span> : null}
    </p>
  );
}

function AssetField({ value, field }: ContentFieldRendererProps) {
  const asset = (value ?? {}) as { preview_url?: string; title?: string };
  return asset.preview_url ? (
    <figure className="overflow-hidden rounded-md border border-line-subtle">
      <img src={asset.preview_url} alt={asset.title ?? field.label} className="max-h-64 w-full object-contain" />
      {asset.title ? <figcaption className="px-3 py-2 text-xs text-ink-muted">{asset.title}</figcaption> : null}
    </figure>
  ) : (
    <p className="rounded-md border border-dashed border-line bg-surface-soft px-3 py-4 text-center text-sm text-ink-faint">
      素材位置：{field.label}（待填充）
    </p>
  );
}

function MathField({ value, onChange, readOnly }: ContentFieldRendererProps) {
  const math = typeof value === "string" ? { formula: value } : ((value ?? {}) as { formula?: string });
  if (readOnly) {
    return (
      <p className="rounded-md bg-surface-soft px-3 py-2 font-mono text-[15px] text-ink-strong">
        {math.formula ?? "—"}
      </p>
    );
  }
  return (
    <Input
      value={math.formula ?? ""}
      onChange={(e) => onChange({ ...math, formula: e.target.value })}
      className="font-mono"
      placeholder="例如：3/4 > 2/4"
    />
  );
}

function RubricField({ value, onChange, readOnly }: ContentFieldRendererProps) {
  const rubric = (value ?? {}) as { criteria?: { name: string; description?: string }[] };
  const criteria = rubric.criteria ?? [];
  return (
    <ul className="space-y-2">
      {criteria.map((criterion, index) => (
        <li key={index} className="rounded-md border border-line-subtle bg-surface-soft p-3">
          {readOnly ? (
            <>
              <p className="text-sm font-medium text-ink-strong">{criterion.name}</p>
              {criterion.description ? <p className="mt-0.5 text-sm text-ink-muted">{criterion.description}</p> : null}
            </>
          ) : (
            <div className="space-y-1.5">
              <Input
                value={criterion.name}
                aria-label={`评价条目 ${index + 1} 名称`}
                onChange={(e) =>
                  onChange({
                    criteria: criteria.map((c, i) => (i === index ? { ...c, name: e.target.value } : c)),
                  })
                }
              />
              <Textarea
                value={criterion.description ?? ""}
                rows={2}
                aria-label={`评价条目 ${index + 1} 说明`}
                onChange={(e) =>
                  onChange({
                    criteria: criteria.map((c, i) => (i === index ? { ...c, description: e.target.value } : c)),
                  })
                }
              />
            </div>
          )}
        </li>
      ))}
      {!readOnly ? (
        <Button variant="ghost" size="sm" onClick={() => onChange({ criteria: [...criteria, { name: "" }] })}>
          <Plus className="size-4" aria-hidden />
          添加评价条目
        </Button>
      ) : null}
    </ul>
  );
}

function TimelineField({ value, onChange, readOnly }: ContentFieldRendererProps) {
  const items = (Array.isArray(value) ? value : []) as { label?: string; minutes?: number; note?: string }[];
  return (
    <ol className="space-y-2">
      {items.map((item, index) => (
        <li key={index} className="flex items-start gap-3 rounded-md border border-line-subtle bg-surface-soft p-3">
          <span className="mt-1 flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-600">
            {index + 1}
          </span>
          {readOnly ? (
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-medium text-ink-strong">
                {item.label ?? `阶段 ${index + 1}`}
                {item.minutes != null ? <span className="ml-2 text-xs font-normal text-ink-muted">{item.minutes} 分钟</span> : null}
              </p>
              {item.note ? <p className="mt-0.5 text-ink-muted">{item.note}</p> : null}
            </div>
          ) : (
            <div className="grid min-w-0 flex-1 gap-1.5 sm:grid-cols-[1fr_88px]">
              <Input
                value={item.label ?? ""}
                aria-label={`阶段 ${index + 1} 名称`}
                onChange={(e) => onChange(items.map((v, i) => (i === index ? { ...v, label: e.target.value } : v)))}
              />
              <Input
                type="number"
                value={item.minutes ?? ""}
                aria-label={`阶段 ${index + 1} 分钟数`}
                onChange={(e) =>
                  onChange(
                    items.map((v, i) => (i === index ? { ...v, minutes: Number(e.target.value) || 0 } : v)),
                  )
                }
              />
              <Textarea
                value={item.note ?? ""}
                rows={1}
                aria-label={`阶段 ${index + 1} 说明`}
                className="sm:col-span-2"
                onChange={(e) => onChange(items.map((v, i) => (i === index ? { ...v, note: e.target.value } : v)))}
              />
            </div>
          )}
          {!readOnly ? (
            <Button
              variant="ghost"
              size="sm"
              aria-label={`删除阶段 ${index + 1}`}
              onClick={() => onChange(items.filter((_, i) => i !== index))}
            >
              <Trash2 className="size-4 text-ink-muted" aria-hidden />
            </Button>
          ) : null}
        </li>
      ))}
      {!readOnly ? (
        <Button variant="ghost" size="sm" onClick={() => onChange([...items, { label: "", minutes: 5 }])}>
          <Plus className="size-4" aria-hidden />
          添加阶段
        </Button>
      ) : null}
    </ol>
  );
}

/** 未知字段类型：显式提示升级，不静默丢内容（07 §7）。 */
export function UnknownFieldNotice({ field }: { field: ContentField }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-md border border-warning-200 bg-warning-50 p-3 text-sm"
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
      <span className="text-ink">
        「{field.label}」使用了当前版本暂不支持的内容类型（{field.type}）。内容已保留，请刷新或等待应用升级后编辑。
      </span>
    </div>
  );
}

let registered = false;

/** 注册全部内置字段渲染器（应用启动时调用一次）。 */
export function registerBuiltinFieldRenderers(): void {
  if (registered) return;
  registered = true;
  contentFieldRegistry.register("text", TextField);
  contentFieldRegistry.register("rich_text", RichTextField);
  contentFieldRegistry.register("number", NumberField);
  contentFieldRegistry.register("boolean", BooleanField);
  contentFieldRegistry.register("list", ListField);
  contentFieldRegistry.register("table", TableField);
  contentFieldRegistry.register("reference", ReferenceField);
  contentFieldRegistry.register("asset", AssetField);
  contentFieldRegistry.register("math", MathField);
  contentFieldRegistry.register("rubric", RubricField);
  contentFieldRegistry.register("timeline", TimelineField);
  // group / repeatable 为结构类型，由 ContentDefinitionRenderer 递归处理
}
