import { AlertTriangle, CirclePause, CloudCog, MessageSquareText } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { createMockTask, saveMockDraft, updateMockNodeState } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";

export function ScenarioStateNotice({ scenario }: { scenario: string | null }) {
  const { openContextDrawer } = useWorkbenchUi();
  const navigate = useNavigate();
  const { lessonId = "", projectId = "", stepKey = "lesson-plan" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const resolveScenario = (
    action: "retry-partial" | "refresh-stale" | "keep-stale" | "restart-cancelled",
  ) => {
    const status = action === "keep-stale" ? "approved" : "queued";
    updateMockNodeState(projectId, lessonId, stepKey, {
      stale_reason: null,
      status,
      title: "当前制作步骤",
    });
    saveMockDraft(
      `project:${projectId}:lesson:${lessonId}:scenario-action`,
      { action, nodeKey: stepKey, status },
      { lessonId, nodeKey: stepKey, projectId },
    );
    if (status === "queued") {
      createMockTask({
        detail:
          action === "retry-partial"
            ? "只重新处理未完成内容，其他内容保持不变"
            : "已按当前内容开始更新作品",
        node_run_id: `${projectId}:${lessonId}:${stepKey}`,
        progress: 0,
        project_id: projectId,
        stage: "等待处理",
        status: "queued",
        title: action === "retry-partial" ? "重新处理未完成内容" : "按新内容更新作品",
      });
    }
    const next = new URLSearchParams(searchParams);
    next.delete("scenario");
    setSearchParams(next, { replace: true });
  };
  if (scenario === "node_running") {
    return (
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--sh-brand-100)] bg-[var(--sh-brand-50)] px-4 py-2 text-xs">
        <CloudCog aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
        <span className="flex-1 text-[var(--sh-ink-default)]">
          系统正在准备当前作品。可以离开页面，返回后会从最新阶段继续显示。
        </span>
        <Button onClick={() => void navigate("/app/tasks")} size="sm" variant="quiet">
          查看处理进度
        </Button>
      </div>
    );
  }
  if (scenario === "node_partial") {
    return (
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--sh-warning)]/20 bg-[var(--sh-warning-soft)] px-4 py-2 text-xs">
        <AlertTriangle aria-hidden="true" className="size-5 text-[var(--sh-warning)]" />
        <span className="flex-1 text-[var(--sh-ink-default)]">
          8 项已完成，1 项需要处理。已完成内容保持不变，只重新处理未完成内容。
        </span>
        <Button onClick={() => resolveScenario("retry-partial")} size="sm" variant="secondary">
          重新处理未完成内容
        </Button>
      </div>
    );
  }
  if (scenario === "node_stale") {
    return (
      <div className="border-b border-[var(--sh-warning)]/20 bg-[var(--sh-warning-soft)] px-4 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <AlertTriangle aria-hidden="true" className="size-5 text-[var(--sh-warning)]" />
          <span className="flex-1 text-[var(--sh-ink-default)]">
            相关内容已经更新，当前作品可能需要同步。原来的作品不会自动删除。
          </span>
          <Button onClick={() => resolveScenario("refresh-stale")} size="sm">
            根据新内容更新
          </Button>
          <Button onClick={() => resolveScenario("keep-stale")} size="sm" variant="secondary">
            继续使用当前版本
          </Button>
        </div>
      </div>
    );
  }
  if (scenario === "prompt_review") {
    return (
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4 py-2 text-xs">
        <MessageSquareText aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
        <span className="flex-1 text-[var(--sh-ink-default)]">
          生成前可以检查并修改内容要求，课程范围和儿童安全要求保持不变。
        </span>
        <Button onClick={() => openContextDrawer("prompt")} size="sm" variant="secondary">
          查看内容要求
        </Button>
      </div>
    );
  }
  if (scenario === "cancelled") {
    return (
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] px-4 py-2 text-xs">
        <CirclePause aria-hidden="true" className="size-5 text-[var(--sh-ink-muted)]" />
        <span className="min-w-0 flex-1 text-[var(--sh-ink-default)]">
          本次制作已取消，已保存的草稿仍然保留。你可以修改要求后重新开始。
        </span>
        <Button onClick={() => resolveScenario("restart-cancelled")} size="sm" variant="secondary">
          修改要求并重新开始
        </Button>
      </div>
    );
  }
  return null;
}
