import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useIntroOptions(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.introOptions(lessonId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/lessons/{lesson_id}/intro-options", {
          params: { path: { lesson_id: lessonId } },
        }),
      );
      return { optionSet: result.data, etag: result.etag };
    },
  });
}

export function useUpdateIntroOption(lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { optionKey: string; etag: string; patch: Record<string, unknown> }) => {
      const result = unwrap(
        await client.PATCH("/lessons/{lesson_id}/intro-options/{option_key}", {
          params: { path: { lesson_id: lessonId, option_key: input.optionKey }, header: { "If-Match": input.etag } },
          body: input.patch,
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.introOptions(lessonId) });
    },
  });
}

export function useCurrentIntroSelection(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.introSelection(lessonId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/lessons/{lesson_id}/intro-selections/current", {
          params: { path: { lesson_id: lessonId } },
        }),
      );
      return result.data ?? null;
    },
  });
}

export function useSelectIntro(lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { optionKey: string; optionSetVersionId: string }) => {
      const result = unwrap(
        await client.POST("/lessons/{lesson_id}/intro-selections", {
          params: { path: { lesson_id: lessonId }, header: { "Idempotency-Key": createIdempotencyKey("intro-select") } },
          body: { option_key: input.optionKey, intro_option_set_version_id: input.optionSetVersionId },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.introSelection(lessonId) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.nodeRuns(lessonId) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.detail(lessonId) });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["lessons", lessonId, "video-project"] });
    },
  });
}
