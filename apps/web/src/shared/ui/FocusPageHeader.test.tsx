import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

describe("FocusPageHeader", () => {
  it("在同一页头中呈现标题、辅助操作和主操作", () => {
    render(
      <FocusPageHeader
        action={<button type="button">创建项目</button>}
        supporting={<input aria-label="搜索项目" type="search" />}
        title="我的项目"
      />,
    );

    const header = screen.getByRole("banner");
    expect(within(header).getByRole("heading", { name: "我的项目" })).toBeInTheDocument();
    expect(within(header).getByRole("searchbox", { name: "搜索项目" })).toBeInTheDocument();
    expect(within(header).getByRole("button", { name: "创建项目" })).toBeInTheDocument();
    expect(within(header).getByTestId("page-header-supporting")).toBeInTheDocument();
  });
});
