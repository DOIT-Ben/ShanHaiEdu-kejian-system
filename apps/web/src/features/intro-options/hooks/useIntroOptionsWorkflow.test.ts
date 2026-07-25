import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import {
  introOptionsArtifactKey,
  introOptionsJobsKey,
  introOptionsPublicKey,
} from "@/features/intro-options/hooks/useIntroOptionsWorkflow";

const projectId = "01960000-0000-7000-8000-000000000001";
const firstLessonId = "01960000-0000-7000-8000-000000000002";
const secondLessonId = "01960000-0000-7000-8000-000000000003";

describe("intro options workflow query keys", () => {
  it("keeps artifact, job, and selection facts isolated between lessons", () => {
    const queryClient = new QueryClient();
    const keys = [
      introOptionsArtifactKey(projectId, firstLessonId),
      introOptionsArtifactKey(projectId, secondLessonId),
      introOptionsJobsKey(projectId, firstLessonId),
      introOptionsJobsKey(projectId, secondLessonId),
      introOptionsPublicKey(firstLessonId),
      introOptionsPublicKey(secondLessonId),
    ] as const;

    keys.forEach((key, index) => queryClient.setQueryData(key, { marker: index }));
    keys.forEach((key, index) => expect(queryClient.getQueryData(key)).toEqual({ marker: index }));
    expect(new Set(keys.map((key) => JSON.stringify(key))).size).toBe(keys.length);
  });
});
