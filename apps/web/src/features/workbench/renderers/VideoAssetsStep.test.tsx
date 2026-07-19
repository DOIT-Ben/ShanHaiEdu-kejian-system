import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { VideoAssetsStep } from "@/features/workbench/renderers/VideoAssetsStep";
import { createMockProject, resetMockRuntime } from "@/shared/api/mocks/runtime";

describe("VideoAssetsStep visual truth", () => {
  beforeEach(() => resetMockRuntime());

  it("新课题使用真实课堂图片替代图标占位，同时明确它只是示例构图", () => {
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

    expect(screen.getAllByRole("img")).toHaveLength(4);
    expect(screen.getAllByText("示例构图 · 等待当前课题素材")).toHaveLength(4);
    expect(
      screen.getAllByRole("img", {
        name: /果汁标签课堂示例.*不是当前课题生成结果/,
      }),
    ).toHaveLength(4);
  });
});
