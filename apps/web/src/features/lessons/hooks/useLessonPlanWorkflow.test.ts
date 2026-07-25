import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import {
  lessonPlanArtifactKey,
  lessonPlanJobsKey,
} from "@/features/lessons/hooks/useLessonPlanWorkflow";

const projectId = "01960000-0000-7000-8000-000000000001";
const firstLessonId = "01960000-0000-7000-8000-000000000002";
const secondLessonId = "01960000-0000-7000-8000-000000000003";

describe("lesson plan workflow query keys", () => {
  it("keeps artifact and job facts isolated between lessons", () => {
    const queryClient = new QueryClient();
    const firstArtifactKey = lessonPlanArtifactKey(projectId, firstLessonId);
    const secondArtifactKey = lessonPlanArtifactKey(projectId, secondLessonId);
    const firstJobsKey = lessonPlanJobsKey(projectId, firstLessonId);
    const secondJobsKey = lessonPlanJobsKey(projectId, secondLessonId);

    queryClient.setQueryData(firstArtifactKey, { artifactId: "artifact-lesson-1" });
    queryClient.setQueryData(secondArtifactKey, { artifactId: "artifact-lesson-2" });
    queryClient.setQueryData(firstJobsKey, [{ id: "job-lesson-1" }]);
    queryClient.setQueryData(secondJobsKey, [{ id: "job-lesson-2" }]);

    expect(queryClient.getQueryData(firstArtifactKey)).toEqual({
      artifactId: "artifact-lesson-1",
    });
    expect(queryClient.getQueryData(secondArtifactKey)).toEqual({
      artifactId: "artifact-lesson-2",
    });
    expect(queryClient.getQueryData(firstJobsKey)).toEqual([{ id: "job-lesson-1" }]);
    expect(queryClient.getQueryData(secondJobsKey)).toEqual([{ id: "job-lesson-2" }]);
    expect(firstArtifactKey).not.toEqual(secondArtifactKey);
    expect(firstJobsKey).not.toEqual(secondJobsKey);
  });
});
