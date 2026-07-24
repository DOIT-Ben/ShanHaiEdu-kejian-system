import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult, unwrapEmptyApiResult } from "@/shared/api/client";

export type CurrentSession = components["schemas"]["CurrentSession"];

export async function createTeacherSession(accessCode: string): Promise<CurrentSession> {
  const response = unwrapApiResult(
    await apiClient.POST("/auth/session", {
      body: { access_code: accessCode },
    }),
  );
  return response.data;
}

export async function getCurrentSession(): Promise<CurrentSession> {
  const response = unwrapApiResult(await apiClient.GET("/auth/session"));
  return response.data;
}

export async function deleteCurrentSession(csrfToken: string): Promise<void> {
  unwrapEmptyApiResult(
    await apiClient.DELETE("/auth/session", {
      params: { header: { "X-CSRF-Token": csrfToken } },
    }),
  );
}
