import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type WorkflowDto = components["schemas"]["WorkflowEnvelope"]["data"];

export async function getProjectWorkflow(projectId: string): Promise<WorkflowDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/workflow", {
      params: { path: { project_id: projectId } },
    }),
  );
  return response.data;
}
