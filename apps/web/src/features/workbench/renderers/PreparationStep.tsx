import { ArrowRight, BookOpenCheck, ListOrdered } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { hasReadyTextbook } from "@/features/workbench/lib/stepAccess";
import { useMockRuntime } from "@/shared/api/mockClient";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export function PreparationStep({ type }: { type: "materials" | "lesson-division" }) {
  const { projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const isMaterials = type === "materials";
  const Icon = isMaterials ? BookOpenCheck : ListOrdered;
  const files = runtime.textbookFiles[projectId] ?? [];
  const lessonItems = getApprovedProjectLessons(runtime, projectId);
  const lessonDivision = Object.values(runtime.nodeStates).find(
    (node) =>
      node.project_id === projectId &&
      node.lesson_id === null &&
      node.node_key === "lesson-division",
  );
  const status = isMaterials
    ? hasReadyTextbook(runtime, projectId)
      ? "ready"
      : "not_ready"
    : lessonDivision?.status === "approved" && lessonItems.length === 0
      ? "review_required"
      : (lessonDivision?.status ?? (lessonItems.length > 0 ? "review_required" : "not_ready"));
  const ready = status === "approved" || status === "ready";
  return (
    <WorkbenchPageFrame width="narrow">
      <FocusPageHeader
        description={
          isMaterials
            ? files.length > 0
              ? `已收到 ${String(files.length)} 个教材文件，正在整理教材内容。`
              : "当前项目还没有教材文件，请先返回项目上传。"
            : lessonItems.length > 0
              ? `项目当前保存了 ${String(lessonItems.length)} 个课时，批准后才会开放下游制作。`
              : "当前项目还没有已保存的课时安排。"
        }
        eyebrow="课程准备"
        status={<StatusBadge status={status} />}
        title={isMaterials ? "查看教材" : "安排课时"}
      />
      <div className="mt-4 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-full bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
          <Icon aria-hidden="true" className="size-6" />
        </span>
        <h2 className="mt-3 text-lg font-semibold text-[var(--sh-ink-strong)]">
          {isMaterials
            ? ready
              ? "教材文件已准备"
              : "等待教材文件"
            : status === "approved"
              ? "课时安排已批准"
              : "课时安排等待确认"}
        </h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-[var(--sh-ink-muted)]">
          请在教材与课时页面核对文件信息和课时范围。确认后，后续教案与课件会使用当前版本。
        </p>
        <Link
          className={`${buttonVariants({ variant: "secondary" })} mt-4`}
          to={`/app/projects/${projectId}/materials`}
        >
          打开教材与课时
          <ArrowRight aria-hidden="true" />
        </Link>
      </div>
    </WorkbenchPageFrame>
  );
}
