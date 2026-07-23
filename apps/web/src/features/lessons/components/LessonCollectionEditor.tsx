import { TooltipProvider } from "@radix-ui/react-tooltip";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type {
  LessonDto,
  UpdateLessonBranchesRequest,
  UpdateLessonCollectionRequest,
} from "@/features/lessons/api/lessonsApi";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

type LessonItem = UpdateLessonCollectionRequest["items"][number];
type LessonBranches = UpdateLessonBranchesRequest["branches"];

type LessonCollectionEditorProps = {
  collectionEtag: string | undefined;
  conflictMessage?: string;
  disabled?: boolean;
  lessonEtags: Readonly<Record<string, string | undefined>>;
  lessons: readonly LessonDto[];
  onSaveBranches: (
    lessonId: string,
    branches: LessonBranches,
    baseEtag: string,
  ) => Promise<unknown> | undefined;
  onSaveCollection: (items: LessonItem[], baseEtag: string) => Promise<unknown> | undefined;
  savingCollection?: boolean;
  savingLessonId?: string;
};

const branchLabels: Record<LessonBranches[number]["branch_key"], string> = {
  intro_options: "课堂导入",
  lesson_plan: "教案",
  ppt: "课堂 PPT",
  video: "课堂视频",
};

function editableLesson(lesson: LessonDto): LessonItem {
  return {
    estimated_minutes: lesson.estimated_minutes,
    id: lesson.id,
    objective_summary: lesson.objective_summary,
    position: lesson.position,
    scope_summary: lesson.scope_summary,
    title: lesson.title,
  };
}

function editableBranches(lesson: LessonDto): LessonBranches {
  return lesson.branches.map(({ branch_key, enabled, settings }) => ({
    branch_key,
    enabled,
    settings,
  }));
}

function normalizeItems(items: readonly LessonItem[]) {
  return items.map((item, index) => ({ ...item, position: index + 1 }));
}

function editableLessons(lessons: readonly LessonDto[]) {
  return normalizeItems(
    [...lessons].sort((left, right) => left.position - right.position).map(editableLesson),
  );
}

function editableBranchRecord(lessons: readonly LessonDto[]) {
  return Object.fromEntries(lessons.map((lesson) => [lesson.id, editableBranches(lesson)]));
}

