import * as ToastPrimitive from "@radix-ui/react-toast";
import { create } from "zustand";
import { CheckCircle2, AlertTriangle, Info, XCircle, X } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export type ToastTone = "success" | "info" | "warning" | "danger";

export interface ToastMessage {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface ToastStore {
  toasts: ToastMessage[];
  push: (toast: Omit<ToastMessage, "id">) => void;
  dismiss: (id: string) => void;
}

let toastSeq = 0;

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: (toast) =>
    set((state) => ({
      toasts: [...state.toasts.slice(-4), { ...toast, id: `toast-${++toastSeq}` }],
    })),
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

/** 短期通知；阻断性错误请使用 ErrorRecoveryPanel，而不是 Toast。 */
export function toast(input: Omit<ToastMessage, "id">) {
  useToastStore.getState().push(input);
}

const toneIcon = {
  success: <CheckCircle2 className="size-4 text-success" aria-hidden />,
  info: <Info className="size-4 text-brand" aria-hidden />,
  warning: <AlertTriangle className="size-4 text-warning" aria-hidden />,
  danger: <XCircle className="size-4 text-danger" aria-hidden />,
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <ToastPrimitive.Provider swipeDirection="right" duration={5000}>
      {toasts.map((t) => (
        <ToastPrimitive.Root
          key={t.id}
          onOpenChange={(open) => {
            if (!open) dismiss(t.id);
          }}
          className={cn(
            "flex items-start gap-3 rounded-overlay border border-line bg-surface-1 p-4 shadow-lg",
          )}
        >
          {toneIcon[t.tone]}
          <div className="min-w-0 flex-1">
            <ToastPrimitive.Title className="text-sm font-medium text-ink-1">
              {t.title}
            </ToastPrimitive.Title>
            {t.description ? (
              <ToastPrimitive.Description className="mt-0.5 text-sm text-ink-2">
                {t.description}
              </ToastPrimitive.Description>
            ) : null}
          </div>
          <ToastPrimitive.Close aria-label="关闭通知" className="rounded p-0.5 text-ink-muted hover:text-ink-1">
            <X className="size-4" aria-hidden />
          </ToastPrimitive.Close>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport className="fixed bottom-16 right-4 z-[60] flex w-96 max-w-[92vw] flex-col gap-2" />
    </ToastPrimitive.Provider>
  );
}
