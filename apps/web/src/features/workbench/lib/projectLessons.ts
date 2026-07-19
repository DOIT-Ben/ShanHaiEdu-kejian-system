import type { LessonSummary } from "@/entities/project/model";
import { demoProjectId, lessons as demoLessons } from "@/shared/data/mockData";
import type { MockRuntimeState } from "@/shared/api/mocks/runtime";

function isLessonSummary(value: unknown): value is LessonSummary {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const lesson = value as Record<string, unknown>;
  return (
    typeof lesson.id === "string" && lesson.id.trim().length > 0 && typeof lesson.title === "string"
  );
}

export function readLessonList(value: unknown): LessonSummary[] | null {
  return Array.isArray(value) && value.every(isLessonSummary) ? value : null;
}

export function getCurrentProjectLessons(runtime: MockRuntimeState, projectId: string) {
  const saved = readLessonList(runtime.drafts[`project:${projectId}:lessons`]?.value);
  if (saved) return saved;
  return projectId === demoProjectId ? demoLessons : [];
}

export function getApprovedProjectLessons(runtime: MockRuntimeState, projectId: string) {
  const division = runtime.nodeStates[`${projectId}:*:lesson-division`];
  if (division?.status !== "approved") return [];
  const approved = readLessonList(runtime.drafts[`project:${projectId}:lessons-approved`]?.value);
  return (approved ?? []).map((lesson) => ({
    ...lesson,
    planStatus:
      runtime.nodeStates[`${projectId}:${lesson.id}:lesson-plan`]?.status ?? lesson.planStatus,
    introStatus:
      runtime.nodeStates[`${projectId}:${lesson.id}:intro-options`]?.status ?? lesson.introStatus,
    pptStatus:
      runtime.nodeStates[`${projectId}:${lesson.id}:ppt-pages`]?.status ?? lesson.pptStatus,
    videoStatus:
      runtime.nodeStates[`${projectId}:${lesson.id}:final-video`]?.status ?? lesson.videoStatus,
  }));
}

export function isApprovedLessonId(runtime: MockRuntimeState, lessonId: string) {
  return runtime.projects.some((project) =>
    getApprovedProjectLessons(runtime, project.id).some((lesson) => lesson.id === lessonId),
  );
}

export function getChangedLessonIds(
  previous: readonly LessonSummary[],
  next: readonly LessonSummary[],
) {
  const previousById = new Map(previous.map((lesson, index) => [lesson.id, { lesson, index }]));
  const nextById = new Map(next.map((lesson, index) => [lesson.id, { lesson, index }]));
  const changed = new Set<string>();
  for (const id of new Set([...previousById.keys(), ...nextById.keys()])) {
    const previousEntry = previousById.get(id);
    const nextEntry = nextById.get(id);
    if (!previousEntry || !nextEntry) {
      changed.add(id);
      continue;
    }
    if (
      previousEntry.index !== nextEntry.index ||
      previousEntry.lesson.title !== nextEntry.lesson.title ||
      previousEntry.lesson.scope !== nextEntry.lesson.scope ||
      previousEntry.lesson.duration !== nextEntry.lesson.duration
    ) {
      changed.add(id);
    }
  }
  return changed;
}
