import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmptyState, FormField, Input } from "@/shared/ui";
import { NodeStatusBadge, TaskStatusBadge } from "@/shared/ui";
import { SaveStatusIndicator } from "@/shared/ui";

describe("FormField", () => {
  it("为控件生成关联的 label 与错误描述", async () => {
    render(
      <FormField label="项目名称" required error="名称不能为空">
        {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} />}
      </FormField>,
    );
    const input = screen.getByLabelText(/项目名称/);
    expect(input).toBeInTheDocument();
    expect(screen.getByText("名称不能为空")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(input, "分数的初步认识");
    expect(input).toHaveValue("分数的初步认识");
  });
});

describe("状态徽标", () => {
  it("节点状态渲染中文标签", () => {
    render(<NodeStatusBadge status="needs_review" />);
    expect(screen.getByText("待审核")).toBeInTheDocument();
  });
  it("任务状态渲染中文标签", () => {
    render(<TaskStatusBadge status="running" />);
    expect(screen.getByText("生成中")).toBeInTheDocument();
  });
});

describe("SaveStatusIndicator", () => {
  it("保存出错时显示错误提示", () => {
    render(<SaveStatusIndicator state="error" errorHint="草稿保存失败" />);
    expect(screen.getByText(/草稿保存失败/)).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("渲染标题与动作", async () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        title="还没有项目"
        description="创建第一个课件项目"
        action={
          <button type="button" onClick={onAction}>
            新建项目
          </button>
        }
      />,
    );
    expect(screen.getByText("还没有项目")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "新建项目" }));
    expect(onAction).toHaveBeenCalledOnce();
  });
});
