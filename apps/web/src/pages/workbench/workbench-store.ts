import { create } from "zustand";

interface WorkbenchUiState {
  inspectorWidth: number;
  inspectorTab: string;
  taskDockExpanded: boolean;
  setInspectorWidth: (width: number) => void;
  setInspectorTab: (tab: string) => void;
  setTaskDockExpanded: (expanded: boolean) => void;
}

export const INSPECTOR_MIN = 320;
export const INSPECTOR_MAX = 520;

/** 工作台 UI 状态（纯界面状态，不含服务器数据）。 */
export const useWorkbenchUi = create<WorkbenchUiState>((set) => ({
  inspectorWidth: 400,
  inspectorTab: "inputs",
  taskDockExpanded: false,
  setInspectorWidth: (width) => set({ inspectorWidth: Math.min(INSPECTOR_MAX, Math.max(INSPECTOR_MIN, width)) }),
  setInspectorTab: (tab) => set({ inspectorTab: tab }),
  setTaskDockExpanded: (expanded) => set({ taskDockExpanded: expanded }),
}));
