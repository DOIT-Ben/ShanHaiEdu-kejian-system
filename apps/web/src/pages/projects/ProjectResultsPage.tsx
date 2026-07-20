import {
  Download,
  FileCheck2,
  History,
  MoreHorizontal,
  Presentation,
  Replace,
  Video,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  artifactPreviewRegistry,
  type ArtifactType,
} from "@/features/project-results/artifactPreviewRegistry";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import {
  getPlayableFinalVideo,
  isFinalVideoMediaConfirmed,
} from "@/features/workbench/lib/videoMedia";
import { saveMockDraft, useMockRuntime } from "@/shared/api/mocks/runtime";
import {
  listMockSavedResultHistory,
  listMockSavedResults,
  replaceMockResult,
  saveMockResult,
  type SaveMockResultInput,
} from "@/shared/api/mocks/savedResults";
import { demoProjectId } from "@/shared/data/mockData";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { IconButton } from "@/shared/ui/IconButton";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { Select } from "@/shared/ui/Select";

const seededAssets: Array<{
  id: string;
  resultId: string;
  type: ArtifactType;
  title: string;
  use: string;
  lesson: string;
  slotKey: string;
  version: number;
  source: "seed";
  preview?: undefined;
}> = [
  {
    id: "a1",
    resultId: "a1",
    type: "image",
    title: "三瓶果汁主视觉",
    use: "PPT 第 2 页主视觉",
    lesson: "第 1 课时",
    slotKey: "ppt.page-2.hero",
    version: 1,
    source: "seed",
  },
  {
    id: "a2",
    resultId: "a2",
    type: "ppt_page",
    title: "百格图里的 37%",
    use: "PPT 第 3 页",
    lesson: "第 1 课时",
    slotKey: "ppt.page-3.body",
    version: 1,
    source: "seed",
  },
  {
    id: "a3",
    resultId: "a3",
    type: "video",
    title: "镜头 1 · 果汁落桌关键帧",
    use: "导入视频关键帧参考",
    lesson: "第 1 课时",
    slotKey: "video.shot-1",
    version: 1,
    source: "seed",
  },
  {
    id: "a4",
    resultId: "a4",
    type: "audio",
    title: "场次 1 旁白",
    use: "导入视频旁白",
    lesson: "第 1 课时",
    slotKey: "video.narration-1",
    version: 1,
    source: "seed",
  },
  {
    id: "a5",
    resultId: "a5",
    type: "document",
    title: "课堂导入设计附录",
    use: "教案附录",
    lesson: "第 1 课时",
    slotKey: "lesson-plan.appendix",
    version: 1,
    source: "seed",
  },
  {
    id: "a6",
    resultId: "a6",
    type: "image",
    title: "百格光窗视觉稿",
    use: "项目通用教学图片",
    lesson: "第 1 课时",
    slotKey: "project.shared-images:a6",
    version: 1,
    source: "seed",
  },
];

const filters: Array<{ value: "all" | ArtifactType; label: string }> = [
  { value: "all", label: "全部" },
  { value: "image", label: "教学图片" },
  { value: "ppt_page", label: "PPT 页面" },
  { value: "video", label: "关键帧参考" },
  { value: "audio", label: "音频字幕" },
  { value: "document", label: "文档" },
];

