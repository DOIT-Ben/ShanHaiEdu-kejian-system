import { AlertTriangle, Plus, Trash2 } from "lucide-react";
import type { ComponentType } from "react";
import { useId, useState } from "react";
import type {
  ContentData,
  ContentDefinition,
  ContentField,
} from "@/features/content-definition/model";
import { IconButton } from "@/shared/ui/IconButton";

type FieldProps = {
  field: ContentField;
  value: unknown;
  onChange: (value: unknown) => void;
};

type FieldRendererProps = FieldProps & {
  inputId: string;
  labelId: string;
  descriptionId?: string;
};

function TextField({
  descriptionId,
  field,
  inputId,
  labelId,
  onChange,
  value,
}: FieldRendererProps) {
  const displayValue = typeof value === "string" || typeof value === "number" ? String(value) : "";
  return (
    <input
      aria-describedby={descriptionId}
      aria-labelledby={labelId}
      className="mt-3 min-h-11 w-full rounded-[var(--sh-radius-sm)] border border-transparent bg-[var(--sh-surface-soft)] px-3 text-base outline-none hover:border-[var(--sh-line-default)] focus:border-[var(--sh-brand-500)] focus:bg-[var(--sh-surface-elevated)]"
      disabled={!field.editable}
      id={inputId}
      onChange={(event) => onChange(event.target.value)}
      value={displayValue}
    />
  );
}

function RichTextField({
  descriptionId,
  field,
  inputId,
  labelId,
  onChange,
  value,
}: FieldRendererProps) {
  const displayValue = typeof value === "string" || typeof value === "number" ? String(value) : "";
  return (
    <textarea
      aria-describedby={descriptionId}
      aria-labelledby={labelId}
      className="mt-3 min-h-28 w-full resize-y rounded-[var(--sh-radius-sm)] border border-transparent bg-[var(--sh-surface-soft)] p-3 text-base leading-7 outline-none hover:border-[var(--sh-line-default)] focus:border-[var(--sh-brand-500)] focus:bg-[var(--sh-surface-elevated)]"
      disabled={!field.editable}
      id={inputId}
      onChange={(event) => onChange(event.target.value)}
      value={displayValue}
    />
  );
}

function ListField({ descriptionId, field, inputId, onChange, value }: FieldRendererProps) {
  const items = Array.isArray(value) ? value.map(String) : [];
  return (
    <div className="mt-3 space-y-2">
      {items.map((item, index) => (
        <div className="flex gap-2" key={`${field.field_key}-${String(index)}`}>
          <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-[var(--sh-brand-500)]" />
          <input
            aria-describedby={descriptionId}
            aria-label={`${field.label}第 ${String(index + 1)} 项`}
            className="min-h-10 min-w-0 flex-1 rounded-[var(--sh-radius-sm)] border border-transparent bg-[var(--sh-surface-soft)] px-3 outline-none focus:border-[var(--sh-brand-500)] focus:bg-[var(--sh-surface-elevated)]"
            disabled={!field.editable}
            id={`${inputId}-${String(index)}`}
            onChange={(event) =>
              onChange(
                items.map((current, itemIndex) =>
                  itemIndex === index ? event.target.value : current,
                ),
              )
            }
            value={item}
          />
          {field.editable ? (
            <IconButton
              label={`删除${field.label}第 ${String(index + 1)} 项`}
              onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}
            >
              <Trash2 aria-hidden="true" />
            </IconButton>
          ) : null}
        </div>
      ))}
      {field.editable ? (
        <button
          className="inline-flex min-h-9 items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 text-sm font-semibold text-[var(--sh-brand-600)] hover:bg-[var(--sh-brand-50)]"
          onClick={() => onChange([...items, ""])}
          type="button"
        >
          <Plus aria-hidden="true" className="size-4" />
          增加一项
        </button>
      ) : null}
    </div>
  );
}

function BooleanField({
  descriptionId,
  field,
  inputId,
  labelId,
  onChange,
  value,
}: FieldRendererProps) {
  return (
    <label className="mt-3 inline-flex items-center gap-2 text-sm">
      <input
        aria-describedby={descriptionId}
        aria-labelledby={labelId}
        checked={Boolean(value)}
        disabled={!field.editable}
        id={inputId}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
      是
    </label>
  );
}

function NumberField({
  descriptionId,
  field,
  inputId,
  labelId,
  onChange,
  value,
}: FieldRendererProps) {
  return (
    <input
      aria-describedby={descriptionId}
      aria-labelledby={labelId}
      className="mt-3 min-h-11 w-40 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3"
      disabled={!field.editable}
      id={inputId}
      onChange={(event) => onChange(event.target.valueAsNumber)}
      type="number"
      value={typeof value === "number" ? value : 0}
    />
  );
}

function GroupField({ field, onChange, value }: FieldRendererProps) {
  const groupValue = typeof value === "object" && value !== null ? (value as ContentData) : {};
  return (
    <div className="mt-3 space-y-3 border-l-2 border-[var(--sh-brand-100)] pl-4">
      {field.children?.map((child) => (
        <FieldBlock
          field={child}
          key={child.field_key}
          onChange={(next) => onChange({ ...groupValue, [child.field_key]: next })}
          value={groupValue[child.field_key]}
        />
      ))}
    </div>
  );
}

const fieldRegistry: Record<string, ComponentType<FieldRendererProps>> = {
  text: TextField,
  rich_text: RichTextField,
  number: NumberField,
  boolean: BooleanField,
  list: ListField,
  repeatable: ListField,
  timeline: ListField,
  table: RichTextField,
  group: GroupField,
  reference: TextField,
  asset: TextField,
  math: TextField,
  rubric: RichTextField,
};

function FieldBlock({ field, onChange, value }: FieldProps) {
  const generatedId = useId();
  const inputId = `content-field-${generatedId}`;
  const labelId = `${inputId}-label`;
  const descriptionId = field.description ? `${inputId}-description` : undefined;
  const Renderer = fieldRegistry[field.type];
  return (
    <section className="border-b border-[var(--sh-line-subtle)] py-6 last:border-0">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-lg font-semibold text-[var(--sh-ink-strong)]" id={labelId}>
          {field.label}
        </h3>
        {field.required ? (
          <span className="text-xs text-[var(--sh-danger)]">必填</span>
        ) : (
          <span className="text-xs text-[var(--sh-ink-faint)]">选填</span>
        )}
      </div>
      {field.description ? (
        <p className="mt-1 text-sm text-[var(--sh-ink-muted)]" id={descriptionId}>
          {field.description}
        </p>
      ) : null}
      {Renderer ? (
        <Renderer
          descriptionId={descriptionId}
          field={field}
          inputId={inputId}
          labelId={labelId}
          onChange={onChange}
          value={value}
        />
      ) : (
        <div className="mt-3 flex items-start gap-2 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-3 text-sm text-[var(--sh-danger)]">
          <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          此内容类型需要升级后才能编辑：{field.type}
        </div>
      )}
    </section>
  );
}

export function ContentDefinitionRenderer({
  data: initialData,
  definition,
  onChange,
}: {
  data: ContentData;
  definition: ContentDefinition;
  onChange?: (data: ContentData) => void;
}) {
  const [data, setData] = useState(initialData);
  const updateField = (key: string, value: unknown) => {
    const next = { ...data, [key]: value };
    setData(next);
    onChange?.(next);
  };
  return (
    <div>
      {definition.fields.map((field) => (
        <FieldBlock
          field={field}
          key={field.field_key}
          onChange={(value) => updateField(field.field_key, value)}
          value={data[field.field_key]}
        />
      ))}
    </div>
  );
}
