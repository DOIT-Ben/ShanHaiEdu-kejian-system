import type { z } from "zod";

export * from "./evidence";
export * from "./division";
export * from "./lessonPlan";
export * from "./introDesign";
export * from "./ppt";
export * from "./video";

/**
 * 安全解析产物 content：失败时返回 null，由画布展示「内容格式异常」态，
 * 不允许因单个产物解析失败导致页面崩溃。
 */
export function parseContent<T extends z.ZodTypeAny>(
  schema: T,
  content: unknown,
): z.infer<T> | null {
  const result = schema.safeParse(content);
  return result.success ? result.data : null;
}
