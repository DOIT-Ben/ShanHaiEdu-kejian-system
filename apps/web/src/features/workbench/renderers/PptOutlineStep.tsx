import { ArrowRight, Check, GripVertical, PencilLine, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { getApprovedDraftValue } from "@/features/workbench/lib/approvedDraft";
import { markPptOutlineDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { readPptOutlinePages, type PptOutlinePage } from "@/features/workbench/lib/pptOutline";
import { reorderItem } from "@/shared/lib/reorderItem";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { IconButton } from "@/shared/ui/IconButton";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";

const initialPages: PptOutlinePage[] = [
  {
    id: "cover",
    pageType: "cover",
    title: "封面",
    task: "建立课题印象",
    source: "批准教案 · 课题",
  },
  {
    id: "life",
    pageType: "content",
    title: "生活中的百分数",
    task: "发现百分数信息",
    source: "教材第 82 页",
  },
  {
    id: "grid",
    pageType: "content",
    title: "百格图里的 37%",
    task: "用图形表示百分数",
    source: "教材例 1",
  },
  {
    id: "meaning",
    pageType: "content",
    title: "百分数表示什么",
    task: "概括百分数的意义",
    source: "教案 · 探究环节",
  },
  {
    id: "fraction",
    pageType: "content",
    title: "分数与百分数",
    task: "辨析两种表达的用途",
    source: "教案 · 重难点",
  },
  {
    id: "practice",
    pageType: "content",
    title: "我会判断",
    task: "用反例巩固概念边界",
    source: "教材练一练",
  },
  {
    id: "summary",
    pageType: "summary",
    title: "课堂回望",
    task: "总结百分数的核心关系",
    source: "教案 · 课堂总结",
  },
];

function createTopicPages(topic: string): PptOutlinePage[] {
  return [
    {
      id: "cover",
      pageType: "cover",
      title: "封面",
      task: "建立课题印象",
      source: "批准教案 · 课题",
    },
    {
      id: "context",
      pageType: "content",
      title: `走近${topic}`,
      task: "发现教材情境中的关键信息",
      source: "教材情境",
    },
    {
      id: "explore",
      pageType: "content",
      title: `探究${topic}`,
      task: "用图示或操作解释关系",
      source: "教案 · 探究环节",
    },
    {
      id: "share",
      pageType: "content",
      title: "交流与辨析",
      task: "比较不同想法并说明理由",
      source: "教案 · 重难点",
    },
    {
      id: "practice",
      pageType: "content",
      title: "课堂练习",
      task: "在新情境中检查理解",
      source: "教材练习",
    },
    {
      id: "summary",
      pageType: "summary",
      title: "课堂回望",
      task: `总结${topic}的核心关系`,
      source: "教案 · 课堂总结",
    },
  ];
}

export function PptOutlineStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const topic = project?.knowledge_point ?? "本课知识点";
  const fallbackPages =
    projectId === demoProjectId || !project ? initialPages : createTopicPages(topic);
  const draftKey = `project:${projectId}:lesson:${lessonId}:ppt-outline`;
  const approvedDraftKey = `${draftKey}:approved`;
  const editingKey = `${draftKey}:editing`;
  const savedPages = readPptOutlinePages(runtime.drafts[draftKey]?.value);
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:ppt-outline`];
  const nodeApproved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  const editing = runtime.drafts[editingKey]?.value === true;
  const approved = nodeApproved && !editing;
  const approvedSnapshot = readPptOutlinePages(
    getApprovedDraftValue(runtime, projectId, lessonId, "ppt-outline"),
  );
  const [pages, setPages] = useState<PptOutlinePage[]>(
    () => savedPages ?? approvedSnapshot ?? fallbackPages,
  );
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [reorderMessage, setReorderMessage] = useState("");

  const persistPages = (next: PptOutlinePage[]) => {
    if (approved) return;
    setPages(next);
    saveMockDraft(draftKey, next, { lessonId, nodeKey: "ppt-outline", projectId });
  };

  const movePage = (from: number, to: number) => {
    if (approved || from === to || to < 0 || to >= pages.length) return;
    if (pages[from]?.pageType === "cover" || pages[to]?.pageType === "cover") return;
    persistPages(reorderItem(pages, from, to));
    setReorderMessage(`已将页面移到第 ${String(to + 1)} 位`);
  };

  return (
    <WorkbenchPageFrame>
      <FocusPageHeader
        action={
          approved ? (
            <>
              <Button
                onClick={() => {
                  if (!runtime.drafts[approvedDraftKey]) {
                    saveMockDraft(approvedDraftKey, pages, {
                      lessonId,
                      nodeKey: "ppt-outline",
                      projectId,
                    });
                  }
                  saveMockDraft(editingKey, true, {
                    lessonId,
                    nodeKey: "ppt-outline",
                    projectId,
                  });
                }}
                size="md"
                variant="secondary"
              >
                <PencilLine aria-hidden="true" />
                重新编辑页面安排
              </Button>
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-cover`}>
                  选择课件封面
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          ) : (
            <Button
              disabled={pages.length === 0}
              onClick={() => {
                const changed =
                  nodeApproved && JSON.stringify(approvedSnapshot) !== JSON.stringify(pages);
                if (changed) markPptOutlineDependentsStale(runtime, projectId, lessonId);
                saveMockDraft(draftKey, pages, {
                  lessonId,
                  nodeKey: "ppt-outline",
                  projectId,
                });
                saveMockDraft(approvedDraftKey, pages, {
                  lessonId,
                  nodeKey: "ppt-outline",
                  projectId,
                });
                saveMockDraft(editingKey, false, {
                  lessonId,
                  nodeKey: "ppt-outline",
                  projectId,
                });
                if (!nodeApproved || changed) {
                  updateMockNodeState(projectId, lessonId, "ppt-outline", {
                    stale_reason: null,
                    title: "安排 PPT 页面",
                    status: "approved",
                  });
                }
              }}
              size="md"
            >
              <Check aria-hidden="true" />
              {editing ? "确认新页面安排" : "确认页面安排"}
            </Button>
          )
        }
        eyebrow="当前要做：确认 PPT 页面安排"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={`${String(pages.length)} 页课堂课件`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-4 grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {pages.map((page, index) => (
          <article
            className="flex min-w-0 items-center gap-2 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3"
            key={page.id}
            onDragOver={(event) => {
              if (!approved) event.preventDefault();
            }}
            onDrop={() => {
              if (!approved && dragIndex !== null) movePage(dragIndex, index);
              setDragIndex(null);
            }}
          >
            <button
              aria-label={`拖动第 ${String(index + 1)} 页 ${page.title}；也可使用上下方向键移动`}
              className="grid size-9 shrink-0 cursor-grab place-items-center rounded-md text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"
              disabled={approved || page.pageType === "cover"}
              draggable={!approved && page.pageType !== "cover"}
              onDragStart={() => setDragIndex(index)}
              onKeyDown={(event) => {
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  movePage(index, index - 1);
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  movePage(index, index + 1);
                }
              }}
              type="button"
            >
              <GripVertical aria-hidden="true" className="size-5" />
            </button>
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[var(--sh-brand-50)] text-sm font-semibold text-[var(--sh-brand-600)]">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <input
                aria-label={`第 ${String(index + 1)} 页标题`}
                className="w-full bg-transparent font-semibold text-[var(--sh-ink-strong)] outline-none focus:rounded focus:bg-[var(--sh-brand-50)]"
                disabled={approved}
                onChange={(event) =>
                  persistPages(
                    pages.map((item) =>
                      item.id === page.id ? { ...item, title: event.target.value } : item,
                    ),
                  )
                }
                value={page.title}
              />
              <p className="mt-1 truncate text-sm text-[var(--sh-ink-muted)]">{page.task}</p>
            </div>
            <span className="hidden rounded-full bg-[var(--sh-surface-soft)] px-2 py-1 text-xs text-[var(--sh-ink-muted)] 2xl:block">
              {page.source}
            </span>
            <IconButton
              disabled={approved || pages.length <= 1 || page.pageType === "cover"}
              label={`删除第 ${String(index + 1)} 页`}
              onClick={() => {
                persistPages(pages.filter((item) => item.id !== page.id));
                setReorderMessage(`已删除${page.title}`);
              }}
            >
              <Trash2 aria-hidden="true" />
            </IconButton>
          </article>
        ))}
      </div>
      <p aria-live="polite" className="sr-only">
        {reorderMessage}
      </p>
      <button
        disabled={approved}
        className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-[var(--sh-radius-sm)] border border-dashed border-[var(--sh-line-strong)] text-sm font-semibold text-[var(--sh-brand-600)] hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-brand-50)]"
        onClick={() =>
          persistPages([
            ...pages,
            {
              id: `page-${String(Date.now())}`,
              pageType: "content",
              title: `新页面 ${String(pages.length + 1)}`,
              task: "补充一个课堂任务",
              source: "待补充",
            },
          ])
        }
        type="button"
      >
        <Plus aria-hidden="true" className="size-4" />
        增加一页
      </button>
    </WorkbenchPageFrame>
  );
}
