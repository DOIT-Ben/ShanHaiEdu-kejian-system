import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getLesson,
  listProjectLessons,
  updateLessonBranches,
  updateProjectLessons,
  type UpdateLessonBranchesRequest,
  type UpdateLessonCollectionRequest,
} from "@/features/lessons/api/lessonsApi";
import { LessonCollectionEditor } from "@/features/lessons/components/LessonCollectionEditor";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { isRuntimeConflict, runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

type BranchIntent = {
  baseEtag: string;
  branches: UpdateLessonBranchesRequest["branches"];
  lessonId: string;
};

type CollectionIntent = {
  baseEtag: string;
  items: UpdateLessonCollectionRequest["items"];
};

type LessonSnapshot = Awaited<ReturnType<typeof getLesson>>;

const emptyLessons = [] as const;

function combineLessonSnapshots(results: { data: LessonSnapshot | undefined }[]) {
  return results.map((result) => result.data);
}

export function RuntimeLessonsPage() {
  const { projectId } = useParams();
  const queryClient = useQueryClient();
  useProjectEvents(projectId);

  const lessonsKey = ["projects", projectId, "lessons"] as const;
  const lessonsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => listProjectLessons(projectId ?? ""),
    queryKey: lessonsKey,
  });
  const lessonRows = lessonsQuery.data?.lessons ?? emptyLessons;
  const lessonQueryOptions = useMemo(
    () =>
      lessonRows.map((lesson) => ({
        enabled: Boolean(projectId),
        queryFn: () => getLesson(lesson.id),
        queryKey: ["lessons", lesson.id] as const,
      })),
    [lessonRows, projectId],
  );
  const lessonSnapshots = useQueries({
    queries: lessonQueryOptions,
    combine: combineLessonSnapshots,
  });
  const editorLessons = useMemo(
    () =>
      lessonRows.map((lesson, index) => {
        const branchSnapshot = lessonSnapshots[index]?.lesson;
        return branchSnapshot ? { ...lesson, branches: branchSnapshot.branches } : lesson;
      }),
    [lessonRows, lessonSnapshots],
  );
  const lessonEtags = useMemo(
    () =>
      Object.fromEntries(
        lessonRows.map((lesson, index) => [lesson.id, lessonSnapshots[index]?.etag]),
      ),
    [lessonRows, lessonSnapshots],
  );
  const refreshLessons = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ exact: true, queryKey: lessonsKey }),
      queryClient.invalidateQueries({ exact: false, queryKey: ["lessons"] }),
    ]);
  };
  const collectionMutation = useMutation({
    mutationFn: ({ baseEtag, items }: CollectionIntent) => {
      if (!projectId) throw new Error("LESSON_COLLECTION_PROJECT_MISSING");
      return updateProjectLessons({
        etag: baseEtag,
        idempotencyKey: crypto.randomUUID(),
        input: { items },
        projectId,
      });
    },
    onSuccess: refreshLessons,
  });
  const branchMutation = useMutation({
    mutationFn: ({ baseEtag, branches, lessonId }: BranchIntent) => {
      return updateLessonBranches({
        etag: baseEtag,
        idempotencyKey: crypto.randomUUID(),
        input: { branches },
        lessonId,
      });
    },
    onSuccess: refreshLessons,
  });

  if (!projectId) return null;

  const mutationError = collectionMutation.error ?? branchMutation.error;
  const conflictMessage = mutationError
    ? isRuntimeConflict(mutationError)
      ? "课时已经被其他操作更新。请刷新后确认最新内容，再重新保存。"
      : runtimeErrorMessage(mutationError, "课时没有保存，请检查网络后重试。")
    : undefined;
  const writeReady = isCsrfTokenAvailable();
  const disabled = !writeReady || !lessonsQuery.data?.etag || lessonsQuery.isFetching;

  return (
    <div className="mx-auto max-w-[980px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          <Link
            className={buttonVariants({ variant: "secondary" })}
            to={`/app/projects/${projectId}`}
          >
            <ArrowLeft aria-hidden="true" />
            返回项目
          </Link>
        }
        description="编辑课时范围、目标、时长与分支设置。保存时会校验最新版本。"
        title="课时安排"
      />

      <div className="mt-5">
        {lessonsQuery.isLoading ? (
          <div
            className="h-52 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
            role="status"
          >
            <span className="sr-only">正在读取课时</span>
          </div>
        ) : lessonsQuery.isError ? (
          <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
            <p className="text-sm text-[var(--sh-danger)]" role="alert">
              {runtimeErrorMessage(lessonsQuery.error, "课时暂时无法读取，请稍后重试。")}
            </p>
            <Button
              className="mt-4"
              onClick={() => void lessonsQuery.refetch()}
              variant="secondary"
            >
              重新读取课时
            </Button>
          </section>
        ) : (
          <>
            {!writeReady ? (
              <p
                className="mb-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning)]"
                role="status"
              >
                当前会话仅支持查看课时，无法保存。
              </p>
            ) : null}
            <LessonCollectionEditor
              collectionEtag={lessonsQuery.data?.etag}
              conflictMessage={conflictMessage}
              disabled={disabled}
              lessonEtags={lessonEtags}
              lessons={editorLessons}
              onSaveBranches={(lessonId, branches, baseEtag) =>
                branchMutation.mutateAsync({ baseEtag, branches, lessonId })
              }
              onSaveCollection={(items, baseEtag) =>
                collectionMutation.mutateAsync({ baseEtag, items })
              }
              savingCollection={collectionMutation.isPending}
              savingLessonId={
                branchMutation.isPending ? branchMutation.variables.lessonId : undefined
              }
            />
          </>
        )}
      </div>
    </div>
  );
}
