import { Navigate, useParams } from "react-router";
import { stepKeyForNode, STEPS } from "@/entities/workflow";
import { useLessonNodeRuns } from "@/features/projects";
import { FullScreenLoading } from "@/shared/ui";

/** 课时入口：定位到第一个需要老师处理的步骤（等待确认 > 已变化 > 可开始 > 默认教案）。 */
export default function LessonEntryPage() {
  const { projectId = "", lessonId = "" } = useParams();
  const { data: nodeRuns, isPending } = useLessonNodeRuns(lessonId);

  if (isPending || !nodeRuns) {
    return <FullScreenLoading label="正在打开课时…" />;
  }

  const byPriority = (statuses: string[]): string | null => {
    for (const status of statuses) {
      // 按流程栏顺序找第一个符合状态的节点
      for (const step of STEPS) {
        if (!step.nodeKey) continue;
        const run = nodeRuns.find((r) => r.node_key === step.nodeKey);
        if (run && run.status === status) {
          return stepKeyForNode(run.node_key, run.status);
        }
      }
    }
    return null;
  };

  const target =
    byPriority(["review_required", "stale", "failed", "running", "queued", "ready", "draft"]) ?? "lesson-plan";

  return <Navigate to={`/app/projects/${projectId}/lessons/${lessonId}/work/${target}`} replace />;
}
