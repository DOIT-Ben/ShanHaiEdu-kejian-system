import { mockProjects } from "@/shared/api/mocks/fixtures";
import type { MockRuntimeState, MockTextbookFile } from "@/shared/api/mocks/runtimeTypes";
import { demoLessonId, demoProjectId, lessons, taskItems } from "@/shared/data/mockData";

function clone<T>(value: T): T {
  if (typeof globalThis.structuredClone === "function") return globalThis.structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as T;
}

export function createDefaultMockRuntimeState(): MockRuntimeState {
  const textbookFiles: Record<string, MockTextbookFile[]> = {
    [demoProjectId]: [
      {
        id: "01960000-0000-7000-8000-000000000401",
        project_id: demoProjectId,
        name: "百分数教材节选.pdf",
        size: 2_458_624,
        type: "application/pdf",
        last_modified: null,
        status: "ready",
        created_at: "2026-07-12T02:01:00Z",
      },
    ],
  };
  return {
    schemaVersion: 1,
    projects: clone(mockProjects),
    textbookFiles,
    nodeStates: {
      [`${demoProjectId}:*:lesson-division`]: {
        id: "01960000-0000-7000-8000-000000000200",
        project_id: demoProjectId,
        lesson_id: null,
        node_key: "lesson-division",
        title: "安排课时",
        status: "approved",
        revision: 1,
        updated_at: "2026-07-12T02:20:00Z",
        stale_reason: null,
      },
      [`${demoProjectId}:${demoLessonId}:lesson-plan`]: {
        id: "01960000-0000-7000-8000-000000000201",
        project_id: demoProjectId,
        lesson_id: demoLessonId,
        node_key: "lesson-plan",
        title: "生成教案",
        status: "review_required",
        revision: 3,
        updated_at: "2026-07-17T02:24:00Z",
        stale_reason: null,
      },
    },
    tasks: taskItems.map((task, index) => ({
      ...task,
      project_id: index === 0 ? demoProjectId : null,
      node_run_id: index === 0 ? "01960000-0000-7000-8000-000000000201" : null,
      progress: task.status === "running" ? 68 : task.status === "partially_completed" ? 75 : 100,
      retry_count: 0,
      updated_at: "2026-07-17T02:24:00Z",
    })),
    saveConflicts: [],
    drafts: {
      [`project:${demoProjectId}:lessons`]: {
        key: `project:${demoProjectId}:lessons`,
        value: clone(lessons),
        project_id: demoProjectId,
        lesson_id: null,
        node_key: "lesson-division",
        revision: 1,
        updated_at: "2026-07-12T02:20:00Z",
      },
      [`project:${demoProjectId}:lessons-approved`]: {
        key: `project:${demoProjectId}:lessons-approved`,
        value: clone(lessons),
        project_id: demoProjectId,
        lesson_id: null,
        node_key: "lesson-division",
        revision: 1,
        updated_at: "2026-07-12T02:20:00Z",
      },
    },
    session: null,
  };
}
