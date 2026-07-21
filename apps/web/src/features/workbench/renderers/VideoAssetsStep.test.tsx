import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { VideoAssetsStep } from "@/features/workbench/renderers/VideoAssetsStep";
import { createMockProject, resetMockRuntime } from "@/shared/api/mocks/runtime";

describe("VideoAssetsStep visual truth", () => {
  beforeEach(() => resetMockRuntime());

  it("新课题以紧凑资产状态列表呈现，不再用大面积占位图", () => {
    const project = createMockProject({
      knowledge_point: "圆的面积",
      title: "圆的面积课堂",
    });

    render(
      <MemoryRouter initialEntries={[`/projects/${project.id}/lessons/lesson-a/work/video-assets`]}>
        <Routes>
          <Route
            element={<VideoAssetsStep />}
            path="/projects/:projectId/lessons/:lessonId/work/video-assets"
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryAllByRole("img")).toHaveLength(0);
    expect(screen.getByRole("region", { name: "图片资产制作状态" })).toBeInTheDocument();
    expect(screen.getAllByText("等待制作").length).toBeGreaterThan(0);
    expect(screen.queryByText("示例构图 · 等待当前课题素材")).not.toBeInTheDocument();
  });
});
