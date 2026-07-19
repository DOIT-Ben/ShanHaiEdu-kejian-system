import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { useRef, useState } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import {
  SaveToProjectDialog,
  type SaveResultDescriptor,
} from "@/features/save-to-project/SaveToProjectDialog";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";

function Harness({
  result = { id: "result-1", title: "测试作品", type: "image" },
}: {
  result?: SaveResultDescriptor;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button onClick={() => setOpen(true)} ref={triggerRef} type="button">
        保存到项目
      </button>
      <SaveToProjectDialog
        onOpenChange={setOpen}
        onSaved={() => undefined}
        open={open}
        result={result}
        returnFocusRef={triggerRef}
      />
    </>
  );
}

describe("SaveToProjectDialog focus", () => {
  beforeEach(() => resetMockRuntime());

  it("关闭后把焦点还给打开按钮", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>,
    );
    const trigger = screen.getByRole("button", { name: "保存到项目" });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "保存到项目" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "关闭" }));

    expect(screen.queryByRole("dialog", { name: "保存到项目" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("只展示与作品类型匹配的保存位置", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <Harness result={{ id: "video-1", title: "课堂导入", type: "video" }} />
      </TooltipProvider>,
    );
    await user.click(screen.getByRole("button", { name: "保存到项目" }));
    await user.click(screen.getByRole("combobox", { name: "保存位置" }));

    expect(screen.getByRole("option", { name: "课堂导入视频" })).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "PPT 第 3 页主视觉（课堂讲解时显示）" }),
    ).not.toBeInTheDocument();
  });
});
