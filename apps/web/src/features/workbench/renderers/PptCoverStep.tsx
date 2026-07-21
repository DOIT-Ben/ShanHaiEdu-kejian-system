import { ArrowRight, Check, Download, PencilLine, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PptCoverArtwork, pptCoverOptions } from "@/features/workbench/components/PptCoverArtwork";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { markPptCoverDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { requiredItem } from "@/shared/lib/requiredItem";
import { demoProjectId } from "@/shared/data/mockData";

function CoverVisual({
  candidate,
  demo,
  topic,
}: {
  candidate: { id: number; label: string };
  demo: boolean;
  topic: string;
}) {
  return (
    <PptCoverArtwork demo={demo} variant={candidate.id}>
      <p className="text-[clamp(0.45rem,1.1vw,0.76rem)] font-semibold opacity-70">小学数学课堂</p>
      <p className="mt-[4%] text-[clamp(0.8rem,2.7vw,2rem)] font-bold leading-tight">
        {demo ? "认识百分数" : topic}
      </p>
      <p className="mt-[4%] text-[clamp(0.42rem,1vw,0.74rem)] opacity-70">{candidate.label}</p>
    </PptCoverArtwork>
  );
}

export function PptCoverStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const topic = project?.knowledge_point ?? "本课知识点";
  const demo = projectId === demoProjectId || !project;
  const availableCandidates = demo
    ? pptCoverOptions
    : pptCoverOptions.map((candidate, index) => ({
        ...candidate,
        label: ["教材情境", "图形探究", "课堂发现"][index] ?? candidate.label,
      }));
  const draftKey = `project:${projectId}:lesson:${lessonId}:ppt-cover`;
  const approvedKey = `${draftKey}:approved`;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:ppt-cover`];
  const approved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  const currentSaved = runtime.drafts[draftKey]?.value as { selectedId?: number } | undefined;
  const approvedSaved = runtime.drafts[approvedKey]?.value as { selectedId?: number } | undefined;
  const saved = approved ? approvedSaved : (currentSaved ?? approvedSaved);
  const selectedId = saved?.selectedId ?? 1;
  const [message, setMessage] = useState("");
  const { openContextDrawer } = useWorkbenchUi();
  const selectCover = (nextId: number) => {
    saveMockDraft(draftKey, { selectedId: nextId }, { lessonId, nodeKey: "ppt-cover", projectId });
    updateMockNodeState(projectId, lessonId, "ppt-cover", {
      stale_reason: null,
      status: "review_required",
      title: "设计封面",
    });
  };
  const selected =
    availableCandidates.find((candidate) => candidate.id === selectedId) ??
    requiredItem(availableCandidates, 0, "默认备选封面");
  return (
    <WorkbenchPageFrame width="workspace">
      <FocusPageHeader
        action={
          approved ? (
            <>
              <Button
                onClick={() => {
                  if (!runtime.drafts[approvedKey]) {
                    saveMockDraft(
                      approvedKey,
                      { selectedId },
                      { lessonId, nodeKey: "ppt-cover", projectId },
                    );
                  }
                  updateMockNodeState(projectId, lessonId, "ppt-cover", {
                    status: "review_required",
                    title: "设计封面",
                  });
                  setMessage("已进入重新选择；确认前仍保留当前封面");
                }}
                size="md"
                variant="secondary"
              >
                <PencilLine aria-hidden="true" />
                重新选择封面
              </Button>
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`}>
                  制作 PPT 正文
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          ) : (
            <Button
              onClick={() => {
                if (approvedSaved?.selectedId && approvedSaved.selectedId !== selectedId) {
                  markPptCoverDependentsStale(runtime, projectId, lessonId);
                }
                saveMockDraft(
                  draftKey,
                  { selectedId },
                  { lessonId, nodeKey: "ppt-cover", projectId },
                );
                saveMockDraft(
                  approvedKey,
                  { selectedId },
                  { lessonId, nodeKey: "ppt-cover", projectId },
                );
                updateMockNodeState(projectId, lessonId, "ppt-cover", {
                  stale_reason: null,
                  status: "approved",
                  title: "设计封面",
                });
              }}
              size="md"
            >
              <Check aria-hidden="true" />
              采用这张封面
            </Button>
          )
        }
        eyebrow="当前要做：选择一张 PPT 封面"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={`${demo ? "认识百分数" : topic} · 封面`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-3 space-y-3">
        <section className="flex min-h-0 items-center justify-center rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-stage)] p-3 md:p-4">
          <div
            className="w-full max-w-[min(960px,max(280px,calc((100dvh-450px)*1.7778)))] shadow-[var(--sh-shadow-floating)]"
            data-testid="ppt-cover-preview"
          >
            <CoverVisual candidate={selected} demo={demo} topic={topic} />
          </div>
        </section>
        <aside className="mx-auto w-full max-w-[720px]">
          <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">3 张备选封面</p>
          <div className="mt-2 grid grid-cols-3 gap-2 md:gap-3">
            {availableCandidates.map((candidate) => (
              <button
                aria-label={`选择${candidate.label}`}
                aria-pressed={selectedId === candidate.id}
                className={`min-w-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-1.5 text-left md:p-2 ${selectedId === candidate.id ? "border-[var(--sh-brand-500)] shadow-[var(--sh-shadow-card)]" : "border-[var(--sh-line-subtle)]"}`}
                disabled={approved}
                key={candidate.id}
                onClick={() => {
                  selectCover(candidate.id);
                  setMessage(`已切换到备选封面“${candidate.label}”`);
                }}
                type="button"
              >
                <CoverVisual candidate={candidate} demo={demo} topic={topic} />
                <span className="mt-1.5 block truncate px-1 text-xs font-semibold text-[var(--sh-ink-strong)]">
                  {candidate.label}
                </span>
              </button>
            ))}
          </div>
        </aside>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button disabled={approved} onClick={() => openContextDrawer("prompt")} variant="secondary">
          提出修改
        </Button>
        <Button
          disabled={approved}
          onClick={() => {
            const nextId = (selectedId % availableCandidates.length) + 1;
            selectCover(nextId);
            setMessage("已生成并切换到新的备选封面");
          }}
          variant="quiet"
        >
          <RefreshCw aria-hidden="true" />
          重新生成
        </Button>
        <Button
          onClick={() =>
            downloadExampleFile(
              `${demo ? "认识百分数" : topic}_备选封面${String(selectedId)}.svg`,
              `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#6B5344"/><circle cx="1030" cy="170" r="90" fill="#C98A5C"/><text x="110" y="280" fill="#FFF9F2" font-size="76" font-family="sans-serif" font-weight="700">${(demo ? "认识百分数" : topic).replace(/[&<>"']/g, "")}</text><text x="110" y="370" fill="#E8DCCE" font-size="34" font-family="sans-serif">${selected.label.replace(/[&<>"']/g, "")}</text></svg>`,
              "image/svg+xml;charset=utf-8",
            )
          }
          variant="quiet"
        >
          <Download aria-hidden="true" />
          下载预览
        </Button>
      </div>
      {message ? (
        <p className="mt-3 text-sm font-medium text-[var(--sh-success)]" role="status">
          {message}
        </p>
      ) : null}
    </WorkbenchPageFrame>
  );
}
