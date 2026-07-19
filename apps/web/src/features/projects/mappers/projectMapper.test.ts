import { describe, expect, it } from "vitest";
import type { ProjectDto } from "@/features/projects/api/projectsApi";
import { mapProjectSummary } from "./projectMapper";

const project = {
  id: "project-1",
  title: "认识百分数",
  subject: "primary_math",
  knowledge_point: "百分数的意义",
  status: "draft",
  execution_mode: "guided",
  grade: "六年级",
  textbook_edition: "人教版",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-20T00:00:00Z",
} satisfies ProjectDto;

describe("mapProjectSummary", () => {
  it("只映射项目接口真实提供的状态，不推断课时或下一步", () => {
    expect(mapProjectSummary(project)).toMatchObject({
      id: "project-1",
      knowledgePoint: "百分数的意义",
      progressLabel: "草稿",
      status: "draft",
    });
    expect(mapProjectSummary(project).currentLesson).toBeUndefined();
    expect(mapProjectSummary(project).nextAction).toBeUndefined();
  });
});
