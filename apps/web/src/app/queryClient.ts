import { QueryClient } from "@tanstack/react-query";
import { AppError } from "@/shared/api";

/**
 * 服务端状态唯一入口（06 §5）：TanStack Query。
 * 重试只针对可重试错误；4xx 业务错误立即失败交给页面处理。
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => {
          if (error instanceof AppError) {
            if (!error.retryable) return false;
            return failureCount < 2;
          }
          return failureCount < 1;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}
