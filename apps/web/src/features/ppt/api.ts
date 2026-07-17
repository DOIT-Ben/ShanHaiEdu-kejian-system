import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function usePptPages(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.pptPages(lessonId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/lessons/{lesson_id}/ppt-pages", {
          params: { path: { lesson_id: lessonId } },
        }),
      );
      return result.data.items;
    },
  });
}

export function usePptPage(pageId: string | null) {
  return useQuery({
    queryKey: qk.pptPages.detail(pageId ?? "none"),
    enabled: Boolean(pageId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/ppt-pages/{page_id}", {
          params: { path: { page_id: pageId! } },
        }),
      );
      return { detail: result.data, etag: result.etag };
    },
  });
}

export function useSavePptPage(pageId: string, lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { etag: string; spec: Record<string, unknown> }) => {
      const result = unwrap(
        await client.PUT("/ppt-pages/{page_id}", {
          params: { path: { page_id: pageId }, header: { "If-Match": input.etag } },
          body: { spec: input.spec as never },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.pptPages.detail(pageId) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.pptPages(lessonId) });
    },
  });
}

export function useRegeneratePptPage(pageId: string, lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input?: { instruction?: string }) => {
      const result = unwrap(
        await client.POST("/ppt-pages/{page_id}/regenerate", {
          params: { path: { page_id: pageId }, header: { "Idempotency-Key": createIdempotencyKey("page-regen") } },
          body: input?.instruction ? { instruction: input.instruction } : {},
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.pptPages.detail(pageId) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.pptPages(lessonId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}

export function usePptStyleContract(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.pptStyleContract(lessonId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/lessons/{lesson_id}/ppt-style-contract", {
          params: { path: { lesson_id: lessonId } },
        }),
      );
      return result.data ?? null;
    },
  });
}
