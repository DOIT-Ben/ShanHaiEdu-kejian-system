import { afterEach, describe, expect, it, vi } from "vitest";
import { getLessonIntroOptions, selectLessonIntroOption } from "./introOptionsApi";
import { configureCsrfTokenProvider } from "@/shared/api/client";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

describe("R1 Intro options API", () => {
  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("读取课时方案并创建 exact ArtifactVersion 的唯一选择", async () => {
    configureCsrfTokenProvider(() => "csrf-r1-intro");
    const lessonId = "01960000-0000-7000-8000-000000000001";
    const versionId = "01960000-0000-7000-8000-000000000002";
    const options = {
      artifact_id: "01960000-0000-7000-8000-000000000003",
      current_approved_version_id: versionId,
      current_selection: null,
      display_version: null,
      pending_version: null,
    };
    const selection = {
      active: true,
      artifact_version_id: versionId,
      consumable: true,
      deactivated_at: null,
      option_key: "INTRO-SCI-01",
      reason: "teacher_selected",
      selected_at: "2026-07-25T00:00:00Z",
      selection_id: "01960000-0000-7000-8000-000000000004",
      selection_method: "teacher_selected",
      snapshot: {},
      unconsumable_reason: null,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ data: options, request_id: "intro-options" }))
      .mockResolvedValueOnce(jsonResponse({ data: selection, request_id: "intro-select" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getLessonIntroOptions(lessonId)).resolves.toEqual(options);
    await expect(
      selectLessonIntroOption({
        artifactVersionId: versionId,
        idempotencyKey: "select-intro-option-1",
        lessonId,
        optionKey: "INTRO-SCI-01",
      }),
    ).resolves.toEqual(selection);

    const selectionRequest = fetchMock.mock.calls[1]?.[0] as Request;
    expect(selectionRequest.url).toContain(`/lessons/${lessonId}/intro-selections`);
    expect(selectionRequest.headers.get("Idempotency-Key")).toBe("select-intro-option-1");
    await expect(selectionRequest.json()).resolves.toEqual({
      artifact_version_id: versionId,
      option_key: "INTRO-SCI-01",
    });
  });
});
