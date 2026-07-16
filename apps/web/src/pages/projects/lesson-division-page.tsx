import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router";
import { CheckCircle2, GripVertical, Plus, RotateCcw, Trash2 } from "lucide-react";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { divisionContentSchema, lessonTypeLabels, parseContent, type DivisionContent, type DivisionLesson } from "@/entities/content";
import {
  useApproveDivision,
  useDivisionVersions,
  useGenerateDivision,
  useLessonDivision,
  useSaveDivision,
} from "@/features/projects";
import { AppError } from "@/shared/api";
import {
  Badge,
  Button,
  EmptyState,
  Input,
  PageHeader,
  SaveStatusIndicator,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  toast,
  type SaveState,
} from "@/shared/ui";
import { AppErrorPanel, ConflictDialog } from "@/widgets";

function LessonRow({
  lesson,
  index,
  editable,
  onChange,
  onRemove,
}: {
  lesson: DivisionLesson;
  index: number;
  editable: boolean;
  onChange: (next: DivisionLesson) => void;
  onRemove: () => void;
}) {
  return (
    <li className="flex items-start gap-2 rounded-card border border-line bg-surface-1 p-3">
      <GripVertical className="mt-2 size-4 shrink-0 text-ink-disabled" aria-hidden />
      <span className="mt-2 w-14 shrink-0 text-xs text-ink-muted">第{index + 1}课时</span>
      <div className="grid min-w-0 flex-1 gap-2 lg:grid-cols-[1fr_120px_100px_1fr]">
        <Input
          value={lesson.title}
          disabled={!editable}
          aria-label={`第${index + 1}课时标题`}
          onChange={(event) => onChange({ ...lesson, title: event.target.value })}
        />
        <Select
          value={lesson.lesson_type}
          onValueChange={(value) => onChange({ ...lesson, lesson_type: value as DivisionLesson["lesson_type"] })}
        >
          <SelectTrigger disabled={!editable} aria-label="课型">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(lessonTypeLabels).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          value={lesson.textbook_pages}
          disabled={!editable}
          aria-label="教材页码"
          placeholder="P12-15"
          onChange={(event) => onChange({ ...lesson, textbook_pages: event.target.value })}
        />
        <Input
          value={lesson.knowledge_points.join("、")}
          disabled={!editable}
          aria-label="知识点"
          placeholder="知识点，用、分隔"
          onChange={(event) => onChange({ ...lesson, knowledge_points: event.target.value.split("、").filter(Boolean) })}
        />
      </div>
      {editable ? (
        <Button size="sm" variant="ghost" onClick={onRemove} aria-label={`删除第${index + 1}课时`}>
          <Trash2 className="size-4 text-danger" aria-hidden />
        </Button>
      ) : null}
    </li>
  );
}

