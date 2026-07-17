import { createContext, useContext } from "react";
import { useParams } from "react-router";
import { useLessonNodeRuns, useLesson, useProjectWorkflow } from "@/features/projects";
import { getStep, type StepDefinition } from "@/entities/workflow";
import type { NodeRun } from "@/shared/api";

/** 工作台上下文：canvas 组件从这里取 projectId/lessonId/step/nodeRun。 */
export interface WorkbenchContextValue {
  projectId: string;
  lessonId: string;
  stepKey: string;
}

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export const WorkbenchProvider = WorkbenchContext.Provider;

export function useWorkbench(): WorkbenchContextValue {
  const ctx = useContext(WorkbenchContext);
  const params = useParams();
  if (ctx) return ctx;
  return {
    projectId: params.projectId ?? "",
    lessonId: params.lessonId ?? "",
    stepKey: params.stepKey ?? "",
  };
}

/** 当前步骤对应的节点运行（rail 数据共享同一查询）。 */
export function useStepNodeRun(): {
  step: StepDefinition | undefined;
  nodeRun: NodeRun | null;
  isPending: boolean;
} {
  const { lessonId, stepKey } = useWorkbench();
  const step = getStep(stepKey);
  const { data: nodeRuns, isPending } = useLessonNodeRuns(lessonId);
  const nodeRun = step?.nodeKey
    ? (nodeRuns?.find((run) => run.node_key === step.nodeKey) ?? null)
    : null;
  return { step, nodeRun, isPending };
}

export { useLesson, useProjectWorkflow };
