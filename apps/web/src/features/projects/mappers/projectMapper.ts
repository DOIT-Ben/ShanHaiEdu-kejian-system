import type { ProjectDto } from "@/features/projects/api/projectsApi";
import type { ProjectSummary } from "@/entities/project/model";

export function mapProjectSummary(project: ProjectDto): ProjectSummary {
  const statusLabel =
    project.status === "archived" ? "已归档" : project.status === "active" ? "进行中" : "草稿";
  return {
    archived: project.status === "archived",
    id: project.id,
    title: project.title,
    knowledgePoint: project.knowledge_point,
    grade: project.grade ?? "年级待确认",
    textbookEdition: project.textbook_edition ?? "教材版本待确认",
    progressLabel: statusLabel,
    status: project.status,
    updatedAt: new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(
      new Date(project.updated_at),
    ),
    updatedAtIso: project.updated_at,
  };
}
