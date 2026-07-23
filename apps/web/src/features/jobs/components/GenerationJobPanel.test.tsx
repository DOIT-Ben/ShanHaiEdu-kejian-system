import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { GenerationJobDto } from "@/features/jobs/api/jobsApi";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";

function job(status: GenerationJobDto["status"]): GenerationJobDto {
  return {
    created_at: "2030-01-01T00:00:00Z",
    error_code: status === "failed" ? "PROVIDER_TIMEOUT" : null,
    id: "job-1",
    job_type: "parse_material",
    progress_message: status === "failed" ? "教材解析超时" : "正在解析教材",
    progress_percent: status === "failed" ? 52 : 32,
    status,
    updated_at: "2030-01-01T00:01:00Z",
  };
}

describe("GenerationJobPanel", () => {
  it("展示失败事实并只为可取消状态发送取消意图", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const { rerender } = render(<GenerationJobPanel job={job("failed")} onCancel={onCancel} />);

    expect(screen.getByRole("alert")).toHaveTextContent("任务没有完成");
    expect(screen.getByRole("alert")).not.toHaveTextContent("PROVIDER_TIMEOUT");
    expect(screen.queryByRole("button", { name: "取消任务" })).not.toBeInTheDocument();

    rerender(<GenerationJobPanel job={job("running")} onCancel={onCancel} />);
    await user.click(screen.getByRole("button", { name: "取消任务" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
