import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  BookOpen,
  ArrowRight,
  Check,
  CheckCircle2,
  MoreHorizontal,
  PencilLine,
  Plus,
  Replace,
  Settings2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PercentSlidePreview } from "@/features/home/components/PercentSlidePreview";
import { PptCoverArtwork } from "@/features/workbench/components/PptCoverArtwork";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { getApprovedDraftValue } from "@/features/workbench/lib/approvedDraft";
import { readPptOutlinePages, type PptOutlinePage } from "@/features/workbench/lib/pptOutline";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import {
  getMockDraft,
  saveMockDraft,
  updateMockNodeState,
  useMockRuntime,
} from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { IconButton } from "@/shared/ui/IconButton";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";
import { requiredItem } from "@/shared/lib/requiredItem";

const demoPageLabels = [
  "封面",
  "生活中的百分数",
  "百格图里的 37%",
  "百分数表示什么",
  "分数与百分数",
  "我会判断",
  "课堂回望",
];

function createTopicPageLabels(topic: string) {
  return [
    "封面",
    `走近${topic}`,
    `观察${topic}`,
    `解释${topic}`,
    "交流与辨析",
    "课堂练习",
    "课堂回望",
  ];
}

function createFallbackOutlinePages(labels: string[]): PptOutlinePage[] {
  return labels.map((title, index) => ({
    id: String(index),
    pageType: index === 0 ? "cover" : index === labels.length - 1 ? "summary" : "content",
    source: "默认页面安排",
    task: index === 0 ? "建立课题印象" : index === labels.length - 1 ? "回顾本课" : "完成课堂任务",
    title,
  }));
}

type SavedPptPages = {
  approved: boolean;
  page: number;
  pageId?: string;
  content: Record<string, string>;
  pageRevisions: Record<string, number>;
  regeneratedPages: number[];
};

function createDefaultContent(
  topic: string,
  demo: boolean,
  coverPageId: string,
): SavedPptPages["content"] {
  return {
    [`page-${coverPageId}-subtitle`]: demo
      ? "从生活中的数据，看见整体与部分"
      : "从课堂问题出发，先观察，再表达，再验证",
    [`page-${coverPageId}-title`]: demo ? "认识百分数" : topic,
  };
}

function regeneratedContent(
  pageId: string,
  pageType: PptOutlinePage["pageType"],
  revision: number,
  topic: string,
  demo: boolean,
) {
  if (pageType === "cover") {
    return {
      [`page-${pageId}-subtitle`]:
        demo && revision % 2 !== 0
          ? "从果汁标签出发，读懂整体与部分"
          : `从课堂问题出发，探究${topic}`,
    };
  }
  if (demo && (pageId === "2" || pageId === "grid")) return {};
  return {
    [`page-${pageId}-body`]:
      demo && revision % 2 === 0
        ? "先观察图中的整体与部分，再用一句话解释这个百分数"
        : `先观察与${topic}有关的线索，再用一句话说明自己的判断理由`,
  };
}

function readPageContent(
  content: Record<string, string>,
  pageId: string,
  pageIndex: number,
  field: "body" | "subtitle" | "title",
) {
  return content[`page-${pageId}-${field}`] ?? content[`page-${String(pageIndex)}-${field}`];
}

