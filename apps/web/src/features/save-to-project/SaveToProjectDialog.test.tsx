import { TooltipProvider } from "@radix-ui/react-tooltip";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  SaveToProjectDialog,
  type SaveResultDescriptor,
} from "@/features/save-to-project/SaveToProjectDialog";

const projects = [{ id: "project-1", title: "认识百分数" }];
const slots = [
  { accepts: ["image" as const], key: "lesson.cover", label: "课时封面" },
  { accepts: ["video" as const], key: "lesson.intro-video", label: "课堂导入视频" },
];

function Harness({
  conflict,
  onSave = () => undefined,
  result = { id: "result-1", title: "课堂作品", type: "image" },
}: {
  conflict?: Parameters<typeof SaveToProjectDialog>[0]["conflict"];
  onSave?: Parameters<typeof SaveToProjectDialog>[0]["onSave"];
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
        conflict={conflict}
        onOpenChange={setOpen}
        onSave={onSave}
        open={open}
        projects={projects}
        result={result}
        returnFocusRef={triggerRef}
        slots={slots}
      />
    </>
  );
}

describe("SaveToProjectDialog", () => {
  it("关闭后把焦点还给打开按钮", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>,
    );
    const trigger = screen.getByRole("button", { name: "保存到项目" });
    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: "关闭" }));

    expect(screen.queryByRole("dialog", { name: "保存到项目" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("只展示 adapter 提供且与作品类型匹配的位置", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <Harness result={{ id: "video-1", title: "课堂导入", type: "video" }} />
      </TooltipProvider>,
    );
    await user.click(screen.getByRole("button", { name: "保存到项目" }));
    await user.click(screen.getByRole("combobox", { name: "保存位置" }));

    expect(screen.getByRole("option", { name: "课堂导入视频" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "课时封面" })).not.toBeInTheDocument();
  });

  it("首次提交只发出拒绝覆盖的保存意图", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    const result: SaveResultDescriptor = {
      id: "result-2",
      preview: { candidate: 1, generation: 2, ratio: "4:3" },
      title: "果汁标签观察图",
      type: "image",
    };
    render(
      <TooltipProvider>
        <Harness onSave={onSave} result={result} />
      </TooltipProvider>,
    );
    await user.click(screen.getByRole("button", { name: "保存到项目" }));
    await user.click(screen.getByRole("button", { name: "保存到这个位置" }));

    expect(onSave).toHaveBeenCalledWith({
      projectId: "project-1",
      replaceMode: "reject_if_occupied",
      result,
      slotKey: "lesson.cover",
    });
  });

  it("冲突由 adapter 驱动并显式发出追加意图", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(
      <TooltipProvider>
        <Harness conflict={{ canAppend: true }} onSave={onSave} />
      </TooltipProvider>,
    );
    await user.click(screen.getByRole("button", { name: "保存到项目" }));
    await user.click(screen.getByRole("radio", { name: "追加到这个保存位置" }));
    await user.click(screen.getByRole("button", { name: "确认保存" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ replaceMode: "append", slotKey: "lesson.cover" }),
    );
  });
});
