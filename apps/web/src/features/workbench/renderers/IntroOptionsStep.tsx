import * as Tabs from "@radix-ui/react-tabs";
import { ArrowRight, Check, ChevronRight, Clock3, Edit3, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { createTopicIntroOptions, introOptions } from "@/features/intro-options/data";
import type { IntroCategory, IntroOption } from "@/features/intro-options/model";
import { markIntroDependentsStale } from "@/features/intro-options/invalidateDependents";
import {
  adoptPreviewedIntroOption,
  getIntroOptionRevision,
  getPreviewedIntroOptionRevision,
  isPreviewAdopted,
  previewIntroOption,
  readIntroOptionsDraft,
  resolveIntroOption,
  returnToAdoptedIntroOption,
} from "@/features/intro-options/state";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { requiredItem } from "@/shared/lib/requiredItem";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { demoProjectId } from "@/shared/data/mockData";

const categories: Array<{ value: "all" | IntroCategory; label: string }> = [
  { value: "all", label: "全部 9 套" },
  { value: "science", label: "科普" },
  { value: "application", label: "应用" },
  { value: "story", label: "故事" },
];

function OptionCard({
  active,
  adopted,
  onSelect,
  option,
}: {
  active: boolean;
  adopted: boolean;
  onSelect: () => void;
  option: IntroOption;
}) {
  const categoryLabel =
    option.category === "science" ? "科普" : option.category === "application" ? "应用" : "故事";
  return (
    <button
      aria-label={`选择${categoryLabel}方案：${option.title}`}
      aria-pressed={active}
      className={`w-full rounded-[var(--sh-radius-md)] border p-2.5 text-left transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 sm:p-3 ${active ? "border-[var(--sh-brand-500)] bg-[var(--sh-brand-50)] shadow-[var(--sh-shadow-card)]" : "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] hover:border-[var(--sh-brand-300)]"}`}
      onClick={onSelect}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="rounded-full bg-[var(--sh-surface-elevated)] px-2.5 py-1 text-xs font-semibold text-[var(--sh-brand-600)]">
          {categoryLabel}
        </span>
        <strong className="text-base text-[var(--sh-brand-600)] sm:text-lg">
          {option.score}
          <span className="ml-0.5 text-xs font-medium text-[var(--sh-ink-faint)]">分</span>
        </strong>
      </div>
      <h3 className="mt-1.5 text-sm font-semibold text-[var(--sh-ink-strong)] sm:mt-2 sm:text-base">
        {option.title}
      </h3>
      <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--sh-ink-muted)] sm:text-sm lg:max-xl:hidden">
        {option.concept}
      </p>
      <div className="mt-1.5 flex items-center justify-between text-[11px] text-[var(--sh-ink-faint)] sm:mt-2 sm:text-xs">
        <span className="flex items-center gap-1">
          <Clock3 aria-hidden="true" className="size-3.5" />约 {option.duration} 秒
        </span>
        {adopted ? (
          <span className="flex items-center gap-1 font-semibold text-[var(--sh-success-strong)]">
            <Check aria-hidden="true" className="size-3.5" />
            当前采用
          </span>
        ) : (
          <span className="flex items-center gap-1 font-semibold text-[var(--sh-brand-600)]">
            查看详情
            <ChevronRight aria-hidden="true" className="size-3.5" />
          </span>
        )}
      </div>
    </button>
  );
}

