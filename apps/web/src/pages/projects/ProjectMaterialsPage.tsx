import {
  CheckCircle2,
  FileText,
  GripVertical,
  PencilLine,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { LessonSummary } from "@/entities/project/model";
import {
  addMockTextbookFile,
  createMockEntityId,
  saveMockDraft,
  updateMockTextbookFile,
  updateMockNodeState,
  updateMockProject,
  useMockRuntime,
} from "@/shared/api/mocks/runtime";
import { apiConfig } from "@/shared/api/config";
import { demoProjectId, lessons } from "@/shared/data/mockData";
import { markLessonDivisionDependentsStaleForLessons } from "@/features/workbench/lib/invalidateDependents";
import { getChangedLessonIds, readLessonList } from "@/features/workbench/lib/projectLessons";
import { hasReadyTextbook } from "@/features/workbench/lib/stepAccess";
import { reorderItem } from "@/shared/lib/reorderItem";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { IconButton } from "@/shared/ui/IconButton";
import { requiredItem } from "@/shared/lib/requiredItem";

function createInitialLessons(projectId: string, knowledgePoint?: string): LessonSummary[] {
  if (projectId !== demoProjectId && knowledgePoint) {
    return [
      {
        ...requiredItem(lessons, 0, "默认课时"),
        id: createMockEntityId(),
        title: `第 1 课时 · ${knowledgePoint}`,
        scope: `围绕${knowledgePoint}完成概念理解、例题探究与课堂练习。`,
        planStatus: "draft",
        introStatus: "review_required",
        pptStatus: "disabled",
        videoStatus: "disabled",
      },
    ];
  }
  return lessons.map((lesson, index) =>
    index === 0 && knowledgePoint
      ? {
          ...lesson,
          title: `第 1 课时 · ${knowledgePoint}`,
          scope: `围绕${knowledgePoint}完成概念理解、例题探究与课堂练习。`,
        }
      : { ...lesson },
  );
}

export function ProjectMaterialsPage() {
  const { projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const textbookFiles = runtime.textbookFiles[projectId] ?? [];
  const textbookReady = hasReadyTextbook(runtime, projectId);
  const pendingTextbook = textbookFiles.find(
    (file) => file.status === "uploaded" || file.status === "processing",
  );
  const textbookFile =
    textbookFiles.find((file) => file.status === "ready") ?? pendingTextbook ?? textbookFiles[0];
  const lessonDraftKey = `project:${projectId}:lessons`;
  const approvedLessonsKey = `project:${projectId}:lessons-approved`;
  const editingKey = `project:${projectId}:lesson-division-editing`;
  const savedLessons = runtime.drafts[lessonDraftKey]?.value;
  const lessonDivisionState = runtime.nodeStates[`${projectId}:*:lesson-division`];
  const approvedSnapshot = readLessonList(runtime.drafts[approvedLessonsKey]?.value);
  const nodeWasApproved = lessonDivisionState?.status === "approved";
  const nodeApproved = nodeWasApproved && (approvedSnapshot?.length ?? 0) > 0;
  const editing = runtime.drafts[editingKey]?.value === true;
  const locked = nodeApproved && !editing;
  const [lessonItems, setLessonItems] = useState<LessonSummary[]>(
    () =>
      readLessonList(savedLessons) ??
      approvedSnapshot ??
      createInitialLessons(projectId, project?.knowledge_point),
  );
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [reorderMessage, setReorderMessage] = useState("");
  const [uploadError, setUploadError] = useState("");

  useEffect(() => {
    if (apiConfig.mode !== "mock" || textbookReady || !pendingTextbook) return;
    const timer = window.setTimeout(() => {
      updateMockTextbookFile(projectId, pendingTextbook.id, { status: "ready" });
    }, 650);
    return () => window.clearTimeout(timer);
  }, [pendingTextbook, projectId, textbookReady]);

  const persistLessons = (next: LessonSummary[]) => {
    if (locked) return;
    setLessonItems(next);
    saveMockDraft(lessonDraftKey, next, { projectId, nodeKey: "lesson-division" });
  };

  const moveLesson = (from: number, to: number) => {
    if (locked || from === to || to < 0 || to >= lessonItems.length) return;
    persistLessons(reorderItem(lessonItems, from, to));
    setReorderMessage(`已将课时移到第 ${String(to + 1)} 位`);
  };

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 px-5 pb-24 pt-6 md:px-8">
      <FocusPageHeader
        description="先确认教材范围和课时安排，教案会在你批准后按课时独立生成。"
        title="教材与课时"
      />

      <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
        <div className="flex flex-wrap items-center gap-4">
          <span className="grid size-12 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
            <FileText aria-hidden="true" className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h2
              className="line-clamp-2 break-all font-semibold leading-5 text-[var(--sh-ink-strong)] sm:line-clamp-1 sm:break-normal"
              title={textbookFile?.name ?? "尚未上传教材"}
            >
              {textbookFile?.name ?? "尚未上传教材"}
            </h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              {textbookFile
                ? `${(textbookFile.size / 1024 / 1024).toFixed(1)} MB · ${textbookReady ? "教材内容已整理" : textbookFile.status === "failed" ? "教材读取失败，请重新上传" : "文件已保存，正在读取教材内容"}`
                : "请返回项目重新上传教材文件"}
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 text-sm font-semibold ${textbookReady ? "text-[var(--sh-success)]" : "text-[var(--sh-warning)]"}`}
          >
            <CheckCircle2 aria-hidden="true" className="size-4" />
            {textbookReady
              ? "教材已准备"
              : textbookFile?.status === "failed"
                ? "读取失败"
                : textbookFile
                  ? "正在整理"
                  : "等待上传"}
          </span>
          {!textbookReady && (!textbookFile || textbookFile.status === "failed") ? (
            <div className="flex flex-col items-start gap-1 sm:items-end">
              <Button asChild size="sm" variant="secondary">
                <label>
                  <Upload aria-hidden="true" />
                  重新上传教材
                  <input
                    accept="application/pdf,.pdf"
                    aria-label="重新上传教材文件"
                    className="sr-only"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (!file) return;
                      if (
                        file.type !== "application/pdf" ||
                        !file.name.toLowerCase().endsWith(".pdf")
                      ) {
                        setUploadError("请选择 PDF 教材文件");
                        return;
                      }
                      if (file.size > 100 * 1024 * 1024) {
                        setUploadError("教材文件不能超过 100 MB");
                        return;
                      }
                      addMockTextbookFile(projectId, {
                        lastModified: file.lastModified,
                        name: file.name,
                        size: file.size,
                        type: file.type,
                      });
                      setUploadError("");
                      event.currentTarget.value = "";
                    }}
                    type="file"
                  />
                </label>
              </Button>
              {uploadError ? (
                <span className="text-xs font-medium text-[var(--sh-danger)]" role="alert">
                  {uploadError}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="mt-5 grid gap-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-[var(--sh-ink-muted)]">识别知识点</p>
            <p className="mt-1 text-sm font-semibold text-[var(--sh-ink-strong)]">
              {project?.knowledge_point ?? "知识点待确认"}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--sh-ink-muted)]">教材证据</p>
            <p className="mt-1 text-sm font-semibold text-[var(--sh-ink-strong)]">
              {textbookFile ? "教材内容整理完成后建立" : "上传教材后开始安排"}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--sh-ink-muted)]">建议课时</p>
            <p className="mt-1 text-sm font-semibold text-[var(--sh-ink-strong)]">
              {lessonItems.length} 课时 · 每课时 40 分钟
            </p>
          </div>
        </div>
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-[var(--sh-ink-strong)]">安排课时</h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              拖动调整顺序，编辑每课时范围；此处不会生成详细教案。
            </p>
          </div>
          <Button
            disabled={locked}
            onClick={() =>
              persistLessons([
                ...lessonItems,
                {
                  id: createMockEntityId(),
                  title: `第 ${String(lessonItems.length + 1)} 课时 · 新增课时`,
                  scope: "补充本课的教学目标和练习范围。",
                  duration: 40,
                  planStatus: "draft",
                  introStatus: "review_required",
                  pptStatus: "disabled",
                  videoStatus: "disabled",
                },
              ])
            }
            variant="secondary"
          >
            <Plus aria-hidden="true" />
            增加课时
          </Button>
        </div>
        <div className="mt-4 space-y-3">
          {lessonItems.map((lesson, index) => (
            <article
              className="flex items-start gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 md:p-5"
              key={lesson.id}
              onDragOver={(event) => {
                if (!locked) event.preventDefault();
              }}
              onDrop={() => {
                if (!locked && dragIndex !== null) moveLesson(dragIndex, index);
                setDragIndex(null);
              }}
            >
              <button
                aria-label={`拖动${lesson.title}；也可使用上下方向键移动`}
                className="mt-1 grid size-9 shrink-0 cursor-grab place-items-center rounded-md text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"
                disabled={locked}
                draggable={!locked}
                onDragStart={() => setDragIndex(index)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowUp") {
                    event.preventDefault();
                    moveLesson(index, index - 1);
                  }
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    moveLesson(index, index + 1);
                  }
                }}
                type="button"
              >
                <GripVertical aria-hidden="true" className="size-5" />
              </button>
              <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-full bg-[var(--sh-brand-50)] text-sm font-semibold text-[var(--sh-brand-600)]">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <input
                  aria-label="课时名称"
                  className="w-full bg-transparent font-semibold text-[var(--sh-ink-strong)] outline-none focus:rounded focus:bg-[var(--sh-brand-50)]"
                  disabled={locked}
                  onChange={(event) =>
                    persistLessons(
                      lessonItems.map((item) =>
                        item.id === lesson.id ? { ...item, title: event.target.value } : item,
                      ),
                    )
                  }
                  value={lesson.title}
                />
                <textarea
                  aria-label="课时范围"
                  className="mt-2 min-h-16 w-full resize-y rounded-md border-0 bg-[var(--sh-surface-soft)] p-3 text-sm text-[var(--sh-ink-muted)] outline-none focus:ring-1 focus:ring-[var(--sh-brand-300)]"
                  disabled={locked}
                  onChange={(event) =>
                    persistLessons(
                      lessonItems.map((item) =>
                        item.id === lesson.id ? { ...item, scope: event.target.value } : item,
                      ),
                    )
                  }
                  value={lesson.scope}
                />
              </div>
              <IconButton
                disabled={locked || lessonItems.length <= 1}
                label={`删除${lesson.title}`}
                onClick={() => {
                  persistLessons(lessonItems.filter((item) => item.id !== lesson.id));
                  setReorderMessage(`已删除${lesson.title}`);
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
      </section>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]/95 p-4 shadow-[var(--sh-shadow-floating)] backdrop-blur xl:sticky xl:bottom-4">
        <p className="text-sm text-[var(--sh-ink-muted)]">
          {locked
            ? "课时安排已批准，可以进入各课时工作台。"
            : editing
              ? "正在修改课时安排；现有课堂内容保持当前批准版本。"
              : textbookReady
                ? `共 ${String(lessonItems.length)} 课时，批准后系统按课时准备教案和课堂导入方案。`
                : "教材还在整理，整理完成后才能批准课时安排。"}
        </p>
        {locked && lessonItems[0] ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => {
                saveMockDraft(editingKey, true, { projectId, nodeKey: "lesson-division" });
              }}
              variant="secondary"
            >
              <PencilLine aria-hidden="true" />
              重新编辑课时
            </Button>
            <Button asChild>
              <Link to={`/app/projects/${projectId}/lessons/${lessonItems[0].id}/work/lesson-plan`}>
                开始第 1 课时教案
              </Link>
            </Button>
          </div>
        ) : (
          <Button
            disabled={lessonItems.length === 0 || !textbookReady}
            onClick={() => {
              const previousApproved = readLessonList(runtime.drafts[approvedLessonsKey]?.value);
              const changedLessonIds = previousApproved
                ? getChangedLessonIds(previousApproved, lessonItems)
                : new Set<string>();
              const changed = previousApproved ? changedLessonIds.size > 0 : nodeWasApproved;
              if (nodeWasApproved && changed) {
                const historicalLessonIds = Object.values(runtime.nodeStates)
                  .filter(
                    (node) =>
                      node.project_id === projectId &&
                      typeof node.lesson_id === "string" &&
                      node.lesson_id.length > 0,
                  )
                  .map((node) => node.lesson_id as string);
                markLessonDivisionDependentsStaleForLessons(
                  runtime,
                  projectId,
                  previousApproved
                    ? changedLessonIds
                    : new Set([...historicalLessonIds, ...lessonItems.map((lesson) => lesson.id)]),
                );
              }
              saveMockDraft(lessonDraftKey, lessonItems, {
                projectId,
                nodeKey: "lesson-division",
              });
              saveMockDraft(approvedLessonsKey, lessonItems, {
                projectId,
                nodeKey: "lesson-division",
              });
              saveMockDraft(editingKey, false, { projectId, nodeKey: "lesson-division" });
              if (!nodeWasApproved || changed) {
                updateMockNodeState(projectId, null, "lesson-division", {
                  title: "安排课时",
                  status: "approved",
                });
              }
              updateMockProject(projectId, { status: "active" });
            }}
          >
            批准课时安排
          </Button>
        )}
      </div>
    </div>
  );
}
