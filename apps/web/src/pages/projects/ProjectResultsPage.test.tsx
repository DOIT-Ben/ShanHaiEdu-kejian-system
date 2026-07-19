import { TooltipProvider } from "@radix-ui/react-tooltip";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { ProjectResultsPage } from "@/pages/projects/ProjectResultsPage";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";
import { demoProjectId } from "@/shared/data/mockData";

describe("ProjectResultsPage video truth", () => {
  beforeEach(() => resetMockRuntime());

  it("没有真实媒体地址时只展示关键帧参考", () => {
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/app/projects/${demoProjectId}/results`]}>
          <Routes>
            <Route element={<ProjectResultsPage />} path="/app/projects/:projectId/results" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    const videoCard = screen.getByRole("heading", { name: "课堂导入视频" }).closest("article");
    expect(videoCard).not.toBeNull();
    if (!videoCard) return;
    expect(within(videoCard).getByText("关键帧参考已保存，视频尚未生成")).toBeVisible();
    fireEvent.click(within(videoCard).getByRole("button", { name: "查看当前成果" }));

    expect(screen.getByText("当前关键帧参考")).toBeVisible();
    expect(screen.getByRole("img", { name: /关键帧示意，视频尚未生成/ })).toBeVisible();
    expect(screen.getByRole("button", { name: "下载关键帧说明" })).toBeEnabled();
  });
});