export function ProjectResultsPage() {
  const { projectId = demoProjectId } = useParams();
  const runtime = useMockRuntime();
  const [filter, setFilter] = useState<"all" | ArtifactType>("all");
  const selectionKey = `project:${projectId}:results-selection`;
  const storedSelection = runtime.drafts[selectionKey]?.value;
  const [selectedId, setSelectedId] = useState(
    typeof storedSelection === "string" ? storedSelection : "a1",
  );
  const [message, setMessage] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [lesson, setLesson] = useState("all");
  const assets = useMemo(() => {
    const savedAssets = listMockSavedResults(runtime, projectId).map((result) => ({
      id: result.id,
      lesson: result.lessonLabel,
      preview: result.preview,
      resultId: result.resultId,
      slotKey: result.slotKey,
      title: result.title,
      type: result.type,
      use: result.slotLabel,
      version: result.version,
      source: "runtime" as const,
    }));
    const occupiedSlots = new Set(savedAssets.map((asset) => asset.slotKey));
    return projectId === demoProjectId
      ? [...savedAssets, ...seededAssets.filter((asset) => !occupiedSlots.has(asset.slotKey))]
      : savedAssets;
  }, [projectId, runtime]);
  const visible = useMemo(
    () =>
      assets.filter(
        (asset) =>
          (filter === "all" || asset.type === filter) &&
          (lesson === "all" || asset.lesson === lesson),
      ),
    [assets, filter, lesson],
  );
  const selected = assets.find((asset) => asset.id === selectedId) ?? assets[0];
  const otherVisible = visible.filter((asset) => asset.id !== selected?.id);
  const history = selected
    ? selected.source === "runtime"
      ? listMockSavedResultHistory(runtime, projectId, selected.slotKey)
      : [
          {
            id: selected.id,
            lessonLabel: selected.lesson,
            projectId,
            replaceMode: "replace" as const,
            resultId: selected.resultId,
            savedAt: "2026-07-17T02:24:00Z",
            slotKey: selected.slotKey,
            slotLabel: selected.use,
            title: selected.title,
            type: selected.type,
            version: selected.version,
          },
        ]
    : [];
  const SelectedPreview = selected
    ? artifactPreviewRegistry[selected.type]
    : artifactPreviewRegistry.image;
  const nodeStatus = (keys: string[]) =>
    Object.values(runtime.nodeStates).find(
      (node) => node.project_id === projectId && keys.includes(node.node_key),
    )?.status ?? "not_ready";
  const hasPlayableVideo = getApprovedProjectLessons(runtime, projectId).some((item) => {
    const media = getPlayableFinalVideo(runtime, projectId, item.id);
    return (
      runtime.nodeStates[`${projectId}:${item.id}:final-video`]?.status === "approved" &&
      isFinalVideoMediaConfirmed(runtime, projectId, item.id, media)
    );
  });
  const resultCards = [
    {
      title: "教案",
      detail: "第 1 课时 · 当前版本",
      icon: FileCheck2,
      status: nodeStatus(["lesson-plan"]),
    },
    {
      title: "PPT",
      detail: "正文与导出版本",
      icon: Presentation,
      status: nodeStatus(["ppt-pages", "ppt-outline"]),
    },
    {
      title: "课堂导入视频",
      detail: hasPlayableVideo ? "可播放视频与关键帧参考" : "关键帧参考已保存，视频尚未生成",
      icon: Video,
      status: hasPlayableVideo ? ("approved" as const) : ("not_ready" as const),
    },
  ];
  const selectAsset = (assetId: string) => {
    saveMockDraft(selectionKey, assetId, { projectId });
    setSelectedId(assetId);
  };
  const replaceSelected = () => {
    if (!selected) return;
    const nextVersion = selected.version + 1;
    const baseTitle = selected.title.replace(/（调整版 \d+）$/, "");
    const replacement: SaveMockResultInput = {
      lessonLabel: selected.lesson,
      ...(selected.preview ? { preview: selected.preview } : {}),
      projectId,
      replaceMode: "replace",
      resultId: `result-revision-${globalThis.crypto.randomUUID()}`,
      slotKey: selected.slotKey,
      slotLabel: selected.use,
      title: `${baseTitle}（调整版 ${String(nextVersion)}）`,
      type: selected.type,
    };
    const previous: SaveMockResultInput = {
      lessonLabel: selected.lesson,
      ...(selected.preview ? { preview: selected.preview } : {}),
      projectId,
      replaceMode: "replace",
      resultId: selected.resultId,
      slotKey: selected.slotKey,
      slotLabel: selected.use,
      title: selected.title,
      type: selected.type,
    };
    const saved =
      selected.source === "seed"
        ? replaceMockResult(replacement, previous)
        : saveMockResult(replacement);
    selectAsset(saved.id);
    setMessage(`已将“${baseTitle}”替换为版本 ${String(saved.version)}，上一版本已保留在历史中`);
  };
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 lg:px-12">
      <FocusPageHeader
        description="这里展示已保存到项目的当前作品和历史版本。"
        title="素材与成果"
      />
      <section
        className="mt-5 grid grid-cols-3 gap-2 md:mt-7 md:gap-4"
        data-testid="results-summary"
      >
        {resultCards.map(({ detail, icon: Icon, status, title }) => (
          <article
            className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 md:p-5"
            key={title}
          >
            <div className="flex flex-col items-start gap-2 md:flex-row md:justify-between md:gap-3">
              <span className="grid size-8 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)] md:size-11">
                <Icon aria-hidden="true" className="size-4 md:size-5" />
              </span>
              <StatusBadge status={status} />
            </div>
            <h2 className="mt-2 min-h-10 text-sm font-semibold leading-5 text-[var(--sh-ink-strong)] md:mt-5 md:min-h-0 md:text-lg md:leading-7">
              {title}
            </h2>
            <p className="mt-1 hidden text-sm text-[var(--sh-ink-muted)] md:block">{detail}</p>
            <Button
              aria-label="查看当前成果"
              className="mt-2 w-full px-2 md:mt-5 md:w-auto md:px-3"
              onClick={() => {
                const targetType =
                  title === "PPT" ? "ppt_page" : title === "课堂导入视频" ? "video" : "document";
                const target = assets.find((asset) => asset.type === targetType);
                if (target) selectAsset(target.id);
                setMessage(target ? `正在查看：${title}` : `${title}还没有已保存成果`);
              }}
              size="sm"
              variant="secondary"
            >
              <span className="md:hidden">查看</span>
              <span className="hidden md:inline">查看当前成果</span>
            </Button>
          </article>
        ))}
      </section>
      <section className="mt-6 md:mt-9">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-[var(--sh-ink-strong)]">项目素材</h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">按课时、类型和使用位置查看。</p>
          </div>
          <Select
            ariaLabel="按课时筛选"
            className="w-32"
            onValueChange={setLesson}
            options={[
              { label: "全部课时", value: "all" },
              { label: "第 1 课时", value: "第 1 课时" },
              { label: "第 2 课时", value: "第 2 课时" },
            ]}
            value={lesson}
          />
        </div>
        <div
          aria-label="素材类型"
          className="mt-3 flex gap-1 overflow-x-auto border-b border-[var(--sh-line-subtle)] md:mt-4"
          role="group"
        >
          {filters.map((item) => (
            <button
              aria-pressed={filter === item.value}
              className="shrink-0 border-b-2 border-transparent px-3 py-2.5 text-sm font-medium text-[var(--sh-ink-muted)] data-[state=active]:border-[var(--sh-brand-500)] data-[state=active]:text-[var(--sh-ink-strong)]"
              data-state={filter === item.value ? "active" : "inactive"}
              key={item.value}
              onClick={() => setFilter(item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="mt-4 grid gap-4 lg:mt-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-5">
          <div className="order-2 grid content-start gap-4 sm:grid-cols-2 lg:order-1 lg:grid-cols-2 xl:grid-cols-3">
            {otherVisible.map((asset) => {
              const Preview = artifactPreviewRegistry[asset.type];
              return (
                <button
                  aria-pressed={selectedId === asset.id}
                  className={`rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-3 text-left ${selectedId === asset.id ? "border-[var(--sh-brand-500)]" : "border-[var(--sh-line-subtle)] hover:border-[var(--sh-brand-300)]"}`}
                  key={asset.id}
                  onClick={() => selectAsset(asset.id)}
                  type="button"
                >
                  <Preview preview={asset.preview} />
                  <h3 className="mt-3 truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {asset.title}
                  </h3>
                  <p className="mt-1 truncate text-xs text-[var(--sh-ink-muted)]">{asset.use}</p>
                </button>
              );
            })}
            {visible.length === 0 ? (
              <p className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)] p-6 text-sm text-[var(--sh-ink-muted)] sm:col-span-2 xl:col-span-3">
                当前筛选下还没有已保存成果。请先在创作中心选中作品并保存到本项目。
              </p>
            ) : otherVisible.length === 0 ? (
              <p className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)] p-6 text-sm text-[var(--sh-ink-muted)] sm:col-span-2 xl:col-span-3">
                当前筛选下没有其他素材；上方就是正在采用的版本。
              </p>
            ) : null}
          </div>
          {selected ? (
            <aside
              className="order-1 h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 lg:order-2 lg:sticky lg:top-20 lg:p-5"
              data-testid="current-result-summary"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold text-[var(--sh-brand-600)]">
                    {selected.type === "video" ? "当前关键帧参考" : "当前采用版本"}
                  </p>
                  <h2 className="mt-1 font-semibold text-[var(--sh-ink-strong)]">
                    {selected.title}
                  </h2>
                  <p className="mt-1 text-xs text-[var(--sh-ink-muted)]">版本 {selected.version}</p>
                </div>
                <IconButton
                  label="更多素材操作"
                  onClick={() => setMessage(`已打开${selected.title}的更多操作`)}
                >
                  <MoreHorizontal aria-hidden="true" />
                </IconButton>
              </div>
              <div className="mt-4 hidden lg:block">
                <SelectedPreview preview={selected.preview} />
              </div>
              {selected.type === "video" ? (
                <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] px-3 py-2 text-xs font-medium text-[var(--sh-ink-default)]">
                  当前仅为关键帧示意，视频尚未生成。
                </p>
              ) : null}
              <dl className="mt-5 hidden space-y-3 text-sm lg:block">
                <div>
                  <dt className="text-xs text-[var(--sh-ink-muted)]">使用位置</dt>
                  <dd className="mt-1 text-[var(--sh-ink-strong)]">{selected.use}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--sh-ink-muted)]">来源</dt>
                  <dd className="mt-1 text-[var(--sh-ink-strong)]">
                    {selected.lesson} · 创作中心保存
                  </dd>
                </div>
              </dl>
              <div className="mt-3 flex gap-2 lg:mt-5 lg:grid">
                <Button
                  aria-label="替换当前版本"
                  className="min-w-0 flex-1 px-2 lg:w-full"
                  onClick={replaceSelected}
                  size="sm"
                >
                  <Replace aria-hidden="true" />
                  <span className="lg:hidden">替换</span>
                  <span className="hidden lg:inline">替换当前版本</span>
                </Button>
                <Button
                  aria-label={selected.type === "video" ? "下载关键帧说明" : "下载作品说明"}
                  className="min-w-0 flex-1 px-2 lg:w-full"
                  onClick={() => {
                    const keyframeNotice =
                      selected.type === "video" ? "\n当前仅为关键帧示意，视频尚未生成。" : "";
                    downloadExampleFile(
                      `${selected.title}_${selected.type === "video" ? "关键帧" : "成果"}说明.txt`,
                      `山海教育项目成果\n作品：${selected.title}\n使用位置：${selected.use}\n来源：${selected.lesson}\n此文件记录当前作品信息。${keyframeNotice}`,
                    );
                    setMessage(
                      `已下载“${selected.title}”的${selected.type === "video" ? "关键帧" : "成果"}说明`,
                    );
                  }}
                  size="sm"
                  variant="secondary"
                >
                  <Download aria-hidden="true" />
                  <span className="lg:hidden">下载</span>
                  <span className="hidden lg:inline">
                    {selected.type === "video" ? "下载关键帧说明" : "下载作品说明"}
                  </span>
                </Button>
                <Button
                  aria-label="查看历史版本"
                  className="min-w-0 flex-1 px-2 lg:w-full"
                  onClick={() => setHistoryOpen((open) => !open)}
                  size="sm"
                  variant="quiet"
                >
                  <History aria-hidden="true" />
                  <span className="lg:hidden">历史</span>
                  <span className="hidden lg:inline">查看历史版本</span>
                </Button>
              </div>
              {historyOpen ? (
                <section
                  aria-label="历史版本"
                  className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4"
                >
                  <h3 className="font-semibold text-[var(--sh-ink-strong)]">历史版本</h3>
                  {history.length > 0 ? (
                    <ul className="mt-3 space-y-2 text-xs text-[var(--sh-ink-muted)]">
                      {history.map((entry, index) => (
                        <li
                          className="flex items-center justify-between gap-3"
                          key={`${String(entry.version)}-${entry.savedAt}`}
                        >
                          <span className="min-w-0">
                            <span className="block font-semibold text-[var(--sh-ink-default)]">
                              版本 {entry.version} · {index === 0 ? "当前采用" : "已归档"}
                            </span>
                            <span className="mt-0.5 block truncate">{entry.title}</span>
                          </span>
                          <time dateTime={entry.savedAt}>
                            {new Intl.DateTimeFormat("zh-CN", {
                              hour: "2-digit",
                              minute: "2-digit",
                            }).format(new Date(entry.savedAt))}
                          </time>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-xs text-[var(--sh-ink-muted)]">
                      当前只有初始采用版本；替换后会在这里保留历史。
                    </p>
                  )}
                </section>
              ) : null}
            </aside>
          ) : null}
        </div>
      </section>
      {message ? (
        <p
          aria-live="polite"
          className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] p-4 text-sm font-semibold text-[var(--sh-brand-700)]"
        >
          {message}
        </p>
      ) : null}
    </div>
  );
}
