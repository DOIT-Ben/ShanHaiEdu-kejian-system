import { TooltipProvider } from "@radix-ui/react-tooltip";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectAssetDrawer } from "@/features/creation-studio/ProjectAssetDrawer";
import type { ProjectCreationPackageItem } from "@/features/creation-studio/projectCreationPackage";

const items: ProjectCreationPackageItem[] = [
  {
    id: "character",
    prompt: "人物提示词",
    ratio: "16:9",
    slotKey: "video.asset.lesson.character",
    slotLabel: "人物素材",
    style: "paper",
    title: "参与观察的小学生",
    type: "人物",
  },
  {
    id: "scene",
    prompt: "场景提示词",
    ratio: "16:9",
    slotKey: "video.asset.lesson.scene",
    slotLabel: "场景素材",
    style: "paper",
    title: "果汁标签观察桌",
    type: "场景",
  },
];

describe("ProjectAssetDrawer", () => {
  it("从右侧按钮打开项目资产并切换待制作素材", () => {
    const onSelect = vi.fn();
    render(
      <TooltipProvider>
        <ProjectAssetDrawer
          activeId="character"
          items={items}
          lessonTitle="第 1 课时 · 百分数的意义"
          onCancel={() => undefined}
          onImport={onSelect}
          onRetry={() => undefined}
          projectTitle="认识百分数"
          savedSlotKeys={new Set<string>()}
          taskStatuses={{ character: "ready", scene: "idle" }}
        />
      </TooltipProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开项目资产" }));
    expect(screen.getByRole("dialog", { name: "项目资产" })).toBeInTheDocument();
    expect(screen.getByText(/认识百分数/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "导入场景：果汁标签观察桌" }));
    expect(onSelect).toHaveBeenCalledWith("scene");
  });
});
