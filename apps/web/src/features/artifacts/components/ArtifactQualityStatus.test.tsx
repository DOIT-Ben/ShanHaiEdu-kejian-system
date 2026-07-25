import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AcceptedNodeRunDto } from "@/features/artifacts/api/artifactsApi";
import { ArtifactQualityStatus } from "@/features/artifacts/components/ArtifactQualityStatus";
import type { NodeRunDto } from "@/features/workflow/api/workflowApi";

const qualityNodeRunId = "01960000-0000-7000-8000-000000000901";
const accepted = {
  events_url: "/api/v2/projects/project-1/events/stream",
  node_run_id: qualityNodeRunId,
  status: "ready",
} satisfies AcceptedNodeRunDto;

function node(id: string, status: NodeRunDto["status"]): NodeRunDto {
  return { id, node_key: "lesson_plan.validate", status };
}

describe("ArtifactQualityStatus", () => {
  it("follows the exact quality NodeRun from queued work through a passed terminal state", () => {
    const view = render(
      <ArtifactQualityStatus
        accepted={accepted}
        nodeRuns={[node(qualityNodeRunId, "running")]}
        subject="教案"
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("教案质量校验正在处理");

    view.rerender(
      <ArtifactQualityStatus
        accepted={accepted}
        nodeRuns={[node(qualityNodeRunId, "approved")]}
        subject="教案"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("教案质量校验已通过，可以批准当前版本");
  });

  it("reports the exact failed NodeRun instead of an unrelated approved run", () => {
    render(
      <ArtifactQualityStatus
        accepted={accepted}
        nodeRuns={[
          node("01960000-0000-7000-8000-000000000999", "approved"),
          node(qualityNodeRunId, "failed"),
        ]}
        subject="课时划分"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "课时划分质量校验未通过，请修订当前版本后重新校验",
    );
  });
});
