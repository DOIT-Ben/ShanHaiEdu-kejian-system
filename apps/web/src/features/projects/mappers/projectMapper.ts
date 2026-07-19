import type { ProjectDto } from "@/features/projects/api/projectsApi";
import type { ProjectSummary } from "@/entities/project/model";

export function mapProjectSummary(project: ProjectDto): ProjectSummary {
  return {
    archived: project.status === "archived",
    id: project.id,
    title: project.title,
    knowledgePoint: project.knowledge_point,
    grade: project.grade ?? "年级待确认",
    textbookEdition: project.textbook_edition ?? "教材版本待确认",
    currentLesson: "第 1 课时 · 当前知识点",
    nextAction:
      project.status === "draft"
        ? "上传并确认教材范围"
        : project.status === "archived"
          ? "查看已归档内容"
          : "继续当前课时制作",
    progressLabel:
      project.status === "draft" ? "准备课程" : project.status === "archived" ? "已归档" : "制作中",
    status: project.status,
    updatedAt: new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(
      new Date(project.updated_at),
    ),
  };
}
