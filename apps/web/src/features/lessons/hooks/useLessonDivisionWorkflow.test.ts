import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import {
  lessonDivisionArtifactKey,
  lessonDivisionJobsKey,
} from "@/features/lessons/hooks/useLessonDivisionWorkflow";

describe("lesson division workflow query keys", () => {
  it("keeps artifact and job facts isolated between projects", () => {
    const queryClient = new QueryClient();
    const firstArtifactKey = lessonDivisionArtifactKey("project-1");
    const secondArtifactKey = lessonDivisionArtifactKey("project-2");
    const firstJobsKey = lessonDivisionJobsKey("project-1");
    const secondJobsKey = lessonDivisionJobsKey("project-2");

    queryClient.setQueryData(firstArtifactKey, { id: "artifact-1" });
    queryClient.setQueryData(secondArtifactKey, { id: "artifact-2" });
    queryClient.setQueryData(firstJobsKey, [{ id: "job-1" }]);
    queryClient.setQueryData(secondJobsKey, [{ id: "job-2" }]);

    expect(queryClient.getQueryData(firstArtifactKey)).toEqual({ id: "artifact-1" });
    expect(queryClient.getQueryData(secondArtifactKey)).toEqual({ id: "artifact-2" });
    expect(queryClient.getQueryData(firstJobsKey)).toEqual([{ id: "job-1" }]);
    expect(queryClient.getQueryData(secondJobsKey)).toEqual([{ id: "job-2" }]);
    expect(firstArtifactKey).not.toEqual(secondArtifactKey);
    expect(firstJobsKey).not.toEqual(secondJobsKey);
  });
});
