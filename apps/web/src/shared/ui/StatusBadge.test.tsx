import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WorkflowStatus } from "@/entities/workflow/model";
import { StatusBadge } from "@/shared/ui/StatusBadge";

describe("StatusBadge", () => {
  it("falls back to an upgrade-safe label for an unknown runtime value", () => {
    render(<StatusBadge status={"future_status" as WorkflowStatus} />);

    expect(screen.getByText("状态待升级")).toBeInTheDocument();
  });
});
