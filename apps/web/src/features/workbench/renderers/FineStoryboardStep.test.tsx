import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { FineStoryboardStep } from "@/features/workbench/renderers/FineStoryboardStep";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";

describe("FineStoryboardStep media truth", () => {
  beforeEach(() => resetMockRuntime());

  it("静态素材只允许选择关键帧参考，不称作视频片段", () => {
    render(
      <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/fine-storyboard"]}>
        <Routes>
          <Route
            element={<FineStoryboardStep />}
            path="/projects/:projectId/lessons/:lessonId/work/fine-storyboard"
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "选择这个关键帧参考" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关键帧参考 1" })).toBeInTheDocument();
    expect(screen.getAllByText(/视频尚未生成/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/备选片段|合成完整视频|采用这个结果/)).not.toBeInTheDocument();
  });
});