export function LessonCollectionEditor({
  collectionEtag,
  conflictMessage,
  disabled = false,
  lessonEtags,
  lessons,
  onSaveBranches,
  onSaveCollection,
  savingCollection = false,
  savingLessonId,
}: LessonCollectionEditorProps) {
  const [items, setItems] = useState<LessonItem[]>(() => editableLessons(lessons));
  const [branches, setBranches] = useState<Record<string, LessonBranches>>(() =>
    editableBranchRecord(lessons),
  );
  const [collectionDirty, setCollectionDirty] = useState(false);
  const [dirtyBranches, setDirtyBranches] = useState<Record<string, boolean>>({});
  const collectionBaseEtag = useRef(collectionEtag);
  const collectionDirtyRef = useRef(false);
  const collectionRevision = useRef(0);
  const branchBaseEtags = useRef<Record<string, string | undefined>>({});
  const dirtyBranchRefs = useRef<Record<string, boolean>>({});
  const branchRevisions = useRef<Record<string, number>>({});

  useEffect(() => {
    if (!collectionDirtyRef.current && !collectionDirty) {
      collectionBaseEtag.current = collectionEtag;
      setItems(editableLessons(lessons));
    }
    lessons.forEach((lesson) => {
      if (!dirtyBranchRefs.current[lesson.id] && !dirtyBranches[lesson.id]) {
        branchBaseEtags.current[lesson.id] = lessonEtags[lesson.id];
      }
    });
    setBranches((current) =>
      Object.fromEntries(
        lessons.map((lesson) => {
          const currentBranches = current[lesson.id];
          return [
            lesson.id,
            dirtyBranches[lesson.id] && currentBranches
              ? currentBranches
              : editableBranches(lesson),
          ];
        }),
      ),
    );
  }, [collectionDirty, collectionEtag, dirtyBranches, lessonEtags, lessons]);

  const changeItems = (change: (current: LessonItem[]) => LessonItem[]) => {
    if (!collectionDirtyRef.current) {
      collectionDirtyRef.current = true;
    }
    collectionRevision.current += 1;
    setCollectionDirty(true);
    setItems((current) => normalizeItems(change(current)));
  };

  const updateItem = (lessonId: string, patch: Partial<LessonItem>) =>
    changeItems((current) =>
      current.map((item) => (item.id === lessonId ? { ...item, ...patch } : item)),
    );

  const moveItem = (index: number, offset: -1 | 1) => {
    const nextIndex = index + offset;
    if (nextIndex < 0 || nextIndex >= items.length) return;
    changeItems((current) => {
      const next = [...current];
      const currentItem = next[index];
      const targetItem = next[nextIndex];
      if (!currentItem || !targetItem) return current;
      next[index] = targetItem;
      next[nextIndex] = currentItem;
      return next;
    });
  };

  const removeItem = (lessonId: string) => {
    if (items.length <= 1) return;
    changeItems((current) => current.filter((item) => item.id !== lessonId));
  };

  const updateBranch = (
    lessonId: string,
    branchKey: LessonBranches[number]["branch_key"],
    enabled: boolean,
  ) => {
    if (!dirtyBranchRefs.current[lessonId]) {
      dirtyBranchRefs.current[lessonId] = true;
    }
    branchRevisions.current[lessonId] = (branchRevisions.current[lessonId] ?? 0) + 1;
    setDirtyBranches((current) => ({ ...current, [lessonId]: true }));
    setBranches((current) => ({
      ...current,
      [lessonId]: (current[lessonId] ?? []).map((candidate) =>
        candidate.branch_key === branchKey ? { ...candidate, enabled } : candidate,
      ),
    }));
  };

  const saveCollection = async () => {
    const baseEtag = collectionBaseEtag.current;
    if (!baseEtag) return;
    const revision = collectionRevision.current;
    const payload = normalizeItems(items);
    setItems(payload);
    try {
      await onSaveCollection(payload, baseEtag);
    } catch {
      return;
    }
    if (collectionRevision.current === revision) {
      collectionDirtyRef.current = false;
      setCollectionDirty(false);
    }
  };

  const saveBranches = async (lessonId: string, lessonBranches: LessonBranches) => {
    const baseEtag = branchBaseEtags.current[lessonId];
    if (!baseEtag) return;
    const revision = branchRevisions.current[lessonId] ?? 0;
    try {
      await onSaveBranches(lessonId, lessonBranches, baseEtag);
    } catch {
      return;
    }
    if ((branchRevisions.current[lessonId] ?? 0) === revision) {
      dirtyBranchRefs.current[lessonId] = false;
      setDirtyBranches((current) => ({ ...current, [lessonId]: false }));
    }
  };

  if (!items.length) {
    return (
      <p className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 text-sm text-[var(--sh-ink-muted)]">
        当前项目还没有可编辑的课时。
      </p>
    );
  }

  return (
    <TooltipProvider delayDuration={300}>
      <div className="space-y-4">
        {conflictMessage ? (
          <p
            className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning)]"
            role="alert"
          >
            {conflictMessage}
          </p>
        ) : null}
        {items.map((item, index) => {
          const lessonBranches = branches[item.id] ?? [];
          return (
            <article
              className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5"
              key={item.id}
            >
              <div className="mb-4 flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">
                  课时 {index + 1}
                </p>
                <div
                  aria-label={`${item.title}的排序和归档操作`}
                  className="flex shrink-0 items-center gap-1"
                  role="group"
                >
                  <IconButton
                    disabled={disabled || index === 0}
                    label={`上移${item.title}`}
                    onClick={() => moveItem(index, -1)}
                  >
                    <ArrowUp aria-hidden="true" />
                  </IconButton>
                  <IconButton
                    disabled={disabled || index === items.length - 1}
                    label={`下移${item.title}`}
                    onClick={() => moveItem(index, 1)}
                  >
                    <ArrowDown aria-hidden="true" />
                  </IconButton>
                  <IconButton
                    className="text-[var(--sh-danger)] hover:text-[var(--sh-danger-strong)]"
                    disabled={disabled || items.length <= 1}
                    label={`移除${item.title}`}
                    onClick={() => removeItem(item.id)}
                  >
                    <Trash2 aria-hidden="true" />
                  </IconButton>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium text-[var(--sh-ink-default)]">
                  课时 {index + 1} 名称
                  <input
                    className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-transparent px-3"
                    disabled={disabled}
                    onChange={(event) => updateItem(item.id, { title: event.target.value })}
                    value={item.title}
                  />
                </label>
                <label className="text-sm font-medium text-[var(--sh-ink-default)]">
                  预计分钟
                  <input
                    className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-transparent px-3"
                    disabled={disabled}
                    min={1}
                    onChange={(event) =>
                      updateItem(item.id, {
                        estimated_minutes: event.target.value ? Number(event.target.value) : null,
                      })
                    }
                    type="number"
                    value={item.estimated_minutes ?? ""}
                  />
                </label>
                <label className="text-sm font-medium text-[var(--sh-ink-default)] md:col-span-2">
                  内容范围
                  <textarea
                    className="mt-2 min-h-20 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-transparent p-3"
                    disabled={disabled}
                    onChange={(event) => updateItem(item.id, { scope_summary: event.target.value })}
                    value={item.scope_summary}
                  />
                </label>
                <label className="text-sm font-medium text-[var(--sh-ink-default)] md:col-span-2">
                  学习目标
                  <textarea
                    className="mt-2 min-h-20 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-transparent p-3"
                    disabled={disabled}
                    onChange={(event) =>
                      updateItem(item.id, { objective_summary: event.target.value })
                    }
                    value={item.objective_summary}
                  />
                </label>
              </div>
              <fieldset
                className="mt-5 border-t border-[var(--sh-line-subtle)] pt-4"
                disabled={disabled || !lessonEtags[item.id]}
              >
                <legend className="text-sm font-semibold text-[var(--sh-ink-strong)]">
                  课时分支
                </legend>
                <div className="mt-3 flex flex-wrap gap-4">
                  {lessonBranches.map((branch) => (
                    <label
                      className="inline-flex items-center gap-2 text-sm text-[var(--sh-ink-default)]"
                      key={branch.branch_key}
                    >
                      <input
                        checked={branch.enabled}
                        onChange={(event) =>
                          updateBranch(item.id, branch.branch_key, event.target.checked)
                        }
                        type="checkbox"
                      />
                      {branchLabels[branch.branch_key]}
                    </label>
                  ))}
                </div>
                <Button
                  className="mt-4"
                  disabled={!lessonEtags[item.id] || savingLessonId === item.id}
                  onClick={() => void saveBranches(item.id, lessonBranches)}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  {savingLessonId === item.id ? "正在保存分支" : `保存${item.title}的分支`}
                </Button>
              </fieldset>
            </article>
          );
        })}
        <div className="flex justify-end">
          <Button
            disabled={disabled || !collectionEtag || savingCollection}
            onClick={() => void saveCollection()}
          >
            {savingCollection ? "正在保存课时" : "保存课时集合"}
          </Button>
        </div>
      </div>
    </TooltipProvider>
  );
}
