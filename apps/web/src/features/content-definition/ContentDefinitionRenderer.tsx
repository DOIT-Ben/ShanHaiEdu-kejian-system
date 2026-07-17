import { useMemo } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { ContentDefinition, ContentField } from "@/entities/content";
import { contentFieldRegistry } from "@/entities/registry";
import type { ValidationIssue } from "@/shared/api";
import { Button } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { registerBuiltinFieldRenderers, UnknownFieldNotice } from "./fields";

registerBuiltinFieldRenderers();

/**
 * 内容定义渲染器（06 §4 registry 架构）：
 * 教案等作品的部分结构完全由 content definition 数据驱动——
 * 十二部分教案与五部分简案用同一套代码渲染，前端零硬编码。
 */
export function ContentDefinitionRenderer({
  definition,
  value,
  onChange,
  readOnly = false,
  issues = [],
}: {
  definition: ContentDefinition;
  value: Record<string, unknown>;
  onChange?: (next: Record<string, unknown>) => void;
  readOnly?: boolean;
  issues?: ValidationIssue[];
}) {
  const issuesByPath = useMemo(() => {
    const map = new Map<string, ValidationIssue[]>();
    for (const issue of issues) {
      const path = issue.field_path ?? "";
      const list = map.get(path) ?? [];
      list.push(issue);
      map.set(path, list);
    }
    return map;
  }, [issues]);

  const update = (fieldKey: string, fieldValue: unknown) => {
    onChange?.({ ...value, [fieldKey]: fieldValue });
  };

  return (
    <div className="space-y-8">
      {definition.fields.map((field, index) => (
        <FieldBlock
          key={field.field_key}
          field={field}
          index={index}
          path={field.field_key}
          value={value[field.field_key]}
          onChange={(v) => update(field.field_key, v)}
          readOnly={readOnly || field.editable === false}
          issuesByPath={issuesByPath}
        />
      ))}
    </div>
  );
}

function FieldBlock({
  field,
  index,
  path,
  value,
  onChange,
  readOnly,
  issuesByPath,
  headingLevel = 2,
}: {
  field: ContentField;
  index: number;
  path: string;
  value: unknown;
  onChange: (value: unknown) => void;
  readOnly: boolean;
  issuesByPath: Map<string, ValidationIssue[]>;
  headingLevel?: 2 | 3;
}) {
  const fieldIssues = issuesByPath.get(path) ?? issuesByPath.get(field.field_key) ?? [];
  const Heading = headingLevel === 2 ? "h2" : "h3";

  return (
    <section aria-labelledby={`field-${path}`}>
      <div className="flex items-baseline gap-2">
        <Heading
          id={`field-${path}`}
          className={cn(
            "font-semibold text-ink-strong",
            headingLevel === 2 ? "text-lg" : "text-[15px]",
          )}
        >
          {headingLevel === 2 ? `${romanize(index + 1)}、${field.label}` : field.label}
        </Heading>
        {field.required ? <span className="text-xs text-ink-faint">必填</span> : null}
      </div>
      {field.description ? <p className="mt-0.5 text-xs text-ink-muted">{field.description}</p> : null}
      {fieldIssues.length > 0 ? (
        <ul className="mt-2 space-y-1.5">
          {fieldIssues.map((issue) => (
            <li
              key={issue.key}
              className={cn(
                "rounded-md border px-3 py-2 text-sm",
                issue.severity === "error"
                  ? "border-danger-200 bg-danger-50 text-danger-700"
                  : "border-warning-200 bg-warning-50 text-warning-700",
              )}
            >
              {issue.message}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-3">
        <FieldValue
          field={field}
          path={path}
          value={value}
          onChange={onChange}
          readOnly={readOnly}
          issuesByPath={issuesByPath}
        />
      </div>
    </section>
  );
}

function FieldValue({
  field,
  path,
  value,
  onChange,
  readOnly,
  issuesByPath,
}: {
  field: ContentField;
  path: string;
  value: unknown;
  onChange: (value: unknown) => void;
  readOnly: boolean;
  issuesByPath: Map<string, ValidationIssue[]>;
}) {
  if (field.type === "group") {
    const record = (value ?? {}) as Record<string, unknown>;
    return (
      <div className="space-y-5 rounded-lg border border-line-subtle bg-surface-soft/60 p-4">
        {(field.children ?? []).map((child) => (
          <FieldBlock
            key={child.field_key}
            field={child}
            index={0}
            path={`${path}.${child.field_key}`}
            value={record[child.field_key]}
            onChange={(v) => onChange({ ...record, [child.field_key]: v })}
            readOnly={readOnly || child.editable === false}
            issuesByPath={issuesByPath}
            headingLevel={3}
          />
        ))}
      </div>
    );
  }

  if (field.type === "repeatable") {
    const items = (Array.isArray(value) ? value : []) as Record<string, unknown>[];
    return (
      <div className="space-y-4">
        {items.map((item, itemIndex) => (
          <div key={itemIndex} className="rounded-lg border border-line-subtle bg-surface-soft/60 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-brand-600">
                {field.label} · {itemIndex + 1}
              </p>
              {!readOnly ? (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`删除 ${field.label} ${itemIndex + 1}`}
                  disabled={items.length <= (field.min_items ?? 0)}
                  onClick={() => onChange(items.filter((_, i) => i !== itemIndex))}
                >
                  <Trash2 className="size-4 text-ink-muted" aria-hidden />
                </Button>
              ) : null}
            </div>
            <div className="mt-3 space-y-5">
              {(field.children ?? []).map((child) => (
                <FieldBlock
                  key={child.field_key}
                  field={child}
                  index={0}
                  path={`${path}.${itemIndex}.${child.field_key}`}
                  value={item[child.field_key]}
                  onChange={(v) =>
                    onChange(items.map((it, i) => (i === itemIndex ? { ...it, [child.field_key]: v } : it)))
                  }
                  readOnly={readOnly || child.editable === false}
                  issuesByPath={issuesByPath}
                  headingLevel={3}
                />
              ))}
            </div>
          </div>
        ))}
        {!readOnly ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              onChange([
                ...items,
                Object.fromEntries((field.children ?? []).map((child) => [child.field_key, defaultFor(child)])),
              ])
            }
          >
            <Plus className="size-4" aria-hidden />
            添加一项
          </Button>
        ) : null}
      </div>
    );
  }

  const Renderer = contentFieldRegistry.get(field.type);
  if (!Renderer) {
    return <UnknownFieldNotice field={field} />;
  }
  return <Renderer field={field} value={value} onChange={onChange} readOnly={readOnly} issues={[]} />;
}

function defaultFor(field: ContentField): unknown {
  switch (field.type) {
    case "text":
    case "rich_text":
      return "";
    case "number":
      return null;
    case "boolean":
      return false;
    case "list":
      return [];
    case "repeatable":
      return [];
    case "group":
      return {};
    default:
      return null;
  }
}

const ROMAN = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五", "十六"];

function romanize(n: number): string {
  return ROMAN[n - 1] ?? String(n);
}