export function PptPagesStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const topic = project?.knowledge_point ?? "本课知识点";
  const demo = projectId === demoProjectId || !project;
  const approvedOutline = readPptOutlinePages(
    getApprovedDraftValue(runtime, projectId, lessonId, "ppt-outline"),
  );
  const outlinePages =
    approvedOutline ??
    createFallbackOutlinePages(demo ? demoPageLabels : createTopicPageLabels(topic));
  const pageLabels = outlinePages.map((outlinePage) => outlinePage.title);
  const draftKey = `project:${projectId}:lesson:${lessonId}:ppt-pages`;
  const approvedDraftKey = `${draftKey}:approved`;
  const currentStored = runtime.drafts[draftKey]?.value as Partial<SavedPptPages> | undefined;
  const approvedStored = getApprovedDraftValue<Partial<SavedPptPages>>(
    runtime,
    projectId,
    lessonId,
    "ppt-pages",
  );
  const stored = currentStored ?? approvedStored;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:ppt-pages`];
  const stale = nodeState?.status === "stale";
  const storedPageById = stored?.pageId
    ? outlinePages.findIndex((outlinePage) => outlinePage.id === stored.pageId)
    : -1;
  const page =
    storedPageById >= 0
      ? storedPageById
      : typeof stored?.page === "number" && stored.page >= 0 && stored.page < pageLabels.length
        ? stored.page
        : Math.max(0, Math.min(2, pageLabels.length - 1));
  const currentPage = requiredItem(outlinePages, page, "当前 PPT 页面");
  const coverPage =
    outlinePages.find((outlinePage) => outlinePage.pageType === "cover") ??
    requiredItem(outlinePages, 0, "PPT封面");
  const coverDraft = getApprovedDraftValue<{ selectedId?: number }>(
    runtime,
    projectId,
    lessonId,
    "ppt-cover",
  );
  const coverVariant = coverDraft?.selectedId ?? 1;
  const approved = stored?.approved === true && nodeState?.status === "approved";
  const content = {
    ...createDefaultContent(topic, demo, coverPage.id),
    ...(stored?.content ?? {}),
  };
  const pageRevisions = stored?.pageRevisions ?? {};
  const regeneratedPages = Array.isArray(stored?.regeneratedPages) ? stored.regeneratedPages : [];
  const pageRevision = pageRevisions[currentPage.id] ?? 0;
  const [mobilePagesOpen, setMobilePagesOpen] = useState(false);
  const [pendingRegenerations, setPendingRegenerations] = useState(0);
  const [saveState, setSaveState] = useState("已保存");
  const regenerationTimers = useRef(new Set<number>());
  const { openContextDrawer } = useWorkbenchUi();
  useEffect(
    () => () => {
      regenerationTimers.current.forEach((timer) => window.clearTimeout(timer));
      regenerationTimers.current.clear();
    },
    [],
  );
  const persist = (patch: Partial<SavedPptPages>) => {
    const latest = getMockDraft<Partial<SavedPptPages>>(draftKey)?.value;
    return saveMockDraft(
      draftKey,
      {
        approved: latest?.approved ?? approved,
        content: { ...content, ...(latest?.content ?? {}) },
        page: latest?.page ?? page,
        pageId: latest?.pageId ?? currentPage.id,
        pageRevisions: latest?.pageRevisions ?? pageRevisions,
        regeneratedPages: latest?.regeneratedPages ?? regeneratedPages,
        ...patch,
      },
      { lessonId, nodeKey: "ppt-pages", projectId },
    );
  };
  const selectPage = (nextPage: number) =>
    persist({ page: nextPage, pageId: outlinePages[nextPage]?.id });
  const saveContent = (key: string, value: string) => {
    const latestContent = getMockDraft<Partial<SavedPptPages>>(draftKey)?.value.content;
    persist({ content: { ...content, ...(latestContent ?? {}), [key]: value } });
    setSaveState("已保存");
  };
  const regeneratePage = () => {
    const currentPageIndex = page;
    const currentPageId = currentPage.id;
    const currentPageType = currentPage.pageType;
    setSaveState("正在重新生成");
    setPendingRegenerations((count) => count + 1);
    const timer = window.setTimeout(() => {
      regenerationTimers.current.delete(timer);
      const latestRegeneratedPages =
        getMockDraft<Partial<SavedPptPages>>(draftKey)?.value.regeneratedPages ?? [];
      const latestDraft = getMockDraft<Partial<SavedPptPages>>(draftKey)?.value;
      const nextRevision = (latestDraft?.pageRevisions?.[currentPageId] ?? 0) + 1;
      persist({
        content: {
          ...content,
          ...(latestDraft?.content ?? {}),
          ...regeneratedContent(currentPageId, currentPageType, nextRevision, topic, demo),
        },
        pageRevisions: {
          ...pageRevisions,
          ...(latestDraft?.pageRevisions ?? {}),
          [currentPageId]: nextRevision,
        },
        regeneratedPages: [...new Set([...latestRegeneratedPages, currentPageIndex])],
      });
      setPendingRegenerations((count) => Math.max(0, count - 1));
      setSaveState("已重新生成并保存");
    }, 500);
    regenerationTimers.current.add(timer);
  };
  return (
    <WorkbenchPageFrame width="wide">
      <FocusPageHeader
        action={
          approved ? (
            <>
              <Button
                aria-label="重新编辑 PPT"
                onClick={() => {
                  if (!runtime.drafts[approvedDraftKey]) {
                    saveMockDraft(
                      approvedDraftKey,
                      { ...stored, approved: true },
                      { lessonId, nodeKey: "ppt-pages", projectId },
                    );
                  }
                  persist({ approved: false });
                  updateMockNodeState(projectId, lessonId, "ppt-pages", {
                    status: "review_required",
                    title: "制作 PPT 正文",
                  });
                }}
                size="md"
                variant="secondary"
              >
                <PencilLine aria-hidden="true" />
                重新编辑
              </Button>
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-export`}>
                  检查并导出
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          ) : (
            <Button
              disabled={pendingRegenerations > 0}
              onClick={() => {
                const approvedDraft = persist({ approved: true });
                saveMockDraft(approvedDraftKey, approvedDraft.value, {
                  lessonId,
                  nodeKey: "ppt-pages",
                  projectId,
                });
                updateMockNodeState(projectId, lessonId, "ppt-pages", {
                  stale_reason: null,
                  status: "approved",
                  title: "制作 PPT 正文",
                });
              }}
              size="md"
            >
              <Check aria-hidden="true" />
              {pendingRegenerations > 0 ? "正在生成页面" : "确认整套 PPT"}
            </Button>
          )
        }
        eyebrow="当前要做：检查并修改 PPT 正文"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={`${demo ? "认识百分数" : topic} · ${String(pageLabels.length)} 页`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-3 grid gap-3 lg:h-[max(420px,min(680px,calc(100dvh-255px)))] lg:min-h-0 lg:grid-cols-[116px_minmax(0,1fr)] lg:overflow-hidden">
        <aside className="hidden space-y-1.5 overflow-y-auto lg:block">
          {outlinePages.map((outlinePage, index) => (
            <button
              aria-pressed={page === index}
              className={`w-full rounded-[var(--sh-radius-sm)] border p-1.5 text-left ${page === index ? "border-[var(--sh-brand-500)] bg-[var(--sh-brand-50)]" : "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-paper)]"}`}
              key={outlinePage.id}
              onClick={() => selectPage(index)}
              title={outlinePage.title}
              type="button"
            >
              <div className="aspect-video rounded bg-[var(--sh-artifact-paper)] p-2 shadow-sm">
                <div className="h-1.5 w-1/2 rounded bg-[var(--sh-art-green)]" />
                <div className="mt-2 grid grid-cols-5 gap-px">
                  {Array.from({ length: 20 }, (_, cell) => (
                    <span
                      className={`aspect-square ${cell < index * 3 ? "bg-[var(--sh-art-gold)]" : "bg-[var(--sh-art-paper-green)]"}`}
                      key={cell}
                    />
                  ))}
                </div>
              </div>
              <span className="mt-1.5 block truncate px-1 text-xs font-medium text-[var(--sh-ink-default)]">
                {index + 1}. {outlinePage.title}
              </span>
            </button>
          ))}
        </aside>
        <section className="flex min-w-0 flex-col">
          <div className="mb-1.5 flex min-h-9 flex-nowrap items-center gap-1 overflow-x-auto rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-paper)] p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <IconButton
              className="hidden sm:inline-grid"
              disabled={approved}
              label="查看检查结果"
              onClick={() => openContextDrawer("checks")}
            >
              <CheckCircle2 aria-hidden="true" />
            </IconButton>
            <IconButton
              className="hidden sm:inline-grid"
              disabled={approved}
              label="查看参考内容"
              onClick={() => openContextDrawer("references")}
            >
              <BookOpen aria-hidden="true" />
            </IconButton>
            <IconButton
              className="hidden sm:inline-grid"
              disabled={approved}
              label="编辑内容要求"
              onClick={() => openContextDrawer("prompt")}
            >
              <Settings2 aria-hidden="true" />
            </IconButton>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <Button className="sm:hidden" disabled={approved} size="sm" variant="quiet">
                  <Settings2 aria-hidden="true" />
                  检查与编辑
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="start"
                  aria-label="检查与编辑页面"
                  className="z-[80] min-w-48 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-1.5 text-[var(--sh-ink-default)] shadow-[var(--sh-shadow-floating)]"
                  sideOffset={6}
                >
                  <DropdownMenu.Item
                    className="flex cursor-pointer items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 py-2 text-sm outline-none focus:bg-[var(--sh-surface-soft)]"
                    onSelect={() => openContextDrawer("checks")}
                  >
                    <CheckCircle2 aria-hidden="true" className="size-4" />
                    查看检查结果
                  </DropdownMenu.Item>
                  <DropdownMenu.Item
                    className="flex cursor-pointer items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 py-2 text-sm outline-none focus:bg-[var(--sh-surface-soft)]"
                    onSelect={() => openContextDrawer("references")}
                  >
                    <BookOpen aria-hidden="true" className="size-4" />
                    查看参考内容
                  </DropdownMenu.Item>
                  <DropdownMenu.Item
                    className="flex cursor-pointer items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 py-2 text-sm outline-none focus:bg-[var(--sh-surface-soft)]"
                    onSelect={() => openContextDrawer("prompt")}
                  >
                    <Settings2 aria-hidden="true" className="size-4" />
                    编辑内容要求
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
            <Button
              className="shrink-0"
              disabled={approved}
              onClick={regeneratePage}
              size="sm"
              variant="quiet"
            >
              <Replace aria-hidden="true" />
              重新生成本页
            </Button>
            <span
              aria-live="polite"
              className="sr-only text-xs text-[var(--sh-success)] sm:not-sr-only sm:ml-auto sm:shrink-0"
              role="status"
            >
              第 {page + 1} 页{saveState}
            </span>
            <IconButton
              className="ml-auto shrink-0 sm:ml-0"
              label="更多页面操作"
              onClick={() => openContextDrawer("history")}
            >
              <MoreHorizontal aria-hidden="true" />
            </IconButton>
          </div>
          <div
            className="flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-stage)] p-1.5 md:p-2 lg:[container-type:size]"
            data-testid="ppt-canvas-stage"
          >
            <div
              className="aspect-video w-full lg:w-[min(100%,177.7778cqh)]"
              data-testid="ppt-slide-frame"
            >
              {currentPage.pageType === "cover" ? (
                <PptCoverArtwork demo={demo} variant={coverVariant}>
                  <p className="text-sm font-semibold opacity-70">六年级数学</p>
                  <h2
                    aria-label="封面标题"
                    contentEditable={!approved}
                    suppressContentEditableWarning
                    className="mt-3 text-[clamp(1.4rem,3vw,2.5rem)] font-bold [color:inherit] outline-none focus:bg-white/20"
                    onBlur={(event) =>
                      saveContent(`page-${currentPage.id}-title`, event.currentTarget.textContent)
                    }
                    onInput={() => setSaveState("有未保存修改")}
                  >
                    {readPageContent(content, currentPage.id, page, "title")}
                  </h2>
                  <p
                    aria-label="封面副标题"
                    contentEditable={!approved}
                    suppressContentEditableWarning
                    className="mt-4 text-base [color:inherit] opacity-70 outline-none focus:bg-white/20"
                    onBlur={(event) =>
                      saveContent(
                        `page-${currentPage.id}-subtitle`,
                        event.currentTarget.textContent,
                      )
                    }
                    onInput={() => setSaveState("有未保存修改")}
                  >
                    {readPageContent(content, currentPage.id, page, "subtitle")}
                  </p>
                </PptCoverArtwork>
              ) : demo && (currentPage.id === "2" || currentPage.id === "grid") ? (
                <div className="relative aspect-video">
                  <PercentSlidePreview page={2} />
                  {pageRevision > 0 ? (
                    <p
                      className="absolute bottom-[8%] left-[49%] max-w-[40%] rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)]/94 px-[2.5%] py-[1.5%] text-[clamp(0.55rem,1.2vw,0.9rem)] font-semibold text-[var(--sh-artifact-ink)] shadow-[var(--sh-shadow-card)]"
                      data-testid="ppt-regenerated-note"
                    >
                      {pageRevision % 2 === 0
                        ? "再比较：50 格和 37 格有什么不同？"
                        : "先观察：涂色部分占整体多少？"}
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="relative aspect-video rounded-[var(--sh-radius-sm)] bg-[var(--sh-artifact-paper)] p-[7%] text-[var(--sh-artifact-ink)] shadow-[var(--sh-shadow-floating)]">
                  <p className="text-sm font-semibold [color:var(--sh-art-green)]">
                    {currentPage.title}
                  </p>
                  <h2
                    aria-label={`第 ${String(page + 1)} 页正文`}
                    contentEditable={!approved}
                    suppressContentEditableWarning
                    className="mt-4 max-w-[60%] text-[clamp(1.2rem,2.4vw,2rem)] font-bold [color:var(--sh-artifact-ink)] outline-none focus:bg-[var(--sh-art-paper-green)]"
                    onBlur={(event) =>
                      saveContent(`page-${currentPage.id}-body`, event.currentTarget.textContent)
                    }
                    onInput={() => setSaveState("有未保存修改")}
                  >
                    {readPageContent(content, currentPage.id, page, "body") ??
                      (demo
                        ? "百分数表示一个数是另一个数的百分之几"
                        : `围绕${topic}观察关键信息，并说明自己的发现和理由`)}
                  </h2>
                  <div
                    className={`absolute bottom-[12%] right-[8%] grid w-[32%] gap-0.5 ${demo ? "grid-cols-10" : "grid-cols-6"}`}
                  >
                    {Array.from({ length: demo ? 100 : 24 }, (_, index) => (
                      <span
                        className={`aspect-square ${index < (demo ? 37 : Math.min(18, (page + 1) * 3)) ? "bg-[var(--sh-art-gold)]" : "bg-[var(--sh-art-paper-green)]"}`}
                        key={index}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
          <button
            className="mt-3 inline-flex min-h-10 items-center justify-center gap-2 rounded-[var(--sh-radius-sm)] border border-dashed border-[var(--sh-line-strong)] text-sm font-semibold text-[var(--sh-brand-600)] lg:hidden"
            aria-expanded={mobilePagesOpen}
            onClick={() => setMobilePagesOpen((value) => !value)}
            type="button"
          >
            <Plus aria-hidden="true" className="size-4" />
            选择其他页面
          </button>
          {mobilePagesOpen ? (
            <div className="mt-2 flex gap-2 overflow-x-auto pb-2 lg:hidden">
              {outlinePages.map((outlinePage, index) => (
                <button
                  aria-pressed={page === index}
                  className={`min-h-10 shrink-0 rounded-[var(--sh-radius-sm)] border px-3 text-sm ${page === index ? "border-[var(--sh-brand-500)] bg-[var(--sh-brand-50)]" : "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-paper)]"}`}
                  key={outlinePage.id}
                  onClick={() => {
                    selectPage(index);
                    setMobilePagesOpen(false);
                  }}
                  type="button"
                >
                  {index + 1}. {outlinePage.title}
                </button>
              ))}
            </div>
          ) : null}
        </section>
      </div>
    </WorkbenchPageFrame>
  );
}
