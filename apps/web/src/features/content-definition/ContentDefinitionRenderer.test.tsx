import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { describe, expect, it, vi } from "vitest";
import { ContentDefinitionRenderer } from "@/features/content-definition/ContentDefinitionRenderer";
import type { ContentDefinition } from "@/features/content-definition/model";

const definition: ContentDefinition = {
  definition_key: "test.dynamic",
  title: "动态内容",
  fields: [
    {
      field_key: "goal",
      label: "目标",
      type: "text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "steps",
      label: "步骤",
      type: "list",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "future",
      label: "未来字段",
      type: "future_widget",
      required: false,
      editable: false,
      deletable: false,
    },
  ],
};

describe("ContentDefinitionRenderer", () => {
  const renderDefinition = (onChange?: (data: Record<string, unknown>) => void) =>
    render(
      <TooltipProvider>
        <ContentDefinitionRenderer
          data={{ goal: "理解百分数", steps: ["观察"] }}
          definition={definition}
          onChange={onChange}
        />
      </TooltipProvider>,
    );

  it("不依赖固定十二字段即可渲染和编辑另一套结构", () => {
    const onChange = vi.fn();
    renderDefinition(onChange);
    expect(screen.getByRole("textbox", { name: "目标" })).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("理解百分数"), { target: { value: "解释百分数" } });
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ goal: "解释百分数" }));
    expect(screen.getByText(/此内容类型需要升级后才能编辑/)).toBeInTheDocument();
  });

  it("允许动态列表增加项目", () => {
    renderDefinition();
    expect(screen.getByRole("textbox", { name: "步骤第 1 项" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除步骤第 1 项" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "增加一项" }));
    expect(screen.getAllByRole("textbox")).toHaveLength(3);
    expect(screen.getByRole("textbox", { name: "步骤第 2 项" })).toBeInTheDocument();
  });
});
