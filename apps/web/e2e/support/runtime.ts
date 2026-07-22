import type { Page } from "@playwright/test";

const storageKey = "shanhaiedu.mock-runtime.v1";

const prerequisiteChains: Record<string, string[]> = {
  "ppt-outline": ["lesson-plan"],
  "ppt-cover": ["lesson-plan", "ppt-outline", "ppt-design"],
  "ppt-pages": ["lesson-plan", "ppt-outline", "ppt-design", "ppt-cover"],
  "ppt-export": ["lesson-plan", "ppt-outline", "ppt-design", "ppt-cover", "ppt-pages"],
  "master-script": ["intro-options"],
  "rough-storyboard": ["intro-options", "master-script"],
  "video-style": ["intro-options", "master-script", "rough-storyboard"],
  "video-assets": [
    "intro-options",
    "master-script",
    "rough-storyboard",
    "video-style",
    "video-asset-plan",
  ],
  "fine-storyboard": [
    "intro-options",
    "master-script",
    "rough-storyboard",
    "video-style",
    "video-asset-plan",
    "video-assets",
  ],
  "final-video": [
    "intro-options",
    "master-script",
    "rough-storyboard",
    "video-style",
    "video-asset-plan",
    "video-assets",
    "fine-storyboard",
  ],
};

export async function unlockWorkbenchStep(
  page: Page,
  projectId: string,
  lessonId: string,
  stepKey: string,
) {
  const nodeKeys = prerequisiteChains[stepKey] ?? [];
  await page.evaluate(
    ({ keys, lesson, project, runtimeStorageKey }) => {
      const raw = window.localStorage.getItem(runtimeStorageKey);
      if (!raw) throw new Error("Mock runtime 尚未初始化");
      const runtime = JSON.parse(raw) as {
        nodeStates: Record<string, Record<string, unknown>>;
      };
      const now = new Date().toISOString();
      for (const nodeKey of keys) {
        const key = `${project}:${lesson}:${nodeKey}`;
        const previous = runtime.nodeStates[key] ?? {};
        runtime.nodeStates[key] = {
          ...previous,
          id: previous.id ?? `e2e-${nodeKey}`,
          lesson_id: lesson,
          node_key: nodeKey,
          project_id: project,
          revision: typeof previous.revision === "number" ? previous.revision : 1,
          stale_reason: null,
          status: "approved",
          title: nodeKey,
          updated_at: now,
        };
      }
      window.localStorage.setItem(runtimeStorageKey, JSON.stringify(runtime));
    },
    { keys: nodeKeys, lesson: lessonId, project: projectId, runtimeStorageKey: storageKey },
  );
}
