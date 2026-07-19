import { create } from "zustand";

type WorkbenchUiState = {
  sidebarCollapsed: boolean;
  contextDrawerOpen: boolean;
  contextTab: "references" | "prompt" | "checks" | "history";
  toggleSidebar: () => void;
  closeContextDrawer: () => void;
  openContextDrawer: (tab: WorkbenchUiState["contextTab"]) => void;
};

export const useWorkbenchUi = create<WorkbenchUiState>((set) => ({
  sidebarCollapsed: false,
  contextDrawerOpen: false,
  contextTab: "references",
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  closeContextDrawer: () => set({ contextDrawerOpen: false }),
  openContextDrawer: (contextTab) => set({ contextDrawerOpen: true, contextTab }),
}));
