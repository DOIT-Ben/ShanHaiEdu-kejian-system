import { Link, useOutletContext } from "react-router";
import { ArrowRight, BookOpen, Layers, ListTodo, Package } from "lucide-react";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { useLessons } from "@/features/lessons";
import { formatMinorUnits } from "@/shared/lib/format";
import type { NodeStatus } from "@/shared/lib/status";
import { Badge, EmptyState, NodeStatusBadge, PageHeader, Panel, PanelBody, PanelHeader, Progress, Skeleton } from "@/shared/ui";

const TEXTBOOK_STATUS: Record<string, { label: string; tone: "neutral" | "brand" | "running" | "success" | "danger" }> = {
  none: { label: "未上传", tone: "neutral" },
  uploading: { label: "上传中", tone: "running" },
  parsing: { label: "解析中", tone: "running" },
  evidence_ready: { label: "证据就绪", tone: "success" },
  parse_failed: { label: "解析失败", tone: "danger" },
};

const DIVISION_STATUS: Record<string, { label: string; tone: "neutral" | "brand" | "running" | "success" | "warning" | "danger" }> = {
  none: { label: "未生成", tone: "neutral" },
  generating: { label: "生成中", tone: "running" },
  needs_review: { label: "待确认", tone: "warning" },
  approved: { label: "已确认", tone: "success" },
  failed: { label: "生成失败", tone: "danger" },
};

/** 项目概览：进度、预算、教材/划分状态、课时入口。 */
export function ProjectOverviewPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const lessons = useLessons(project.project_id);
  const textbookStatus = TEXTBOOK_STATUS[project.textbook_status ?? "none"];
  const divisionStatus = DIVISION_STATUS[project.division_status ?? "none"];
  const budget = project.budget_minor_units ?? 0;
  const spent = project.spent_minor_units ?? 0;

  return (
    <div className="space-y-5 p-6">
      <PageHeader
        title={project.name}
        description={`${project.grade}年级 · ${project.textbook_version ?? ""} ${project.volume ?? ""} · ${
          project.execution_mode === "manual" ? "手动模式" : project.execution_mode === "semi_auto" ? "半自动模式" : "全自动草稿模式"
        }`}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel>
          <PanelBody>
            <p className="text-xs font-medium text-ink-muted">整体进度</p>
            <p className="mt-1 text-2xl font-semibold text-ink-1">{Math.round(project.progress_percent ?? 0)}%</p>
            <Progress className="mt-2" value={project.progress_percent ?? 0} />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelBody>
            <p className="text-xs font-medium text-ink-muted">预算使用</p>
            <p className="mt-1 text-2xl font-semibold text-ink-1">
              {formatMinorUnits(spent)}
              <span className="ml-1 text-sm font-normal text-ink-muted">/ {formatMinorUnits(budget)}</span>
            </p>
            <Progress className="mt-2" value={budget > 0 ? Math.min(100, (spent / budget) * 100) : 0} />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelBody className="space-y-2.5">
            <Link to="textbook" className="flex items-center justify-between text-sm text-ink-1 hover:text-brand">
              <span className="flex items-center gap-2">
                <BookOpen className="size-4 text-ink-2" aria-hidden />
                教材证据
              </span>
              <Badge tone={textbookStatus.tone}>{textbookStatus.label}</Badge>
            </Link>
            <Link to="lesson-division" className="flex items-center justify-between text-sm text-ink-1 hover:text-brand">
              <span className="flex items-center gap-2">
                <Layers className="size-4 text-ink-2" aria-hidden />
                课时划分
              </span>
              <Badge tone={divisionStatus.tone}>{divisionStatus.label}</Badge>
            </Link>
            <Link to="delivery" className="flex items-center justify-between text-sm text-ink-1 hover:text-brand">
              <span className="flex items-center gap-2">
                <Package className="size-4 text-ink-2" aria-hidden />
                交付
              </span>
              <ArrowRight className="size-4 text-ink-muted" aria-hidden />
            </Link>
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader
          title="课时"
          description="课时由「课时划分」确认后生成；点击进入课时工作台。"
          actions={
            <Link to="lessons" className="text-xs font-medium text-brand hover:underline">
              查看全部
            </Link>
          }
        />
        <PanelBody>
          {lessons.isPending ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-14" />
              ))}
            </div>
          ) : (lessons.data ?? []).length === 0 ? (
            <EmptyState
              icon={<ListTodo className="size-8" aria-hidden />}
              title="还没有课时"
              description="先上传教材并完成课时划分，系统会为每个课时建立 18 步工作流。"
            />
          ) : (
            <ul className="divide-y divide-divider">
              {(lessons.data ?? []).slice(0, 6).map((lesson) => (
                <li key={lesson.lesson_id}>
                  <Link
                    to={`lessons/${lesson.lesson_id}`}
                    className="flex items-center gap-3 py-2.5 transition-colors hover:bg-surface-hover"
                  >
                    <span className="w-14 shrink-0 text-xs text-ink-muted">第{lesson.sequence_number}课时</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-1">{lesson.title}</span>
                    <span className="hidden items-center gap-1 lg:flex">
                      {(["lesson_plan", "intro_design", "ppt", "video", "delivery"] as const).map((stage) =>
                        lesson.stage_summary?.[stage] ? (
                          <NodeStatusBadge key={stage} status={lesson.stage_summary[stage] as NodeStatus} />
                        ) : null,
                      )}
                    </span>
                    <ArrowRight className="size-4 shrink-0 text-ink-muted" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
