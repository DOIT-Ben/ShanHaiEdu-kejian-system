import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult, unwrapApiResultWithResponse } from "@/shared/api/client";

export type ProjectDto = components["schemas"]["Project"];
type CreateProjectRequest = components["schemas"]["CreateProjectRequest"];

export type ProjectListPage = {
  items: ProjectDto[];
  nextCursor?: string;
};

export async function listProjectsPage(cursor?: string, limit = 100): Promise<ProjectListPage> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects", {
      params: { query: { "page[cursor]": cursor, "page[limit]": limit } },
    }),
  );
  return {
    items: response.data.items,
    nextCursor: response.meta.next_cursor ?? undefined,
  };
}

export async function listProjects(): Promise<ProjectDto[]> {
  return (await listProjectsPage()).items;
}

export async function getProject(projectId: string): Promise<ProjectDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}", {
      params: { path: { project_id: projectId } },
    }),
  );
  return response.data;
}

export async function getProjectVersioned(
  projectId: string,
): Promise<{ etag?: string; project: ProjectDto }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.GET("/projects/{project_id}", {
      params: { path: { project_id: projectId } },
    }),
  );
  return { etag: response.etag, project: response.body.data };
}

export async function createProject({
  idempotencyKey,
  input,
}: {
  idempotencyKey: string;
  input: CreateProjectRequest;
}): Promise<ProjectDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/projects", {
      body: input,
      params: { header: { "Idempotency-Key": idempotencyKey } },
    }),
  );
  return response.data;
}
