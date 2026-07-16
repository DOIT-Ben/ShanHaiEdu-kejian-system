import type { ComponentType } from "react";
import type { NodeWorkspace } from "@/shared/api/types";
import type { NodeItemActionType } from "@/features/runs";

/** 节点画布组件的统一契约。 */
export interface CanvasProps {
  workspace: NodeWorkspace;
  projectId: string;
  lessonId: string;
  nodeKey: string;
  /** 列表项级操作（单套方案/单页/单镜头/单片段）。 */
  onItemAction: (input: {
    itemId: string;
    action: NodeItemActionType;
    instruction?: string;
    payload?: Record<string, unknown>;
  }) => void;
  itemActionPending?: boolean;
  /** 教师直接编辑内容 → 保存为新版本。 */
  onSaveEdited: (content: Record<string, unknown>) => void;
  savePending?: boolean;
}

export type NodeCanvas = ComponentType<CanvasProps>;

const registry = new Map<string, NodeCanvas>();

export function registerNodeCanvas(rendererKey: string, canvas: NodeCanvas): void {
  registry.set(rendererKey, canvas);
}

export function getNodeCanvas(rendererKey: string): NodeCanvas | null {
  return registry.get(rendererKey) ?? null;
}
