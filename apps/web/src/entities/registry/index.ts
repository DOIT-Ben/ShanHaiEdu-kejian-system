import type { ComponentType } from "react";
import type { ContentField } from "@/entities/content/definition";

/**
 * 注册表扩展点（docs/frontend/06_组件化与代码架构.md §4）。
 * 新作品类型 / 字段类型 / 预览类型 / 创作台通过注册进入系统，
 * 禁止在页面用巨型 if/else 或 switch 按类型渲染。
 */

function createRegistry<V>(name: string) {
  const entries = new Map<string, V>();
  return {
    register(key: string, value: V): void {
      entries.set(key, value);
    },
    get(key: string): V | undefined {
      return entries.get(key);
    },
    has(key: string): boolean {
      return entries.has(key);
    },
    keys(): string[] {
      return [...entries.keys()];
    },
    name,
  };
}

/** 工作流步骤画布渲染器：按 stepKey 注册。 */
export interface StepCanvasProps {
  projectId: string;
  lessonId: string;
  stepKey: string;
}

export const nodeRendererRegistry = createRegistry<ComponentType<StepCanvasProps>>(
  "nodeRendererRegistry",
);

/** 动态内容字段渲染器：按 content-definition field type 注册。 */
export interface ContentFieldRendererProps {
  field: ContentField;
  value: unknown;
  onChange: (next: unknown) => void;
  readOnly: boolean;
  issues: { severity: "error" | "warning" | "info"; message: string }[];
}

export const contentFieldRegistry = createRegistry<ComponentType<ContentFieldRendererProps>>(
  "contentFieldRegistry",
);

/** 候选/素材预览渲染器：按 media_type 注册。 */
export interface ArtifactPreviewProps {
  mediaType: string;
  previewUrl: string | null;
  title: string;
  className?: string;
}

export const artifactPreviewRegistry = createRegistry<ComponentType<ArtifactPreviewProps>>(
  "artifactPreviewRegistry",
);

/** 创作台：按 studio_type 注册（image/video/presentation/未来能力）。 */
export interface StudioDefinition {
  key: string;
  title: string;
  description: string;
  entryLabel: string;
  route: string;
}

export const studioRegistry = createRegistry<StudioDefinition>("studioRegistry");
