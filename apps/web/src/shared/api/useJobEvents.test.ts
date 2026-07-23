import { describe, expect, it, vi } from "vitest";
import { jobEventQueryKeys, readJobLastSequence, streamJobEvents } from "@/shared/api/useJobEvents";

const jobEvent = {
  event_id: "01960000-0000-7000-8000-000000000902",
  sequence_no: 7,
  event_type: "generation.job.progress",
  occurred_at: "2026-07-20T00:00:00Z",
  project_id: "01960000-0000-7000-8000-000000000001",
  resource: {
    type: "generation_job",
    id: "01960000-0000-7000-8000-000000000701",
  },
  payload: { status: "succeeded" },
  request_id: null,
} as const;

describe("generation job event transport", () => {
  it("uses the job stream and resumes from its positive sequence", async () => {
    sessionStorage.setItem("shanhaiedu.events.job.job-1.sequence", "6");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(`id: 7\nevent: generation.job.progress\ndata: ${JSON.stringify(jobEvent)}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
        status: 200,
      }),
    );
    const onEvent = vi.fn();

    await streamJobEvents({
      fetchImpl: fetchMock,
      jobId: "job-1",
      lastSequence: readJobLastSequence("job-1"),
      onEvent,
    });

    expect(fetchMock.mock.calls[0]?.[0]).toContain("/generation-jobs/job-1/events/stream");
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("Last-Event-ID")).toBe("6");
    expect(onEvent).toHaveBeenCalledWith(jobEvent);
  });

  it("invalidates only the job snapshot and its project task list", () => {
    expect(jobEventQueryKeys("job-1", "project-1")).toEqual([
      ["generation-jobs", "job-1"],
      ["tasks", "project-1"],
    ]);
    expect(jobEventQueryKeys("job-1")).toEqual([["generation-jobs", "job-1"]]);
  });
});
