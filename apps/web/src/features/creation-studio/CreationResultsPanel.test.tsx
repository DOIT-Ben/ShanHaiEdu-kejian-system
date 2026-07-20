import * as Tooltip from "@radix-ui/react-tooltip";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { CreationResultsPanel } from "@/features/creation-studio/CreationResultsPanel";

function renderResults(overrides: Partial<ComponentProps<typeof CreationResultsPanel>> = {}) {
  return render(
    <Tooltip.Provider>
      <CreationResultsPanel
        candidate={0}
        candidateCount={3}
        generation={1}
        hasUnappliedChanges={false}
        onAdvance={vi.fn()}
        onCandidateChange={vi.fn()}
        onDownload={vi.fn()}
        ratio="1:1"
        stage="ready"
        type="image"
        {...overrides}
      />
    </Tooltip.Provider>,
  );
}

describe("CreationResultsPanel", () => {
  it("在桌面与移动端使用可检查的主预览尺寸，并支持前后切换", () => {
    const onCandidateChange = vi.fn();
    renderResults({ onCandidateChange });

    expect(screen.getByTestId("creation-main-visual")).toHaveClass(
      "w-[min(100%,360px)]",
      "md:w-[clamp(480px,56vw,720px)]",
    );
    expect(screen.getByRole("button", { name: "上一张作品" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "下一张作品" }));
    expect(onCandidateChange).toHaveBeenCalledWith(1);
  });

  it("打开对比视图时并排展示最多三项，并可切换当前作品", () => {
    const onCandidateChange = vi.fn();
    renderResults({ candidate: 1, onCandidateChange });

    fireEvent.click(screen.getByRole("button", { name: "对比作品" }));
    const dialog = screen.getByRole("dialog", { name: "对比作品" });
    expect(within(dialog).getByTestId("creation-comparison-grid")).toBeInTheDocument();
    expect(within(dialog).getAllByRole("button", { name: /查看作品/ })).toHaveLength(3);

    fireEvent.click(within(dialog).getByRole("button", { name: "查看作品 3" }));
    expect(onCandidateChange).toHaveBeenCalledWith(2);
    expect(screen.queryByRole("dialog", { name: "对比作品" })).not.toBeInTheDocument();
  });

  it("提供放大查看，并在浏览器不支持原生全屏时回退到放大视图", () => {
    renderResults();

    fireEvent.click(screen.getByRole("button", { name: "放大查看" }));
    expect(screen.getByRole("dialog", { name: "放大查看" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "关闭放大查看" }));

    fireEvent.click(screen.getByRole("button", { name: "全屏查看" }));
    expect(screen.getByRole("dialog", { name: "放大查看" })).toBeInTheDocument();
  });
});
