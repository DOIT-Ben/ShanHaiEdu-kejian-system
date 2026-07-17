import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useProjects() {
  return useQuery({
    queryKey: qk.projects.list(),
    queryFn: async () => {
      const result = unwrap(await client.GET("/projects"));
      return result.data.items;
    },
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: qk.projects.detail(projectId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/projects/{project_id}", {
          params: { path: { project_id: projectId } },
        }),
      );
      return { project: result.data, etag: result.etag };
    },
  });
}

/** 工作台聚合视图：项目 + 课时 + 节点运行 + 教材 + 自动化状态。 */
export function useProjectWorkflow(projectId: string) {
  return useQuery({
    queryKey: qk.projects.workflow(projectId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/projects/{project_id}/workflow", {
          params: { path: { project_id: projectId } },
        }),
      );
      return result.data;
    },
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      title: string;
      knowledge_point: string;
      grade?: string;
      textbook_edition?: string;
      automation_mode?: "manual" | "assisted" | "automatic";
    }) => {
      const result = unwrap(
        await client.POST("/projects", {
          body: input,
          params: { header: { "Idempotency-Key": createIdempotencyKey("project") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.all });
      void queryClient.invalidateQueries({ queryKey: qk.home });
    },
  });
}

export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      etag: string;
      patch: { title?: string; automation_mode?: "manual" | "assisted" | "automatic" };
    }) => {
      const result = unwrap(
        await client.PATCH("/projects/{project_id}", {
          params: {
            path: { project_id: projectId },
            header: { "If-Match": input.etag, "Idempotency-Key": createIdempotencyKey("project-update") },
          },
          body: input.patch,
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.detail(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.workflow(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.list() });
    },
  });
}

export function useLessons(projectId: string) {
  return useQuery({
    queryKey: qk.projects.lessons(projectId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/projects/{project_id}/lessons", {
          params: { path: { project_id: projectId } },
        }),
      );
      return result.data.items;
    },
  });
}

export function useLesson(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.detail(lessonId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/lessons/{lesson_id}", {
          params: { path: { lesson_id: lessonId } },
        }),
      );
      return { lesson: result.data, etag: result.etag };
    },
  });
}

export function useUpdateLessonBranches(lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      etag: string;
      patch: { ppt_enabled?: boolean; video_enabled?: boolean; intro_enabled?: boolean };
    }) => {
      const result = unwrap(
        await client.PATCH("/lessons/{lesson_id}", {
          params: {
            path: { lesson_id: lessonId },
            header: { "If-Match": input.etag, "Idempotency-Key": createIdempotencyKey("lesson-branch") },
          },
          body: input.patch,
        }),
      );
      return result.data;
    },
    onSuccess: (lesson) => {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.detail(lessonId) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.nodeRuns(lessonId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.workflow(lesson.project_id) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.lessons(lesson.project_id) });
    },
  });
}

export function useLessonNodeRuns(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.nodeRuns(lessonId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/lessons/{lesson_id}/node-runs", {
          params: { path: { lesson_id: lessonId } },
        }),
      );
      return result.data.items;
    },
  });
}
