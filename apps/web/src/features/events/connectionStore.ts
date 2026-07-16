import { create } from "zustand";
import type { ConnectionMode } from "@/shared/api";

interface ConnectionState {
  mode: ConnectionMode;
  lastEventAt: string | null;
  setMode: (mode: ConnectionMode) => void;
  markEvent: () => void;
}

/** 实时连接状态（顶栏指示器 + 轮询降级提示共用）。 */
export const useConnectionStore = create<ConnectionState>((set) => ({
  mode: "connecting",
  lastEventAt: null,
  setMode: (mode) => set({ mode }),
  markEvent: () => set({ lastEventAt: new Date().toISOString() }),
}));
