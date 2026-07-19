import { beforeEach, describe, expect, it } from "vitest";
import {
  getApprovedProjectLessons,
  getChangedLessonIds,
  isApprovedLessonId,
  readLessonList,
} from "@/features/workbench/lib/projectLessons";
import { createDefaultMockRuntimeState } from "@/shared/api/mocks/runtime";
import { demoLessonId, lessons } from "@/shared/data/mockData";
import { requiredItem } from "@/shared/lib/requiredItem";

describe("project lesson version boundaries", () => {
  beforeEach(() => localStorage.clear());

  it("does not treat derived status fields as a structural lesson change", () => {
    const next = lessons.map((lesson, index) =>
      index === 0 ? { ...lesson, planStatus: "approved" as const } : lesson,
    );

    expect(getChangedLessonIds(lessons, next)).toEqual(new Set());
  });

  it("only marks the changed, moved, added, or removed lesson ids", () => {
    const firstLesson = requiredItem(lessons, 0, "第一个课时");
    const secondLesson = requiredItem(lessons, 1, "第二个课时");
    const next = [
      { ...firstLesson, scope: "调整后的范围" },
      { ...secondLesson },
      { ...secondLesson, id: "new-lesson", title: "新增课时" },
    ];

    expect(getChangedLessonIds(lessons, next)).toEqual(new Set([firstLesson.id, "new-lesson"]));
  });

  it("没有批准快照时不把可变草稿当成已批准课时", () => {
    const runtime = createDefaultMockRuntimeState();
    const project = requiredItem(runtime.projects, 0, "默认项目");
    const approvedKey = `project:${project.id}:lessons-approved`;
    runtime.drafts = Object.fromEntries(
      Object.entries(runtime.drafts).filter(([key]) => key !== approvedKey),
    );
    expect(getApprovedProjectLessons(runtime, runtime.projects[0]?.id ?? "")).toEqual([]);
  });

  it("拒绝包含无效课时记录的缓存", () => {
    expect(readLessonList([{ id: "valid", title: "课时" }, null])).toBeNull();
  });

  it("只承认批准快照中的课时 id", () => {
    const runtime = createDefaultMockRuntimeState();
    expect(isApprovedLessonId(runtime, demoLessonId)).toBe(true);
    expect(isApprovedLessonId(runtime, "not-a-real-lesson")).toBe(false);
  });
});
