import { Check, ChevronLeft, CircleAlert, PackageOpen, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { SaveToProjectDialog } from "@/features/save-to-project/SaveToProjectDialog";
import {
  createTopicVideoAssets,
  demoVideoAssets,
  demoVideoTitle,
} from "@/features/workbench/lib/videoContent";
import {
  createAssetsFromApprovedStory,
  getApprovedVideoTitle,
} from "@/features/workbench/lib/videoWorkflow";
import type { VideoAsset } from "@/features/workbench/lib/videoContent";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { markVideoAssetsDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import {
  createMockTask,
  saveMockDraft,
  updateMockNodeState,
  useMockRuntime,
} from "@/shared/api/mockClient";
import { saveMockResult, type MockSavedResult } from "@/shared/api/mocks/savedResults";
import { Button } from "@/shared/ui/Button";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { requiredItem } from "@/shared/lib/requiredItem";
import { demoProjectId } from "@/shared/data/mockData";

type BatchStatus = "approved" | "failed" | "review_required";

type BatchItem = {
  detail: string;
  status: BatchStatus;
  title: string;
};

function createBatchItems(knowledgePoint: string, demo: boolean): BatchItem[] {
  const assets = demo ? demoVideoAssets : createTopicVideoAssets(knowledgePoint);
  return assets.map((asset, index) => ({
    detail: asset.type,
    status:
      asset.status === "ready"
        ? "approved"
        : index === assets.length - 1
          ? "failed"
          : "review_required",
    title: asset.title,
  }));
}

function createBatchItemsFromAssets(assets: VideoAsset[]): BatchItem[] {
  return assets.map((asset, index) => ({
    detail: asset.type,
    status:
      asset.status === "ready"
        ? "approved"
        : index === assets.length - 1
          ? "failed"
          : "review_required",
    title: asset.title,
  }));
}

type SavedBatchState = {
  selected: number;
  selectedCandidate: number;
  statuses: BatchStatus[];
  adopted: boolean;
  saved: boolean;
  savedItems: number[];
  resultIds: Record<string, string>;
  modification: string;
  message: string;
  savedTarget?: string;
};

export function CreationBatchPage() {
  const {
    batchId = "mock-batch",
    lessonId: routeLessonId,
    projectId: routeProjectId,
  } = useParams();
  const [searchParams] = useSearchParams();
  const runtime = useMockRuntime();
  const sourcePayload = batchId.startsWith("video-assets-")
    ? batchId.slice("video-assets-".length)
    : undefined;
  const [sourceProjectFromBatch, sourceLessonFromBatch] = sourcePayload?.split("--lesson--") ?? [];
  const requestedSourceProjectId =
    routeProjectId ?? searchParams.get("sourceProjectId") ?? undefined;
  const sourceProjectMismatch = Boolean(
    sourceProjectFromBatch &&
    requestedSourceProjectId &&
    sourceProjectFromBatch !== requestedSourceProjectId,
  );
  const sourceProjectCandidateId = sourceProjectFromBatch ?? requestedSourceProjectId;
  const sourceProject = runtime.projects.find((project) => project.id === sourceProjectCandidateId);
  const requestedSourceLessonId = routeLessonId ?? searchParams.get("lessonId") ?? undefined;
  const sourceLessonMismatch = Boolean(
    sourceLessonFromBatch &&
    requestedSourceLessonId &&
    sourceLessonFromBatch !== requestedSourceLessonId,
  );
  const sourceLessonId = sourceLessonFromBatch ?? requestedSourceLessonId;
  const sourceLessonValid =
    sourceProject &&
    sourceLessonId &&
    getApprovedProjectLessons(runtime, sourceProject.id).some(
      (lesson) => lesson.id === sourceLessonId,
    );
  const hasSourceContext = Boolean(
    sourceProjectFromBatch || requestedSourceProjectId || sourceLessonId,
  );
  const sourceContextInvalid =
    hasSourceContext &&
    (sourceProjectMismatch || sourceLessonMismatch || !sourceProject || !sourceLessonValid);
  const sourceProjectId = sourceContextInvalid ? undefined : sourceProject?.id;
  const demo = sourceProjectId === demoProjectId || !sourceProject;
  const topic = sourceProject?.knowledge_point ?? "本课知识点";
  const videoTitle = demo
    ? demoVideoTitle
    : sourceProjectId && sourceLessonId
      ? getApprovedVideoTitle(runtime, sourceProjectId, sourceLessonId)
      : topic;
  const approvedStoryAssets =
    sourceProjectId && sourceLessonId
      ? createAssetsFromApprovedStory(runtime, sourceProjectId, sourceLessonId)
      : null;
  const batchItems = demo
    ? createBatchItems(topic, true)
    : approvedStoryAssets
      ? createBatchItemsFromAssets(approvedStoryAssets)
      : createBatchItems(topic, false);
  const stateKey = `creation-batch:${batchId}:state`;
  const approvedAssetsKey =
    sourceProjectId && sourceLessonId
      ? `project:${sourceProjectId}:lesson:${sourceLessonId}:video-assets:approved`
      : undefined;
  const stored = runtime.drafts[stateKey]?.value as Partial<SavedBatchState> | undefined;
  const [batchState, setBatchState] = useState<SavedBatchState>(() => ({
    adopted: stored?.adopted === true,
    message: typeof stored?.message === "string" ? stored.message : "",
    modification: typeof stored?.modification === "string" ? stored.modification : "",
    saved: stored?.saved === true,
    savedItems: Array.isArray(stored?.savedItems)
      ? stored.savedItems.filter((item): item is number => typeof item === "number")
      : [],
    resultIds: stored?.resultIds && typeof stored.resultIds === "object" ? stored.resultIds : {},
    savedTarget: typeof stored?.savedTarget === "string" ? stored.savedTarget : undefined,
    selected: typeof stored?.selected === "number" ? stored.selected : 2,
    selectedCandidate: typeof stored?.selectedCandidate === "number" ? stored.selectedCandidate : 0,
    statuses:
      Array.isArray(stored?.statuses) && stored.statuses.length === batchItems.length
        ? stored.statuses
        : batchItems.map((batchItem) => batchItem.status),
  }));
  const batchStateRef = useRef(batchState);
  const [saveOpen, setSaveOpen] = useState(false);
  const saveTriggerRef = useRef<HTMLButtonElement>(null);
  const [modificationOpen, setModificationOpen] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const updateBatch = (patch: Partial<SavedBatchState>) => {
    const next = { ...batchStateRef.current, ...patch };
    saveMockDraft(stateKey, next, {
      lessonId: sourceLessonId,
      nodeKey: "video-assets",
      projectId: sourceProjectId,
    });
    batchStateRef.current = next;
    setBatchState(next);
  };
  const {
    adopted,
    message,
    modification,
    saved,
    savedItems,
    resultIds,
    savedTarget,
    selected,
    selectedCandidate,
    statuses,
  } = batchState;
  const baseItem = batchItems[selected] ?? requiredItem(batchItems, 0, "默认创作任务");
  const item = { ...baseItem, status: statuses[selected] ?? baseItem.status };
  const nextAction =
    item.status === "failed"
      ? "这张画面需要调整。先点击“重新制作这张”，做好后再挑一张。"
      : !adopted
        ? "先比较下面三张作品，选中最合适的一张，再点击“就用这张”。"
        : !saved
          ? sourceProjectId && sourceLessonId
            ? "选好后点击“就用这张”，系统会自动保存到当前项目。"
            : "这张已经选好了。下一步点击右上角“保存到项目”。"
          : sourceProjectId && sourceLessonId
            ? "这张已经自动保存到当前项目，可以继续处理左侧的其他画面。"
            : "这张已经放进项目，可以继续查看左侧的其他画面。";
  const preserveApprovedAssetsBaseline = () => {
    if (
      !approvedAssetsKey ||
      !sourceProjectId ||
      !sourceLessonId ||
      runtime.drafts[approvedAssetsKey] ||
      runtime.nodeStates[`${sourceProjectId}:${sourceLessonId}:video-assets`]?.status !== "approved"
    ) {
      return;
    }
    saveMockDraft(
      approvedAssetsKey,
      { resultIds },
      { lessonId: sourceLessonId, nodeKey: "video-assets", projectId: sourceProjectId },
    );
  };
  const retrySelected = () => {
    preserveApprovedAssetsBaseline();
    const nextStatuses = statuses.map((status, index) =>
      index === selected ? "review_required" : status,
    );
    const nextResultIds = Object.fromEntries(
      Object.entries(resultIds).filter(([key]) => key !== String(selected)),
    );
    updateBatch({
      adopted: false,
      message: "这张已经重新做好，请从三张作品里挑一张。",
      saved: false,
      savedItems: savedItems.filter((index) => index !== selected),
      resultIds: nextResultIds,
      savedTarget: undefined,
      selectedCandidate: 0,
      statuses: nextStatuses,
    });
    if (sourceProjectId && sourceLessonId) {
      updateMockNodeState(sourceProjectId, sourceLessonId, "video-assets", {
        stale_reason: null,
        status: "review_required",
        title: "制作镜头图片",
      });
    }
  };
  const handleSavedResult = (savedResult: MockSavedResult) => {
    const projectTitle = runtime.projects.find(
      (project) => project.id === savedResult.projectId,
    )?.title;
    const countsForSource = hasSourceContext
      ? savedResult.projectId === sourceProjectId &&
        savedResult.slotKey === `video.asset.${batchId}.${String(selected)}`
      : true;
    const nextStatuses = statuses.map((status, index) =>
      countsForSource && index === selected ? "approved" : status,
    );
    const nextSavedItems = countsForSource ? [...new Set([...savedItems, selected])] : savedItems;
    const nextResultIds = countsForSource
      ? { ...resultIds, [String(selected)]: savedResult.resultId }
      : resultIds;
    const allAssetsApproved = nextStatuses.every((status) => status === "approved");
    updateBatch({
      message:
        sourceProjectId && sourceLessonId
          ? "作品已自动保存到当前项目。"
          : "作品已经保存，可在目标项目的素材与成果中查看。",
      adopted: countsForSource,
      saved: true,
      savedItems: nextSavedItems,
      resultIds: nextResultIds,
      savedTarget: `${projectTitle ?? "目标项目"} · ${savedResult.slotLabel}`,
      statuses: nextStatuses,
    });
    if (countsForSource && sourceProjectId && sourceLessonId) {
      const currentApprovedAssetsKey = `project:${sourceProjectId}:lesson:${sourceLessonId}:video-assets:approved`;
      const previousApproved = runtime.drafts[currentApprovedAssetsKey]?.value as
        { resultIds?: Record<string, string> } | undefined;
      if (
        allAssetsApproved &&
        JSON.stringify(previousApproved?.resultIds ?? {}) !== JSON.stringify(nextResultIds)
      ) {
        markVideoAssetsDependentsStale(runtime, sourceProjectId, sourceLessonId);
      }
      if (allAssetsApproved) {
        saveMockDraft(
          currentApprovedAssetsKey,
          { resultIds: nextResultIds },
          { lessonId: sourceLessonId, nodeKey: "video-assets", projectId: sourceProjectId },
        );
      }
      updateMockNodeState(sourceProjectId, sourceLessonId, "video-assets", {
        stale_reason: null,
        status: allAssetsApproved ? "approved" : "review_required",
        title: "制作镜头图片",
      });
    }
  };
  const saveSelectedToSourceProject = () => {
    if (!sourceProjectId || !sourceLessonId) return;
    handleSavedResult(
      saveMockResult({
        lessonLabel: "当前课时",
        preview: { candidate: selectedCandidate, generation: 0, ratio: "1:1" },
        projectId: sourceProjectId,
        replaceMode: "replace",
        resultId: `batch-${batchId}-item-${String(selected)}-candidate-${String(selectedCandidate + 1)}`,
        slotKey: `video.asset.${batchId}.${String(selected)}`,
        slotLabel: `${item.title}（视频画面素材）`,
        title: `${item.title} · 作品 ${String(selectedCandidate + 1)}`,
        type: "image",
      }),
    );
  };
  return (
    <div className="flex min-h-[calc(100dvh-var(--sh-topbar-height))] flex-col bg-[var(--sh-surface-canvas)]">
      <header className="flex min-h-14 items-center gap-3 border-b border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4">
        <Link
          aria-label={sourceProjectId && sourceLessonId ? "返回项目工作台" : "返回创作中心"}
          className="inline-grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"
          to={
            sourceProjectId && sourceLessonId
              ? `/app/projects/${sourceProjectId}/lessons/${sourceLessonId}/work/video-assets`
              : "/app/creation"
          }
        >
          <ChevronLeft aria-hidden="true" className="size-5" />
        </Link>
        <div>
          <p className="text-xs text-[var(--sh-ink-muted)]">项目里等你继续的作品</p>
          <h1 className="font-semibold text-[var(--sh-ink-strong)]">{videoTitle} · 视频图片资产</h1>
        </div>
        <span className="ml-auto hidden text-xs text-[var(--sh-ink-muted)] sm:block">
          来源：{sourceProject?.title ?? "独立创作"} · {sourceLessonId ? "当前课时" : "待保存"}
        </span>
        {sourceProjectId && sourceLessonId ? (
          saved ? (
            <Button asChild>
              <Link to={`/app/projects/${sourceProjectId}/results`}>查看项目资产</Link>
            </Button>
          ) : null
        ) : (
          <Button
            disabled={!adopted || saved || sourceContextInvalid}
            onClick={() => setSaveOpen(true)}
            ref={saveTriggerRef}
          >
            {saved ? "已保存到项目" : "保存到项目"}
          </Button>
        )}
      </header>
      {sourceContextInvalid ? (
        <div
          className="border-b border-[var(--sh-danger)]/30 bg-[var(--sh-danger-soft)] px-4 py-3 text-sm text-[var(--sh-ink-default)]"
          role="alert"
        >
          这个创作批次的来源项目或课时已经失效，请返回原项目重新打开图片创作台。
        </div>
      ) : null}
      <div className="grid min-h-0 flex-1 md:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="order-2 border-t border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 md:order-1 md:border-r md:border-t-0">
          <div className="mb-3 flex items-center gap-2 px-2 py-1">
            <PackageOpen aria-hidden="true" className="size-4 text-[var(--sh-brand-600)]" />
            <span className="text-sm font-semibold">
              {String(batchItems.length)} 个画面等你完成
            </span>
          </div>
          <div className="space-y-2">
            {batchItems.map((batchItem, index) => (
              <button
                aria-pressed={selected === index}
                className={`w-full rounded-[var(--sh-radius-sm)] border p-3 text-left ${selected === index ? "border-[var(--sh-brand-500)] bg-[var(--sh-brand-50)]" : "border-[var(--sh-line-subtle)]"}`}
                key={batchItem.title}
                onClick={() => {
                  updateBatch({
                    adopted: savedItems.includes(index),
                    message: "",
                    saved: savedItems.includes(index),
                    savedTarget: savedItems.includes(index) ? "已保存的项目位置" : undefined,
                    selected: index,
                    selectedCandidate: 0,
                  });
                  setModificationOpen(false);
                  setPromptOpen(false);
                }}
                type="button"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {batchItem.title}
                  </span>
                  <StatusBadge status={statuses[index] ?? batchItem.status} />
                </div>
                <span className="mt-1 block text-xs text-[var(--sh-ink-muted)]">
                  {batchItem.detail}
                </span>
              </button>
            ))}
          </div>
        </aside>
        <div className="order-1 min-w-0 overflow-y-auto p-4 md:order-2 md:p-6">
          <div className="mx-auto max-w-5xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-[var(--sh-brand-600)]">{item.detail}</p>
                <h2 className="mt-1 text-2xl font-bold text-[var(--sh-ink-strong)]">
                  {item.title}
                </h2>
              </div>
              <StatusBadge status={item.status} />
            </div>
            <div className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] p-4">
              <p className="text-xs font-semibold text-[var(--sh-brand-700)]">接下来</p>
              <p className="mt-1 text-sm leading-6 text-[var(--sh-ink-default)]">{nextAction}</p>
            </div>
            {item.status === "failed" ? (
              <div className="mt-5 flex flex-wrap items-center gap-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-4 text-sm">
                <CircleAlert aria-hidden="true" className="size-5 text-[var(--sh-danger)]" />
                <span className="flex-1 text-[var(--sh-ink-default)]">
                  这张图的主体元素发生粘连，需要单独重新制作，其他图片不会受影响。
                </span>
                <Button onClick={retrySelected} size="sm" variant="secondary">
                  <RefreshCw aria-hidden="true" />
                  重新制作这张
                </Button>
              </div>
            ) : null}
            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,520px)_minmax(260px,1fr)] lg:items-start">
              <div className="rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-stage)] p-4 md:p-5">
                <div className="mx-auto max-w-[420px]">
                  <CreativeResultVisual type="image" variant={selectedCandidate} />
                </div>
              </div>
              <aside className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-card)]">
                <p className="text-xs font-medium text-[var(--sh-brand-600)]">比较作品</p>
                <h3 className="mt-0.5 font-semibold text-[var(--sh-ink-strong)]">
                  选最适合课堂的一张
                </h3>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {[0, 1, 2].map((candidate) => (
                    <button
                      aria-label={`备选作品 ${String(candidate + 1)}`}
                      aria-pressed={selectedCandidate === candidate}
                      className={`min-w-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-1.5 ${candidate === selectedCandidate ? "border-[var(--sh-brand-500)] ring-2 ring-[var(--sh-brand-100)]" : "border-[var(--sh-line-subtle)]"}`}
                      key={candidate}
                      onClick={() => {
                        preserveApprovedAssetsBaseline();
                        updateBatch({
                          adopted: false,
                          message: `已选中作品 ${String(candidate + 1)}`,
                          saved: false,
                          savedItems: savedItems.filter((index) => index !== selected),
                          savedTarget: undefined,
                          selectedCandidate: candidate,
                          statuses: statuses.map((status, index) =>
                            index === selected ? "review_required" : status,
                          ),
                        });
                        if (sourceProjectId && sourceLessonId) {
                          updateMockNodeState(sourceProjectId, sourceLessonId, "video-assets", {
                            stale_reason: null,
                            status: "review_required",
                            title: "制作镜头图片",
                          });
                        }
                      }}
                      type="button"
                    >
                      <CreativeResultVisual loading="lazy" type="image" variant={candidate} />
                      <span className="mt-1 block text-xs font-semibold">作品 {candidate + 1}</span>
                    </button>
                  ))}
                </div>
                <div className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] p-3 text-sm leading-6 text-[var(--sh-ink-default)]">
                  <strong className="text-[var(--sh-brand-700)]">接下来：</strong>
                  满意就选用；还差一点，就把想调整的地方告诉创作台。
                </div>
                <div className="mt-4 grid gap-2">
                  <Button
                    className="w-full"
                    disabled={item.status === "failed" || adopted}
                    onClick={() => {
                      if (sourceProjectId && sourceLessonId) {
                        saveSelectedToSourceProject();
                        return;
                      }
                      updateBatch({
                        adopted: true,
                        message: `已选好作品 ${String(selectedCandidate + 1)}`,
                      });
                    }}
                    size="lg"
                  >
                    <Check aria-hidden="true" />
                    {adopted ? "这张已选好" : "就用这张"}
                  </Button>
                  <Button
                    className="w-full"
                    onClick={() => setModificationOpen((open) => !open)}
                    variant="secondary"
                  >
                    想改一改
                  </Button>
                  <Button
                    className="w-full"
                    onClick={() => setPromptOpen((open) => !open)}
                    variant="quiet"
                  >
                    查看完整创作要求
                  </Button>
                </div>
              </aside>
            </div>
            {modificationOpen ? (
              <section className="mt-5 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4">
                <h3 className="font-semibold text-[var(--sh-ink-strong)]">想怎么改</h3>
                <label className="mt-3 block text-sm font-semibold">
                  说明希望调整的画面
                  <textarea
                    className="mt-2 min-h-24 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] p-3 font-normal"
                    onChange={(event) => updateBatch({ modification: event.target.value })}
                    placeholder={`例如：拉开主体元素的间距，保留与${topic}一致的课堂情境。`}
                    value={modification}
                  />
                </label>
                <Button
                  className="mt-3"
                  disabled={!modification.trim()}
                  onClick={() => {
                    createMockTask({
                      detail: modification.trim(),
                      node_run_id: `${batchId}:${String(selected)}`,
                      progress: 0,
                      project_id: sourceProjectId ?? null,
                      stage: "等待重新制作",
                      status: "queued",
                      title: `${item.title} · 调整画面`,
                    });
                    updateBatch({ message: "已经记下你的要求，当前作品会继续保留。" });
                    setModificationOpen(false);
                  }}
                  size="sm"
                >
                  按要求重新制作
                </Button>
              </section>
            ) : null}
            {promptOpen ? (
              <section
                aria-label="完整创作要求"
                className="mt-5 rounded-[var(--sh-radius-sm)] border border-[var(--sh-brand-100)] bg-[var(--sh-brand-50)] p-4"
              >
                <h3 className="font-semibold text-[var(--sh-ink-strong)]">完整创作要求</h3>
                <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
                  为小学数学课堂制作一张与{topic}有关的教学图片：主体清晰分离，关系准确，
                  画面简洁并保留课堂观察空间；不出现水印、乱码和无关道具。
                </p>
              </section>
            ) : null}
            {message ? (
              <p
                aria-live="polite"
                className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] p-4 text-sm font-semibold text-[var(--sh-brand-700)]"
              >
                {message}
              </p>
            ) : null}
            {saved ? (
              <p className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] p-4 text-sm font-semibold text-[var(--sh-ink-strong)]">
                {sourceProjectId && sourceLessonId ? "已自动保存到" : "已保存到"}“
                {savedTarget ?? sourceProject?.title ?? "目标项目"}
                ”，其他没有选中的作品不会放进项目。
              </p>
            ) : null}
          </div>
        </div>
      </div>
      {!sourceProjectId ? (
        <SaveToProjectDialog
          customSlots={
            sourceProjectId && sourceLessonId
              ? [
                  {
                    accepts: ["image"],
                    key: `video.asset.${batchId}.${String(selected)}`,
                    label: `${item.title}（视频画面素材）`,
                  },
                ]
              : undefined
          }
          lockSourceProject={Boolean(sourceProjectId)}
          onOpenChange={setSaveOpen}
          onSaved={handleSavedResult}
          open={saveOpen}
          result={{
            id: `batch-${batchId}-item-${String(selected)}-candidate-${String(selectedCandidate + 1)}`,
            preview: { candidate: selectedCandidate, generation: 0, ratio: "1:1" },
            title: `${item.title} · 作品 ${String(selectedCandidate + 1)}`,
            type: "image",
            lessonLabel: sourceLessonId ? "当前课时" : "多张作品",
          }}
          returnFocusRef={saveTriggerRef}
          sourceProjectId={sourceProjectId}
        />
      ) : null}
    </div>
  );
}
