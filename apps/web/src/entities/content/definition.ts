import { z } from "zod";

/**
 * 动态内容定义（contracts/content-definition.schema.json）。
 * 教案由后端内容定义驱动；前端通用渲染，禁止固定十二部分字段树。
 */

export const CONTENT_FIELD_TYPES = [
  "text",
  "rich_text",
  "number",
  "boolean",
  "list",
  "table",
  "group",
  "repeatable",
  "reference",
  "asset",
  "math",
  "rubric",
  "timeline",
] as const;

export type ContentFieldType = (typeof CONTENT_FIELD_TYPES)[number];

export interface ContentField {
  field_key: string;
  label: string;
  description?: string;
  type: ContentFieldType | (string & {});
  required: boolean;
  editable: boolean;
  deletable: boolean;
  repeatable?: boolean;
  min_items?: number;
  max_items?: number;
  ui_widget?: string;
  placeholder?: string;
  generation_instruction?: string;
  validation_rules?: Record<string, unknown>[];
  visibility_condition?: Record<string, unknown> | null;
  export_mapping?: Record<string, unknown> | null;
  children?: ContentField[];
}

export interface ContentDefinition {
  definition_key: string;
  title: string;
  description?: string;
  fields: ContentField[];
}

const fieldSchema: z.ZodType<ContentField> = z.lazy(() =>
  z.object({
    field_key: z.string().regex(/^[a-z][a-z0-9_.-]+$/),
    label: z.string().min(1),
    description: z.string().optional(),
    type: z.string(),
    required: z.boolean(),
    editable: z.boolean(),
    deletable: z.boolean(),
    repeatable: z.boolean().optional(),
    min_items: z.number().int().min(0).optional(),
    max_items: z.number().int().min(1).optional(),
    ui_widget: z.string().optional(),
    placeholder: z.string().optional(),
    generation_instruction: z.string().optional(),
    validation_rules: z.array(z.record(z.string(), z.unknown())).optional(),
    visibility_condition: z.record(z.string(), z.unknown()).nullable().optional(),
    export_mapping: z.record(z.string(), z.unknown()).nullable().optional(),
    children: z.array(fieldSchema).optional(),
  }),
);

export const contentDefinitionSchema: z.ZodType<ContentDefinition> = z.object({
  definition_key: z.string().regex(/^[a-z][a-z0-9_.-]+$/),
  title: z.string().min(1),
  description: z.string().optional(),
  fields: z.array(fieldSchema).min(1),
});

export function parseContentDefinition(input: unknown): ContentDefinition {
  return contentDefinitionSchema.parse(input);
}

/** 未知字段类型必须显式暴露，不得静默丢弃（07 文档 §5）。 */
export function isKnownFieldType(type: string): type is ContentFieldType {
  return (CONTENT_FIELD_TYPES as readonly string[]).includes(type);
}
