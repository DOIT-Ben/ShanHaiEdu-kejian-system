import { type ReactNode, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppError } from "@/shared/api";
import { Toaster, TooltipProvider } from "@/shared/ui";

function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof AppError) {
    if (error.isSessionExpired) return false;
    if (error.status === 429 || error.status >= 500 || error.retryable) return failureCount < 2;
    return false;
  }
  // 网络异常等未知错误：有限重试
  return failureCount < 2;
}

export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 15_000,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createAppQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        {children}
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
