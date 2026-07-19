import type { components, paths } from "@/generated/api-schema";
import { apiRequest, apiRequestWithResponse } from "@/shared/api/client";

export type ProjectDto = components["schemas"]["Project"];
type ProjectListEnvelope =
  paths["/projects"]["get"]["responses"][200]["content"]["application/json"];
type ProjectEnvelope =
  paths["/projects/{project_id}"]["get"]["responses"][200]["content"]["application/json"];
type CreateProjectEnvelope =
  paths["/projects"]["post"]["responses"][201]["content"]["application/json"];
type CreateProjectRequest = components["schemas"]["CreateProjectRequest"];

export type ProjectListPage = {
  items: ProjectDto[];
  nextCursor?: string;
};

export async function listProjectsPage(cursor?: string, limit = 100): Promise<ProjectListPage> {
  const params = new URLSearchParams({ "page[limit]": String(limit) });
  if (cursor) params.set("page[cursor]", cursor);
  const response = await apiRequest<ProjectListEnvelope>(`/projects?${params.toString()}`);
  return {
    items: response.data.items,
    nextCursor: response.meta.next_cursor ?? undefined,
  };
}

export async function listProjects(): Promise<ProjectDto[]> {
  return (await listProjectsPage()).items;
}

export async function getProject(projectId: string): Promise<ProjectDto> {
  const response = await apiRequest<ProjectEnvelope>(`/projects/${projectId}`);
  return response.data;
}

export async function getProjectVersioned(
  projectId: string,
): Promise<{ etag?: string; project: ProjectDto }> {
  const response = await apiRequestWithResponse<ProjectEnvelope>(`/projects/${projectId}`);
  return { etag: response.etag, project: response.body.data };
}

export async function createProject({
  idempotencyKey,
  input,
}: {
  idempotencyKey: string;
  input: CreateProjectRequest;
}): Promise<ProjectDto> {
  const response = await apiRequest<CreateProjectEnvelope>("/projects", {
    method: "POST",
    body: input,
    idempotencyKey,
  });
  return response.data;
}