/** 课时划分页：生成 → 编辑（乐观锁）→ 确认；确认后生成课时工作流。 */
export function LessonDivisionPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const projectId = project.project_id;
  const division = useLessonDivision(projectId);
  const versions = useDivisionVersions(projectId);
  const save = useSaveDivision(projectId);
  const generate = useGenerateDivision(projectId);
  const approve = useApproveDivision(projectId);

  const serverContent = useMemo(() => parseContent(divisionContentSchema, division.data?.content), [division.data]);
  const [draft, setDraft] = useState<DivisionContent | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [conflictOpen, setConflictOpen] = useState(false);
  const [serverRowVersion, setServerRowVersion] = useState<number | null>(null);

  useEffect(() => {
    setDraft(serverContent);
    setSaveState("idle");
  }, [serverContent]);

  const noDivision = division.isError && division.error instanceof AppError && division.error.status === 404;
  const isApproved = division.data?.status === "approved";
  const editable = Boolean(draft) && !isApproved;
  const dirty = draft !== null && serverContent !== null && JSON.stringify(draft) !== JSON.stringify(serverContent);

  const doSave = (rowVersionOverride?: number) => {
    if (!draft || !division.data) return;
    setSaveState("saving");
    save.mutate(
      { content: draft, row_version: rowVersionOverride ?? division.data.row_version ?? 1 },
      {
        onSuccess: () => setSaveState("saved"),
        onError: (error) => {
          setSaveState("error");
          if (error instanceof AppError && error.status === 409) {
            const details = error.details as { server_row_version?: number } | undefined;
            setServerRowVersion(details?.server_row_version ?? null);
            setConflictOpen(true);
          }
        },
      },
    );
  };

  return (
    <div className="space-y-4 p-6">
      <PageHeader
        title="课时划分"
        description="基于教材证据把单元拆分为课时；确认后系统为每个课时建立 18 步制作流程。"
        actions={
          <>
            {editable ? <SaveStatusIndicator state={saveState} /> : null}
            {!isApproved && serverContent ? (
              <>
                <Button variant="secondary" onClick={() => generate.mutate()} loading={generate.isPending}>
                  <RotateCcw className="size-4" aria-hidden />
                  重新生成
                </Button>
                <Button variant="secondary" onClick={() => doSave()} loading={save.isPending} disabled={!dirty}>
                  保存草稿
                </Button>
                <Button
                  onClick={() => {
                    if (!division.data) return;
                    approve.mutate(division.data.artifact_version_id, {
                      onSuccess: () => toast({ tone: "success", title: "课时划分已确认", description: "各课时工作流已建立，可进入课时开始制作。" }),
                    });
                  }}
                  loading={approve.isPending}
                  disabled={dirty}
                  title={dirty ? "请先保存草稿" : undefined}
                >
                  <CheckCircle2 className="size-4" aria-hidden />
                  确认划分
                </Button>
              </>
            ) : null}
          </>
        }
      />

      {isApproved ? (
        <p className="rounded-control bg-success-surface px-3 py-2 text-sm text-success">
          课时划分已确认（第 {division.data?.version_number} 版）。调整课时需重新生成划分，已生成的课时内容会标记为失效。
        </p>
      ) : null}

      {division.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      ) : noDivision ? (
        <EmptyState
          title="还没有课时划分"
          description={
            project.textbook_status === "evidence_ready"
              ? "教材证据已就绪，可以生成课时划分建议。"
              : "建议先在「教材」页上传并解析教材，再生成课时划分。"
          }
          action={
            <Button onClick={() => generate.mutate()} loading={generate.isPending}>
              生成课时划分
            </Button>
          }
        />
      ) : division.isError ? (
        <AppErrorPanel error={division.error} title="课时划分加载失败" onRetry={() => void division.refetch()} />
      ) : draft ? (
        <>
          {draft.rationale ? <p className="rounded-control bg-surface-2 px-3 py-2 text-xs leading-5 text-ink-2">划分依据：{draft.rationale}</p> : null}
          <ul className="space-y-2">
            {draft.lessons.map((lesson, index) => (
              <LessonRow
                key={lesson.lesson_key}
                lesson={lesson}
                index={index}
                editable={editable}
                onChange={(next) =>
                  setDraft((prev) => (prev ? { ...prev, lessons: prev.lessons.map((l, i) => (i === index ? next : l)) } : prev))
                }
                onRemove={() => setDraft((prev) => (prev ? { ...prev, lessons: prev.lessons.filter((_, i) => i !== index) } : prev))}
              />
            ))}
          </ul>
          {editable ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                setDraft((prev) =>
                  prev
                    ? {
                        ...prev,
                        lessons: [
                          ...prev.lessons,
                          {
                            lesson_key: `custom_${prev.lessons.length + 1}_${Math.random().toString(36).slice(2, 7)}`,
                            title: "新课时",
                            lesson_type: "new_knowledge",
                            duration_minutes: 40,
                            knowledge_points: [],
                            textbook_pages: "",
                            objectives: "",
                          },
                        ],
                      }
                    : prev,
                )
              }
            >
              <Plus className="size-4" aria-hidden />
              添加课时
            </Button>
          ) : null}
          {(versions.data ?? []).length > 1 ? (
            <p className="text-xs text-ink-muted">
              历史版本：
              {(versions.data ?? []).map((version) => (
                <Badge key={version.artifact_version_id} tone="neutral" className="ml-1">
                  V{version.version_number}
                </Badge>
              ))}
            </p>
          ) : null}
        </>
      ) : null}

      {generate.isError ? <AppErrorPanel error={generate.error} title="课时划分生成失败" onRetry={() => generate.mutate()} /> : null}
      {approve.isError ? <AppErrorPanel error={approve.error} title="确认失败" /> : null}

      <ConflictDialog
        open={conflictOpen}
        onOpenChange={setConflictOpen}
        serverRowVersion={serverRowVersion}
        onKeepMine={() => {
          setConflictOpen(false);
          if (serverRowVersion) doSave(serverRowVersion);
        }}
        onUseServer={() => {
          setConflictOpen(false);
          void division.refetch();
        }}
      />
    </div>
  );
}
