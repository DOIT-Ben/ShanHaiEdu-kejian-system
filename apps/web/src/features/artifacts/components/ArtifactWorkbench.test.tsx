import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ArtifactDto } from "@/features/artifacts/api/artifactsApi";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";

const artifact = {
  artifact_key: "internal.lesson-plan",
  artifact_type: "lesson_plan",
  branch_key: "lesson_plan",
  current_draft: { draft_branch: "main", content: { internal_key: "初稿" } },
  current_submitted_version: {
    content_hash: "internal-content-hash",
    id: "version-2",
    version_no: 2,
  },
  current_approved_version: null,
  id: "artifact-1",
  status: "in_review",
} as unknown as ArtifactDto;

describe("ArtifactWorkbench", () => {
  it("只展示教师可理解的内容与版本动作，不泄漏内部结构", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const onSaveDraft = vi.fn();
    const onSubmit = vi.fn();
    render(
      <ArtifactWorkbench
        artifact={artifact}
        draftEditor={<textarea aria-label="教案内容" defaultValue="初稿" />}
        onApprove={onApprove}
        onSaveDraft={onSaveDraft}
        onSubmit={onSubmit}
        submittedVersionPreview={<article>待确认教案正文</article>}
        title="课时教案"
      />,
    );

    await user.click(screen.getByRole("button", { name: "保存草稿" }));
    expect(onSaveDraft).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: "提交当前草稿" }));
    expect(onSubmit).toHaveBeenCalledWith("main");
    await user.click(screen.getByRole("button", { name: "批准当前版本" }));
    expect(onApprove).toHaveBeenCalledWith("version-2");
    expect(screen.queryByText("internal.lesson-plan")).not.toBeInTheDocument();
    expect(screen.queryByText("internal-content-hash")).not.toBeInTheDocument();
  });

  it("任一写操作进行中时禁用全部版本动作", () => {
    render(
      <ArtifactWorkbench
        artifact={artifact}
        busyAction="submit"
        draftEditor={<textarea aria-label="教案内容" defaultValue="初稿" />}
        onApprove={vi.fn()}
        onSaveDraft={vi.fn()}
        onSubmit={vi.fn()}
        submittedVersionPreview={<article>待确认教案正文</article>}
        title="课时教案"
      />,
    );

    expect(screen.getByRole("button", { name: "保存草稿" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "提交当前草稿" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "批准当前版本" })).toBeDisabled();
  });

  it("缺少安全内容展示时禁用草稿、提交和批准动作", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const onSaveDraft = vi.fn();
    const onSubmit = vi.fn();
    render(
      <ArtifactWorkbench
        artifact={artifact}
        onApprove={onApprove}
        onSaveDraft={onSaveDraft}
        onSubmit={onSubmit}
        title="课时教案"
      />,
    );

    expect(screen.getByText(/草稿正文暂不可查看或编辑/)).toBeVisible();
    expect(screen.getByText(/待确认版本正文暂不可查看/)).toBeVisible();
    const saveButton = screen.getByRole("button", { name: "保存草稿" });
    const submitButton = screen.getByRole("button", { name: "提交当前草稿" });
    const approveButton = screen.getByRole("button", { name: "批准当前版本" });
    expect(saveButton).toBeDisabled();
    expect(submitButton).toBeDisabled();
    expect(approveButton).toBeDisabled();

    await user.click(saveButton);
    await user.click(submitButton);
    await user.click(approveButton);
    expect(onSaveDraft).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(onApprove).not.toHaveBeenCalled();
  });

  it("当前提交版本已经批准时不再提供重复批准动作", () => {
    render(
      <ArtifactWorkbench
        artifact={{
          ...artifact,
          current_approved_version: artifact.current_submitted_version,
          status: "approved",
        }}
        onApprove={vi.fn()}
        onSubmit={vi.fn()}
        title="课时教案"
      />,
    );

    expect(screen.queryByRole("button", { name: "批准当前版本" })).not.toBeInTheDocument();
    expect(screen.getByText("当前提交版本已经批准，无需重复确认。")).toBeVisible();
    expect(screen.getByText("已批准版本 2")).toBeVisible();
  });
});
