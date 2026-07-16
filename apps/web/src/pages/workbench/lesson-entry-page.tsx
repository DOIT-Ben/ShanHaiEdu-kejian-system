import { Navigate, useParams } from "react-router";
import { useLessonWorkspace } from "@/features/lessons";
import { Spinner } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

/** 课时入口：读取工作区后跳转到当前推进节点的工作台。 */
export function LessonEntryPage() {
  const { projectId = "", lessonId = "" } = useParams();
  const workspace = useLessonWorkspace(lessonId);

  if (workspace.isPending) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="正在载入课时…" />
      </div>
    );
  }
  if (workspace.isError) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={workspace.error} title="课时加载失败" onRetry={() => void workspace.refetch()} />
      </div>
    );
  }
  const nodeKey = workspace.data.current_node_key || "lesson_plan";
  return <Navigate to={`/app/projects/${projectId}/lessons/${lessonId}/workbench/${nodeKey}`} replace />;
}
