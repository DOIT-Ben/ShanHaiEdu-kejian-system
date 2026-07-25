import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type WorkflowDto = components["schemas"]["WorkflowEnvelope"]["data"];
export type NodeRunDto = components["schemas"]["NodeRun"];
export type AcceptedNodeRunJobDto = components["schemas"]["AcceptedJobEnvelope"]["data"];

export async function prepareLessonPlanGeneration({
  idempotencyKey,
  lessonId,
}: {
  idempotencyKey: string;
  lessonId: string;
}): Promise<NodeRunDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/lessons/{lesson_id}/lesson-plan/node-runs", {
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { lesson_id: lessonId },
      },
    }),
  );
  return response.data;
}

export async function startNodeRun({
  idempotencyKey,
  nodeRunId,
  userRevision,
}: {
  idempotencyKey: string;
  nodeRunId: string;
  userRevision?: string;
}): Promise<AcceptedNodeRunJobDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/node-runs/{node_run_id}/start", {
      ...(userRevision ? { body: { user_revision: userRevision } } : {}),
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { node_run_id: nodeRunId },
      },
    }),
  );
  return response.data;
}

export async function getProjectWorkflow(projectId: string): Promise<WorkflowDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/workflow", {
      params: { path: { project_id: projectId } },
    }),
  );
  return response.data;
}
