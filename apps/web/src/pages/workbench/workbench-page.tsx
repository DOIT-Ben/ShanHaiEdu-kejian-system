import { useCallback, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, Pause, SkipForward, Undo2 } from "lucide-react";
import "@/features/workbench/register-canvases";
import { getNodeCanvas } from "@/features/workbench";
import { useLessonWorkspace, useNodeWorkspace, useNodeTransition, useUpdateNodeInputs } from "@/features/lessons";
import {
  useCostEstimate,
  useCreateBudgetAuthorization,
  useCreateEditedVersion,
  useCreatePromptDraft,
  useModelOptions,
  useNodeItemAction,
  useStartNodeRun,
} from "@/features/runs";
import { useApproveArtifact, useConfirmStale } from "@/features/artifacts";
import { useCancelTask, useProjectTasks, useRetryTask, useTask } from "@/features/tasks";
import { getNodeDef } from "@/entities/workflow/nodes";
import { AppError } from "@/shared/api";
import { formatMinorUnits } from "@/shared/lib/format";
import type { NodeStatus } from "@/shared/lib/status";
import {
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  NodeStatusBadge,
  ScrollArea,
  Spinner,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  toast,
} from "@/shared/ui";
import { AppErrorPanel, ApprovalBar, OutputPanel, PromptEditor, RunControl, TaskDock, ValidationPanel, VersionTimeline, WorkflowRail } from "@/widgets";
import { InputsTab, AssetsTab } from "./inspector-tabs";
import { INSPECTOR_MAX, INSPECTOR_MIN, useWorkbenchUi } from "./workbench-store";

interface FallbackConfirmState {
  itemId: string;
  providerName: string;
  extraCost: number;
}

