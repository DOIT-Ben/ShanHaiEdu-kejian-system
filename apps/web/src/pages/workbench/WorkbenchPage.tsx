import { useState } from "react";
import { Navigate, useParams } from "react-router";
import { getStep } from "@/entities/workflow";
import { nodeRendererRegistry } from "@/entities/registry";
import { useLesson, useLessonNodeRuns } from "@/features/projects";
import {
  ContextDrawer,
  StepRail,
  TaskStatusBar,
  WorkbenchProvider,
  registerWorkbenchCanvases,
} from "@/features/workbench";
import { Skeleton } from "@/shared/ui";

registerWorkbenchCanvases();

/**
 * 课时工作台（02 §4）：左流程栏 + 中央画布（≥70%）+ 右上下文抽屉 + 底部任务条。
 * stepKey 由 URL 提供，刷新/直达可恢复。
 */
export default function WorkbenchPage() {
  const { projectId = "", lessonId = "", stepKey = "" } = useParams();
  const { data: lessonData, isPending: lessonLoading } = useLesson(lessonId);
  const { data: nodeRuns, isPending: runsLoading } = useLessonNodeRuns(lessonId);
  const [railCollapsed, setRailCollapsed] = useState(false);

  const step = getStep(stepKey);

  if (!step || step.kind === "link") {
    // 未知步骤 / 链接步骤直达时回到课时入口
    return <Navigate to={`/app/projects/${projectId}/lessons/${lessonId}`} replace />;
  }

  if (lessonLoading || runsLoading || !lessonData || !nodeRuns) {
    return (
      <div className="flex flex-1 gap-4 p-6">
        <Skeleton className="h-[70vh] w-56 rounded-lg" />
        <Skeleton className="h-[70vh] flex-1 rounded-lg" />
      </div>
    );
  }

  const Canvas = nodeRendererRegistry.get(stepKey);
  const nodeRun = step.nodeKey ? (nodeRuns.find((run) => run.node_key === step.nodeKey) ?? null) : null;

  return (
    <WorkbenchProvider value={{ projectId, lessonId, stepKey }}>
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1">
          <StepRail
            projectId={projectId}
            lesson={lessonData.lesson}
            nodeRuns={nodeRuns}
            collapsed={railCollapsed}
            onToggle={() => setRailCollapsed((v) => !v)}
          />
          <main className="min-w-0 flex-1 overflow-y-auto bg-canvas">
            {Canvas ? (
              <Canvas projectId={projectId} lessonId={lessonId} stepKey={stepKey} />
            ) : (
              <div className="p-10 text-center" role="alert">
                <p className="text-base font-medium text-ink-strong">这一步暂未支持</p>
                <p className="mt-1 text-sm text-ink-muted">
                  当前版本还不支持「{step.label}」的画布，请刷新或等待应用升级。
                </p>
              </div>
            )}
          </main>
          <ContextDrawer nodeRunId={nodeRun?.id ?? null} />
        </div>
        <TaskStatusBar projectId={projectId} />
      </div>
    </WorkbenchProvider>
  );
}
