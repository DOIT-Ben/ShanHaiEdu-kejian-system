import { TooltipProvider } from "@radix-ui/react-tooltip";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { ProjectResultsPage } from "@/pages/projects/ProjectResultsPage";
import { resetMockRuntime, saveMockDraft } from "@/shared/api/mocks/runtime";
import { saveMockResult } from "@/shared/api/mocks/savedResults";
import { demoProjectId } from "@/shared/data/mockData";

describe("ProjectResultsPage previews", () => {
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

  it("当前采用版本与素材列表展示各自保存的候选和画幅", () => {
    const current = saveMockResult({
      lessonLabel: "独立创作",
      preview: { candidate: 1, generation: 1, ratio: "4:3" },
      projectId: demoProjectId,
      replaceMode: "replace",
      resultId: "creation-image-generation-1-candidate-2",
      slotKey: "ppt.page-2.hero",
      slotLabel: "PPT 第 2 页主视觉",
      title: "当前候选二",
      type: "image",
    });
    saveMockResult({
      lessonLabel: "独立创作",
      preview: { candidate: 2, generation: 1, ratio: "16:9" },
      projectId: demoProjectId,
      replaceMode: "append",
      resultId: "creation-image-generation-1-candidate-3",
      slotKey: "project.shared-images:third",
      slotLabel: "项目通用教学图片",
      title: "列表候选三",
      type: "image",
    });
    saveMockDraft(`project:${demoProjectId}:results-selection`, current.id, {
      projectId: demoProjectId,
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/app/projects/${demoProjectId}/results`]}>
          <Routes>
            <Route element={<ProjectResultsPage />} path="/app/projects/:projectId/results" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    const summary = screen.getByTestId("current-result-summary");
    expect(
      within(summary).getByRole("img", {
        name: "老师和两名学生用几何图形搭建课堂作品",
      }),
    ).toBeVisible();
    expect(summary.querySelector('[data-preview-ratio="4:3"]')).not.toBeNull();

    const listCard = screen.getByRole("heading", { name: "列表候选三" }).closest("button");
    expect(listCard).not.toBeNull();
    if (!listCard) return;
    expect(
      within(listCard).getByRole("img", {
        name: "三瓶彩色饮品和几何卡片组成的课堂观察场景",
      }),
    ).toBeVisible();
    expect(listCard.querySelector('[data-preview-ratio="16:9"]')).not.toBeNull();
  });

  it("未知的内置结果编号不被解释成创作候选", () => {
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/app/projects/${demoProjectId}/results`]}>
          <Routes>
            <Route element={<ProjectResultsPage />} path="/app/projects/:projectId/results" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    const summary = screen.getByTestId("current-result-summary");
    expect(summary.querySelector("[data-preview-candidate]")).toBeNull();
    expect(
      within(summary).getByRole("img", {
        name: "三瓶彩色饮品和几何卡片组成的课堂观察场景",
      }),
    ).toBeVisible();
  });
});
