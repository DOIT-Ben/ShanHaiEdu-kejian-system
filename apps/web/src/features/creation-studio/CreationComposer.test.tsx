import { TooltipProvider } from "@radix-ui/react-tooltip";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { CreationComposer } from "@/features/creation-studio/CreationComposer";
import type { CreationSettings } from "@/features/creation-studio/model";
import { studioRegistry } from "@/features/creation-studio/registry";

const settings: CreationSettings = {
  candidateCount: "3",
  duration: "10",
  model: "balanced",
  ratio: "1:1",
  referenceName: "",
  style: "paper",
};

function ComposerHarness({ onGenerate }: { onGenerate: () => void }) {
  const [description, setDescription] = useState("");

  return (
    <TooltipProvider>
      <CreationComposer
        advancedOpen={false}
        advancedPanel={<div />}
        config={studioRegistry.image}
        description={description}
        descriptionLabel="画面内容"
        onAdvancedOpenChange={() => undefined}
        onDescriptionChange={setDescription}
        onGenerate={onGenerate}
        onPromptReview={() => undefined}
        onSettingsChange={() => undefined}
        settings={settings}
        stage="draft"
        type="image"
      />
    </TooltipProvider>
  );
}

describe("CreationComposer", () => {
  it("默认只展示创作所需的核心操作，参数按需展开", async () => {
    const user = userEvent.setup();
    render(<ComposerHarness onGenerate={() => undefined} />);

    expect(screen.getByRole("button", { name: "添加参考图" })).toBeVisible();
    expect(screen.getByRole("button", { name: "创作设置" })).toBeVisible();
    expect(screen.queryByRole("combobox", { name: "创作模型" })).not.toBeInTheDocument();
    expect(screen.queryByText("留出板书区")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "创作设置" }));

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "创作模型" })).toBeVisible();
      expect(screen.getByRole("combobox", { name: "比例" })).toBeVisible();
      expect(screen.getByRole("button", { name: "画面细节" })).toBeVisible();
      expect(screen.getByRole("button", { name: "完整要求" })).toBeVisible();
    });
  });

  it("输入内容后使用箭头按钮或 Enter 发送", async () => {
    const onGenerate = vi.fn();
    const user = userEvent.setup();
    render(<ComposerHarness onGenerate={onGenerate} />);

    const send = screen.getByRole("button", { name: "开始创作图片" });
    const prompt = screen.getByRole("textbox", { name: "画面内容" });
    expect(send).toBeDisabled();

    await user.type(prompt, "画一张适合课堂观察的果汁标签图片");
    expect(send).toBeEnabled();
    await user.keyboard("{Enter}");
    expect(onGenerate).toHaveBeenCalledTimes(1);
  });

  it("Shift+Enter 保留为换行而不发送", () => {
    const onGenerate = vi.fn();
    render(<ComposerHarness onGenerate={onGenerate} />);

    const prompt = screen.getByRole("textbox", { name: "画面内容" });
    fireEvent.change(prompt, { target: { value: "第一行" } });
    fireEvent.keyDown(prompt, { key: "Enter", shiftKey: true });

    expect(onGenerate).not.toHaveBeenCalled();
  });
});
