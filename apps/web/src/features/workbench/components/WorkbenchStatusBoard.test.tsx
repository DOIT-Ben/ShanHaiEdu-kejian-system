import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkbenchStatusBoard } from "@/features/workbench/components/WorkbenchStatusBoard";

describe("WorkbenchStatusBoard", () => {
  it("未知服务端状态使用中性文案且不泄漏枚举值", () => {
    render(
      <WorkbenchStatusBoard
        items={[{ id: "future", status: "provider_waiting_v2", title: "课堂作品" }]}
      />,
    );

    expect(screen.getByText("状态待升级")).toBeVisible();
    expect(screen.queryByText("provider_waiting_v2")).not.toBeInTheDocument();
  });
});
