import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult, unwrapApiResultWithResponse } from "@/shared/api/client";

export type AutomationPolicyDto = components["schemas"]["AutomationPolicy"];
export type UpdateAutomationPolicyRequest = components["schemas"]["UpdateAutomationPolicyRequest"];

export async function getProjectAutomationPolicy(projectId: string): Promise<AutomationPolicyDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/automation-policy", {
      params: { path: { project_id: projectId } },
    }),
  );
  return response.data;
}

export async function getProjectAutomationPolicyVersioned(
  projectId: string,
): Promise<{ etag?: string; policy: AutomationPolicyDto }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.GET("/projects/{project_id}/automation-policy", {
      params: { path: { project_id: projectId } },
    }),
  );
  return { etag: response.etag, policy: response.body.data };
}

export async function updateProjectAutomationPolicy({
  etag,
  idempotencyKey,
  input,
  projectId,
}: {
  etag: string;
  idempotencyKey: string;
  input: UpdateAutomationPolicyRequest;
  projectId: string;
}): Promise<{ etag?: string; policy: AutomationPolicyDto }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.PATCH("/projects/{project_id}/automation-policy", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey, "If-Match": etag },
        path: { project_id: projectId },
      },
    }),
  );
  return { etag: response.etag, policy: response.body.data };
}
