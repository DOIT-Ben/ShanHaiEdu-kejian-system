import { Check, Download, PencilLine, Presentation } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { PptCoverArtwork } from "@/features/workbench/components/PptCoverArtwork";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { getApprovedDraftValue } from "@/features/workbench/lib/approvedDraft";
import { readPptOutlinePages, type PptOutlinePage } from "@/features/workbench/lib/pptOutline";
import { useMockRuntime } from "@/shared/api/mocks/runtime";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";
import { requiredItem } from "@/shared/lib/requiredItem";

const demoPageTitles = [
  "认识百分数",
  "生活中的百分数",
  "百格图里的 37%",
  "百分数表示什么",
  "百分数和分数",
  "课堂练习",
  "课堂回望",
];

function buildTopicPageTitles(topic: string) {
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

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character] ?? character;
  });
}

function buildExportPages(pageTitles: string[]): PptOutlinePage[] {
  return pageTitles.map((title, index) => ({
    id: String(index),
    pageType: index === 0 ? "cover" : index === pageTitles.length - 1 ? "summary" : "content",
    source: "默认页面安排",
    task: "课堂任务",
    title,
  }));
}

function buildPptPreview(
  topic: string,
  outlinePages: PptOutlinePage[],
  content: Record<string, string>,
  demo: boolean,
  coverVariant: number,
) {
  const readContent = (
    outlinePage: PptOutlinePage,
    index: number,
    field: "body" | "subtitle" | "title",
  ) => content[`page-${outlinePage.id}-${field}`] ?? content[`page-${String(index)}-${field}`];
  const pages = outlinePages
    .map((outlinePage, index) => {
      const title =
        outlinePage.pageType === "cover"
          ? (readContent(outlinePage, index, "title") ?? topic)
          : outlinePage.title;
      const body =
        outlinePage.pageType === "cover"
          ? (readContent(outlinePage, index, "subtitle") ??
            (demo ? "从一杯果汁开始，读懂整体与部分。" : `从课堂问题出发，探究${topic}`))
          : (readContent(outlinePage, index, "body") ??
            `本页围绕${topic}展开一个课堂任务，文字与图示保持清晰。`);
      return `<section data-page-id="${escapeHtml(outlinePage.id)}"${outlinePage.pageType === "cover" ? ` data-cover-variant="${String(coverVariant)}"` : ""}><span>第 ${String(index + 1)} 页</span><h1>${escapeHtml(title)}</h1><p>${escapeHtml(body)}</p></section>`;
    })
    .join("");
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>${escapeHtml(topic)}</title><style>body{margin:0;padding:32px;background:#fff9f2;color:#6b5344;font-family:Inter,"PingFang SC","Microsoft YaHei",sans-serif}section{box-sizing:border-box;aspect-ratio:16/9;max-width:960px;margin:0 auto 32px;padding:9%;border:1px solid #e8dcce;border-radius:16px;background:#fff;box-shadow:0 8px 24px rgba(166,139,110,.15)}span{color:#8b7355;font-size:14px}h1{margin:16px 0 12px;font-size:42px}p{font-size:20px;line-height:1.8}</style>${pages}</html>`;
}

export function PptExportStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const topic = project?.knowledge_point ?? "本课知识点";
  const demo = projectId === demoProjectId || !project;
  const approvedOutline = readPptOutlinePages(
    getApprovedDraftValue(runtime, projectId, lessonId, "ppt-outline"),
  );
  const outlinePages =
    approvedOutline ?? buildExportPages(demo ? demoPageTitles : buildTopicPageTitles(topic));
  const pageTitles = outlinePages.map((outlinePage) => outlinePage.title);
  const pptPagesSnapshot = getApprovedDraftValue<{ content?: Record<string, string> }>(
    runtime,
    projectId,
    lessonId,
    "ppt-pages",
  );
  const approvedContent = pptPagesSnapshot?.content ?? {};
  const coverSnapshot = getApprovedDraftValue<{ selectedId?: number }>(
    runtime,
    projectId,
    lessonId,
    "ppt-cover",
  );
  const coverVariant = coverSnapshot?.selectedId ?? 1;
  const coverPage =
    outlinePages.find((outlinePage) => outlinePage.pageType === "cover") ??
    requiredItem(outlinePages, 0, "PPT封面");
  const coverIndex = Math.max(
    0,
    outlinePages.findIndex((outlinePage) => outlinePage.id === coverPage.id),
  );
  const coverTitle =
    approvedContent[`page-${coverPage.id}-title`] ??
    approvedContent[`page-${String(coverIndex)}-title`] ??
    topic;
  const coverSubtitle =
    approvedContent[`page-${coverPage.id}-subtitle`] ??
    approvedContent[`page-${String(coverIndex)}-subtitle`] ??
    (demo ? "从生活中的数据，看见整体与部分" : "从观察到表达，再到课堂练习");
  const pagesPath = `/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:ppt-pages`];
  const stale = nodeState?.status === "stale";
  const approved = Boolean(pptPagesSnapshot) && !stale;
  const newerDraftPending = approved && nodeState?.status === "review_required";
  const pageCount = pageTitles.length;
  const checks = approved
    ? [`${String(pageCount)} 页课堂内容已确认`, "16:9 画幅适合教室大屏", "标题与正文仍可继续编辑"]
    : [
        `${String(pageCount)} 页页面顺序已经安排`,
        "正文还需要你确认",
        `确认后可下载完整的 ${String(pageCount)} 页预览`,
      ];

  return (
    <WorkbenchPageFrame>
      <FocusPageHeader
        action={
          approved ? (
            <Button
              onClick={() =>
                downloadExampleFile(
                  `${topic}_课堂课件预览.html`,
                  buildPptPreview(topic, outlinePages, approvedContent, demo, coverVariant),
                  "text/html;charset=utf-8",
                )
              }
              size="md"
            >
              <Download aria-hidden="true" />
              下载课件预览
            </Button>
          ) : (
            <Button asChild size="md">
              <Link to={pagesPath}>
                <PencilLine aria-hidden="true" />
                去确认 PPT 正文
              </Link>
            </Button>
          )
        }
        description={
          approved
            ? newerDraftPending
              ? "当前已批准版本仍可下载；正在修改的新稿确认后会替换它。"
              : "最后看一眼封面、正文和课堂顺序，确认后即可带进教室。"
            : "页面已经排好，先确认正文内容，再下载完整课件预览。"
        }
        eyebrow="最后一步 · 带走课堂作品"
        status={<StatusBadge status={stale ? "stale" : approved ? "ready" : "review_required"} />}
        title={approved ? `导出${topic}课件` : "确认正文后再导出课件"}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <section className="relative overflow-hidden rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-stage)] p-3 shadow-[var(--sh-shadow-card)] md:p-4">
          <div className="absolute inset-x-[13%] bottom-[7%] top-[15%] rotate-[3deg] rounded-[var(--sh-radius-md)] bg-[var(--sh-accent-rose-soft)] shadow-[var(--sh-shadow-card)]" />
          <div className="absolute inset-x-[10%] bottom-[10%] top-[10%] -rotate-[2deg] rounded-[var(--sh-radius-md)] bg-[var(--sh-brand-100)] shadow-[var(--sh-shadow-card)]" />
          <div className="relative mx-auto max-w-3xl overflow-hidden rounded-[var(--sh-radius-md)] border-[7px] border-[var(--sh-artifact-paper)] bg-[var(--sh-artifact-paper)] shadow-[var(--sh-shadow-modal)]">
            <PptCoverArtwork demo={demo} variant={coverVariant}>
              <p className="text-sm font-semibold opacity-70">小学数学课堂</p>
              <h2 className="mt-3 text-[clamp(1.4rem,3vw,2.5rem)] font-bold">{coverTitle}</h2>
              <p className="mt-3 text-sm opacity-70">{coverSubtitle}</p>
            </PptCoverArtwork>
          </div>
          <div className="relative mx-auto mt-3 flex max-w-3xl items-center justify-between gap-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)]/94 px-3 py-2 shadow-[var(--sh-shadow-card)] backdrop-blur-sm">
            <span className="flex items-center gap-2 text-sm font-medium text-[var(--sh-ink-strong)]">
              <Presentation aria-hidden="true" className="size-4 text-[var(--sh-brand-700)]" />
              {topic} · {String(pageTitles.length)} 页
            </span>
            <span className="text-xs text-[var(--sh-ink-muted)]">
              封面 + {String(Math.max(0, pageCount - 2))} 页正文 + 课堂回望
            </span>
          </div>
        </section>

        <aside className="h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-card)]">
          <p className="text-xs font-medium text-[var(--sh-brand-600)]">课前确认</p>
          <h2 className="mt-1 text-lg font-semibold">
            {approved ? "这套课件已准备好" : "还差最后一次正文确认"}
          </h2>
          <ul className="mt-3 space-y-2.5">
            {checks.map((item) => (
              <li
                className="flex items-start gap-3 text-sm text-[var(--sh-ink-default)]"
                key={item}
              >
                <span
                  className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ${approved ? "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]" : "bg-[var(--sh-warning-soft)] text-[var(--sh-warning)]"}`}
                >
                  <Check aria-hidden="true" className="size-3" />
                </span>
                {item}
              </li>
            ))}
          </ul>
          <Button asChild className="mt-4 w-full" size="sm" variant="secondary">
            <Link to={pagesPath}>
              <PencilLine aria-hidden="true" />
              {approved ? "返回修改正文" : "去确认正文"}
            </Link>
          </Button>
        </aside>
      </div>
    </WorkbenchPageFrame>
  );
}