/** 课时工作台：工作流侧栏 / 画布 / 检查器 / 任务坞 四区布局。 */
export function WorkbenchPage() {
  const { projectId = "", lessonId = "", nodeKey = "" } = useParams();
  const navigate = useNavigate();
  const ui = useWorkbenchUi();

  const lessonWs = useLessonWorkspace(lessonId);
  const nodeWs = useNodeWorkspace(lessonId, nodeKey);
  const modelOptions = useModelOptions(lessonId, nodeKey);

  const updateInputs = useUpdateNodeInputs(lessonId, nodeKey);
  const promptDraft = useCreatePromptDraft(lessonId, nodeKey);
  const estimate = useCostEstimate(lessonId, nodeKey);
  const budgetAuth = useCreateBudgetAuthorization(lessonId, nodeKey);
  const startRun = useStartNodeRun(lessonId, nodeKey, projectId);
  const itemAction = useNodeItemAction(lessonId, nodeKey, projectId);
  const editedVersion = useCreateEditedVersion(lessonId, nodeKey);
  const approve = useApproveArtifact({ lessonId, nodeKey, projectId });
  const confirmStale = useConfirmStale({ lessonId, projectId });
  const transition = useNodeTransition(lessonId, nodeKey);

  const workspace = nodeWs.data;
  const activeTask = useTask(workspace?.active_task_id ?? null);
  const lessonTasks = useProjectTasks(projectId, { lesson_id: lessonId }, { refetchInterval: activeTask.data ? 3000 : 15000 });
  const cancelTask = useCancelTask(projectId);
  const retryTask = useRetryTask(projectId);

  const [fallbackConfirm, setFallbackConfirm] = useState<FallbackConfirmState | null>(null);
  const dragging = useRef(false);

  const onDragStart = useCallback(
    (event: React.PointerEvent) => {
      dragging.current = true;
      const startX = event.clientX;
      const startWidth = ui.inspectorWidth;
      const onMove = (move: PointerEvent) => {
        if (!dragging.current) return;
        ui.setInspectorWidth(startWidth + (startX - move.clientX));
      };
      const onUp = () => {
        dragging.current = false;
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [ui],
  );

  const nodeDef = getNodeDef(nodeKey);
  const latestPrompt = workspace?.prompt_versions[0] ?? null;

  const runItemAction = useCallback(
    (input: { itemId: string; action: Parameters<typeof itemAction.mutate>[0]["action"]; instruction?: string; payload?: Record<string, unknown> }) => {
      itemAction.mutate(input, {
        onError: (error) => {
          if (error instanceof AppError && error.code === "PROVIDER_FALLBACK_CONFIRMATION_REQUIRED") {
            const details = (error.details ?? {}) as { fallback_provider_name?: string; extra_cost_minor_units?: number };
            setFallbackConfirm({
              itemId: input.itemId,
              providerName: details.fallback_provider_name ?? "备用服务",
              extraCost: details.extra_cost_minor_units ?? 0,
            });
          } else {
            toast({ tone: "danger", title: "操作失败", description: error.message });
          }
        },
      });
    },
    [itemAction],
  );

  if (lessonWs.isPending || nodeWs.isPending) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="正在载入工作台…" />
      </div>
    );
  }
  if (lessonWs.isError) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={lessonWs.error} title="课时加载失败" onRetry={() => void lessonWs.refetch()} />
      </div>
    );
  }
  if (nodeWs.isError) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={nodeWs.error} title="节点加载失败" onRetry={() => void nodeWs.refetch()} />
      </div>
    );
  }
  if (!workspace || !lessonWs.data || !nodeDef) return null;

  const Canvas = getNodeCanvas(workspace.output_renderer);
  const nodeStatus = workspace.node.status as NodeStatus;
  const isGenerating = Boolean(activeTask.data && ["queued", "running", "waiting_provider", "downloading"].includes(activeTask.data.status));
  const canRun = !["locked", "blocked", "skipped"].includes(nodeStatus) && !isGenerating && nodeKey !== "delivery";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1">
        <WorkflowRail
          nodes={lessonWs.data.nodes}
          activeNodeKey={nodeKey}
          onSelect={(key) => void navigate(`/app/projects/${projectId}/lessons/${lessonId}/workbench/${key}`)}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          {/* 节点头部 */}
          <header className="flex items-center gap-3 border-b border-line bg-surface-1 px-5 py-3">
            <Button variant="ghost" size="sm" onClick={() => void navigate(`/app/projects/${projectId}/lessons`)} aria-label="返回课时列表">
              <ArrowLeft className="size-4" aria-hidden />
            </Button>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-base font-semibold text-ink-1">{nodeDef.title}</h1>
                <NodeStatusBadge status={nodeStatus} />
              </div>
              <p className="truncate text-xs text-ink-muted">
                {lessonWs.data.lesson.title} · {workspace.description ?? nodeDef.description}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {isGenerating && activeTask.data?.cancellable ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => cancelTask.mutate(activeTask.data!.task_id)}
                  loading={cancelTask.isPending}
                >
                  <Pause className="size-4" aria-hidden />
                  暂停（取消本次生成）
                </Button>
              ) : null}
              {nodeStatus === "skipped" ? (
                <Button size="sm" variant="secondary" onClick={() => transition.mutate({ action: "restore" })} loading={transition.isPending}>
                  <Undo2 className="size-4" aria-hidden />
                  恢复此步骤
                </Button>
              ) : nodeDef.skippable && !["approved", "locked"].includes(nodeStatus) && !isGenerating ? (
                <Button size="sm" variant="ghost" onClick={() => transition.mutate({ action: "skip" })} loading={transition.isPending}>
                  <SkipForward className="size-4" aria-hidden />
                  跳过
                </Button>
              ) : null}
            </div>
          </header>

          {/* 生成控制条 */}
          {canRun && nodeStatus !== "skipped" ? (
            <div className="border-b border-line bg-surface-1 px-5 py-2.5">
              <RunControl
                profiles={modelOptions.data?.profiles ?? []}
                advancedModels={modelOptions.data?.advanced_models ?? []}
                disabled={!latestPrompt}
                disabledReason={!latestPrompt ? "先在右侧「输入」页签保存输入，生成提示词" : null}
                runLabel={workspace.artifact_versions.length > 0 ? "重新生成" : "开始生成"}
                estimating={estimate.isPending}
                starting={startRun.isPending}
                onEstimate={async ({ modelProfile, modelId }) =>
                  estimate.mutateAsync({ promptVersionId: latestPrompt!.prompt_version_id, modelProfile, modelId })
                }
                onStart={({ modelProfile, modelId, budgetAuthorizationId }) => {
                  startRun.mutate(
                    { promptVersionId: latestPrompt!.prompt_version_id, modelProfile, modelId, budgetAuthorizationId },
                    { onError: (error) => toast({ tone: "danger", title: "生成发起失败", description: error.message }) },
                  );
                }}
                onAuthorizeBudget={async ({ estimatedMaxMinorUnits, reason }) => {
                  const auth = await budgetAuth.mutateAsync({ estimated_max_minor_units: estimatedMaxMinorUnits, reason });
                  return { budget_authorization_id: auth.budget_authorization_id };
                }}
              />
            </div>
          ) : null}

          {/* 画布 / 输出面板 */}
          <ScrollArea className="min-h-0 flex-1">
            <div className="p-5">
              <OutputPanel
                workspace={workspace}
                task={activeTask.data ?? null}
                submitting={startRun.isPending}
                onCancelTask={(taskId) => cancelTask.mutate(taskId)}
                onRetryTask={(taskId) => retryTask.mutate(taskId)}
                onConfirmStale={(versionId) =>
                  confirmStale.mutate(versionId, { onSuccess: () => toast({ tone: "success", title: "已确认沿用当前结果" }) })
                }
                onRegenerate={() => ui.setInspectorTab("inputs")}
              >
                {Canvas ? (
                  <Canvas
                    workspace={workspace}
                    projectId={projectId}
                    lessonId={lessonId}
                    nodeKey={nodeKey}
                    onItemAction={runItemAction}
                    itemActionPending={itemAction.isPending}
                    onSaveEdited={(content) =>
                      editedVersion.mutate(
                        { content, base_version_id: workspace.artifact_versions[0]?.artifact_version_id },
                        { onSuccess: () => toast({ tone: "success", title: "已保存为新版本" }) },
                      )
                    }
                    savePending={editedVersion.isPending}
                  />
                ) : null}
              </OutputPanel>
              <div className="mt-4">
                <ApprovalBar
                  workspace={workspace}
                  approving={approve.isPending}
                  revising={promptDraft.isPending || startRun.isPending}
                  onApprove={({ versionId, overrideWarningRuleIds, overrideReason }) =>
                    approve.mutate(
                      { versionId, override_warning_rule_ids: overrideWarningRuleIds, override_reason: overrideReason },
                      {
                        onSuccess: () => toast({ tone: "success", title: "已批准", description: "下游步骤已解锁。" }),
                        onError: (error) => toast({ tone: "danger", title: "批准失败", description: error.message }),
                      },
                    )
                  }
                  onRevise={(instruction) => {
                    promptDraft.mutate(
                      {
                        input_values: workspace.input_values ?? {},
                        revision_instruction: instruction,
                        base_prompt_version_id: latestPrompt?.prompt_version_id,
                      },
                      {
                        onSuccess: (prompt) => {
                          startRun.mutate({ promptVersionId: prompt.prompt_version_id, modelProfile: "recommended" });
                        },
                      },
                    );
                  }}
                />
              </div>
            </div>
          </ScrollArea>
        </main>

        {/* 检查器 */}
        <aside
          className="relative flex shrink-0 flex-col border-l border-line bg-surface-1"
          style={{ width: ui.inspectorWidth }}
          aria-label="节点检查器"
        >
          <div
            role="separator"
            aria-orientation="vertical"
            aria-valuemin={INSPECTOR_MIN}
            aria-valuemax={INSPECTOR_MAX}
            aria-valuenow={ui.inspectorWidth}
            tabIndex={0}
            onPointerDown={onDragStart}
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft") ui.setInspectorWidth(ui.inspectorWidth + 16);
              if (event.key === "ArrowRight") ui.setInspectorWidth(ui.inspectorWidth - 16);
            }}
            className="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize hover:bg-brand/40"
          />
          <Tabs value={ui.inspectorTab} onValueChange={ui.setInspectorTab} className="flex min-h-0 flex-1 flex-col">
            <TabsList className="mx-3 mt-3">
              <TabsTrigger value="inputs">输入</TabsTrigger>
              <TabsTrigger value="prompt">提示词</TabsTrigger>
              <TabsTrigger value="validation">校验</TabsTrigger>
              <TabsTrigger value="versions">版本</TabsTrigger>
              <TabsTrigger value="assets">资产</TabsTrigger>
            </TabsList>
            <ScrollArea className="min-h-0 flex-1">
              <div className="p-3">
                <TabsContent value="inputs">
                  <InputsTab
                    workspace={workspace}
                    saving={updateInputs.isPending || promptDraft.isPending}
                    onSave={(inputValues) => {
                      updateInputs.mutate(
                        { input_values: inputValues, row_version: workspace.input_row_version ?? 1 },
                        {
                          onSuccess: () => {
                            promptDraft.mutate({ input_values: inputValues });
                          },
                          onError: (error) => toast({ tone: "danger", title: "输入保存失败", description: error.message }),
                        },
                      );
                    }}
                    onOpenUpstream={(key) => void navigate(`/app/projects/${projectId}/lessons/${lessonId}/workbench/${key}`)}
                  />
                </TabsContent>
                <TabsContent value="prompt">
                  <PromptEditor
                    versions={workspace.prompt_versions}
                    saving={promptDraft.isPending}
                    onSaveEdited={(editedPrompt, baseVersionId) =>
                      promptDraft.mutate({
                        input_values: workspace.input_values ?? {},
                        edited_prompt: editedPrompt,
                        base_prompt_version_id: baseVersionId ?? undefined,
                      })
                    }
                    onResetDefault={() =>
                      promptDraft.mutate({ input_values: workspace.input_values ?? {}, reset_to_default: true })
                    }
                  />
                </TabsContent>
                <TabsContent value="validation">
                  <ValidationPanel results={workspace.validation_results ?? []} />
                </TabsContent>
                <TabsContent value="versions">
                  <VersionTimeline
                    versions={workspace.artifact_versions}
                    selectedVersionId={workspace.artifact_versions[0]?.artifact_version_id}
                  />
                </TabsContent>
                <TabsContent value="assets">
                  <AssetsTab
                    workspace={workspace}
                    projectId={projectId}
                    saving={updateInputs.isPending}
                    onChangeSelected={(assetIds) =>
                      updateInputs.mutate({
                        input_values: workspace.input_values ?? {},
                        selected_asset_ids: assetIds,
                        row_version: workspace.input_row_version ?? 1,
                      })
                    }
                  />
                </TabsContent>
              </div>
            </ScrollArea>
          </Tabs>
        </aside>
      </div>

      <TaskDock
        tasks={lessonTasks.data ?? []}
        onCancel={(taskId) => cancelTask.mutate(taskId)}
        onRetry={(taskId) => retryTask.mutate(taskId)}
      />

      {/* 备用服务付费确认（单镜头重试触发 409 时） */}
      <Dialog open={fallbackConfirm !== null} onOpenChange={(open) => !open && setFallbackConfirm(null)}>
        <DialogContent
          title="切换备用服务将再次计费"
          description="主服务暂不可用。使用备用服务重试该镜头会产生新的费用，确认后才会执行。"
        >
          {fallbackConfirm ? (
            <div className="space-y-1.5 rounded-control bg-surface-2 px-4 py-3 text-sm">
              <div className="flex justify-between">
                <span className="text-ink-2">备用服务</span>
                <span className="text-ink-1">{fallbackConfirm.providerName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-2">重试新增费用</span>
                <span className="font-medium text-ink-1">{formatMinorUnits(fallbackConfirm.extraCost)}</span>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setFallbackConfirm(null)}>
              暂不重试
            </Button>
            <Button
              onClick={() => {
                if (fallbackConfirm) {
                  runItemAction({
                    itemId: fallbackConfirm.itemId,
                    action: "retry_clip",
                    payload: { use_fallback_provider: true },
                  });
                  setFallbackConfirm(null);
                }
              }}
            >
              确认费用并重试
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