export function IntroOptionsStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const availableOptions = useMemo(
    () =>
      projectId === demoProjectId || !project
        ? introOptions
        : createTopicIntroOptions(project.knowledge_point),
    [project, projectId],
  );
  const { openContextDrawer } = useWorkbenchUi();
  const [filter, setFilter] = useState<"all" | IntroCategory>("all");
  const draftKey = `project:${projectId}:lesson:${lessonId}:intro-options`;
  const defaultOption = requiredItem(availableOptions, 0, "默认课堂导入方案");
  const stored = readIntroOptionsDraft(runtime.drafts[draftKey]?.value, defaultOption.key);
  const selectedBase =
    availableOptions.find((option) => option.key === stored.previewKey) ?? defaultOption;
  const selected = resolveIntroOption(
    selectedBase,
    stored,
    getPreviewedIntroOptionRevision(stored),
  );
  const adoptedBase = availableOptions.find((option) => option.key === stored.adoptedKey);
  const hasAdoptedOption = adoptedBase !== undefined;
  const previewIsAdopted = isPreviewAdopted(stored);
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:intro-options`];
  const nodeApproved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  const approved = nodeApproved && previewIsAdopted;
  const savePreview = (option: IntroOption) => {
    const next = previewIntroOption(stored, option.key);
    saveMockDraft(draftKey, next, {
      lessonId,
      nodeKey: "intro-options",
      projectId,
    });
    updateMockNodeState(projectId, lessonId, "intro-options", {
      stale_reason: null,
      status: isPreviewAdopted(next) ? "approved" : "review_required",
      title: "选择课堂导入",
    });
  };
  const returnToAdoptedSelection = () => {
    const next = returnToAdoptedIntroOption(stored);
    saveMockDraft(draftKey, next, {
      lessonId,
      nodeKey: "intro-options",
      projectId,
    });
    if (isPreviewAdopted(next)) {
      updateMockNodeState(projectId, lessonId, "intro-options", {
        stale_reason: null,
        status: "approved",
        title: "选择课堂导入",
      });
    }
  };
  const adoptSelection = () => {
    const next = adoptPreviewedIntroOption(stored);
    const changed =
      stored.adoptedKey !== next.adoptedKey || stored.adoptedRevision !== next.adoptedRevision;
    saveMockDraft(draftKey, next, { lessonId, nodeKey: "intro-options", projectId });
    updateMockNodeState(projectId, lessonId, "intro-options", {
      stale_reason: null,
      status: "approved",
      title: "选择课堂导入",
    });
    if (changed) markIntroDependentsStale(runtime, projectId, lessonId);
  };
  const visible = useMemo(
    () =>
      filter === "all"
        ? availableOptions
        : availableOptions.filter((option) => option.category === filter),
    [availableOptions, filter],
  );

  return (
    <WorkbenchPageFrame width="wide">
      <FocusPageHeader
        action={
          approved ? (
            <Button asChild size="md">
              <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/master-script`}>
                编写母版剧本
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          ) : (
            <Button className="hidden md:inline-flex" onClick={adoptSelection} size="md">
              <Check aria-hidden="true" />
              {hasAdoptedOption ? "改用这套方案" : "采用这套方案"}
            </Button>
          )
        }
        eyebrow="当前要做：从三类九套中选择课堂导入"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title="课堂导入设计"
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <section>
          <Tabs.Root
            onValueChange={(value) => setFilter(value as "all" | IntroCategory)}
            value={filter}
          >
            <Tabs.List
              aria-label="方案类别"
              className="mb-2 inline-flex rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-1"
            >
              {categories.map((category) => (
                <Tabs.Trigger
                  className="min-h-8 rounded-md px-3 text-sm font-medium text-[var(--sh-ink-muted)] data-[state=active]:bg-[var(--sh-surface-elevated)] data-[state=active]:text-[var(--sh-ink-strong)] data-[state=active]:shadow-sm"
                  key={category.value}
                  value={category.value}
                >
                  {category.label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
          </Tabs.Root>
          <div
            className="sticky top-[calc(var(--sh-topbar-height)+52px)] z-10 mb-2 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-2.5 shadow-[var(--sh-shadow-card)] xl:hidden"
            data-testid="intro-selected-summary"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-[var(--sh-brand-600)]">
                  {previewIsAdopted ? "当前采用" : "正在预览"} · {selected.score} 分
                </p>
                <h2 className="mt-1 truncate font-semibold text-[var(--sh-ink-strong)]">
                  {selected.title}
                </h2>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {!previewIsAdopted && adoptedBase ? (
                  <Button onClick={returnToAdoptedSelection} size="sm" variant="quiet">
                    <RotateCcw aria-hidden="true" />
                    返回当前方案
                  </Button>
                ) : null}
                <button
                  aria-label="编辑当前方案"
                  className="grid size-9 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"
                  onClick={() => openContextDrawer("prompt")}
                  type="button"
                >
                  <Edit3 aria-hidden="true" className="size-4" />
                </button>
              </div>
            </div>
            <p className="mt-1 line-clamp-1 text-sm leading-5 text-[var(--sh-ink-muted)]">
              {selected.concept}
            </p>
            {!previewIsAdopted ? (
              <Button className="mt-2 w-full md:hidden" onClick={adoptSelection} size="sm">
                <Check aria-hidden="true" />
                {hasAdoptedOption ? "改用这套方案" : "采用这套方案"}
              </Button>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-3">
            {visible.map((option) => {
              const active = selected.key === option.key;
              const latestRevision = getIntroOptionRevision(stored, option.key);
              return (
                <OptionCard
                  active={active}
                  adopted={
                    stored.adoptedKey === option.key &&
                    (active ? previewIsAdopted : stored.adoptedRevision === latestRevision)
                  }
                  key={option.key}
                  onSelect={() => savePreview(option)}
                  option={active ? selected : resolveIntroOption(option, stored, latestRevision)}
                />
              );
            })}
          </div>
        </section>
        <aside
          className="hidden h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 shadow-[var(--sh-shadow-card)] xl:sticky xl:top-[calc(var(--sh-topbar-height)+64px)] xl:block xl:max-h-[calc(100dvh-var(--sh-topbar-height)-112px)] xl:overflow-y-auto"
          data-testid="intro-details-panel"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--sh-brand-600)]">
                {previewIsAdopted ? "当前采用" : "正在预览"} · 约 {selected.duration} 秒
              </p>
              <h2 className="mt-1 text-xl font-bold text-[var(--sh-ink-strong)]">
                {selected.title}
              </h2>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {!previewIsAdopted && adoptedBase ? (
                <Button onClick={returnToAdoptedSelection} size="sm" variant="quiet">
                  <RotateCcw aria-hidden="true" />
                  返回当前方案
                </Button>
              ) : null}
              <button
                aria-label="编辑方案"
                className="grid size-10 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"
                onClick={() => openContextDrawer("prompt")}
                type="button"
              >
                <Edit3 aria-hidden="true" className="size-4" />
              </button>
            </div>
          </div>
          <div className="mt-4 space-y-4 text-sm leading-6">
            <p className="text-[var(--sh-ink-default)]">{selected.concept}</p>
            <p className="border-y border-[var(--sh-line-subtle)] py-3 text-[var(--sh-ink-muted)]">
              {selected.hook}
            </p>
            <section className="border-l-2 border-[var(--sh-brand-400)] bg-[var(--sh-brand-50)] px-3 py-2.5">
              <p className="text-xs font-semibold text-[var(--sh-brand-700)]">课堂从这个问题开始</p>
              <p className="mt-1 font-medium text-[var(--sh-ink-strong)]">
                {selected.firstQuestion}
              </p>
            </section>
          </div>
        </aside>
      </div>
    </WorkbenchPageFrame>
  );
}
