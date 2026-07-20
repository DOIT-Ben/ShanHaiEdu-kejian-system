import { createRef, useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Select } from "@/shared/ui/Select";

const options = [
  { label: "六年级", value: "grade-6" },
  { label: "五年级", value: "grade-5" },
  { disabled: true, label: "暂不可用", value: "disabled" },
];

function ControlledSelect() {
  const [value, setValue] = useState("grade-6");
  return <Select ariaLabel="选择年级" onValueChange={setValue} options={options} value={value} />;
}

describe("Select", () => {
  it("通过统一弹层更新受控值，并保留禁用选项状态", async () => {
    const user = userEvent.setup();
    render(<ControlledSelect />);

    const trigger = screen.getByRole("combobox", { name: "选择年级" });
    expect(trigger).toHaveTextContent("六年级");

    await user.click(trigger);
    expect(screen.getByRole("option", { name: "暂不可用" })).toHaveAttribute("data-disabled");
    await user.click(screen.getByRole("option", { name: "五年级" }));

    expect(trigger).toHaveTextContent("五年级");
  });

  it("支持键盘方向键选择并用 Escape 关闭", async () => {
    const user = userEvent.setup();
    render(<ControlledSelect />);

    const trigger = screen.getByRole("combobox", { name: "选择年级" });
    trigger.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("listbox")).toBeVisible();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(trigger).toHaveTextContent("五年级");

    await user.click(trigger);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("同步外部值，并把 ref 与失焦事件交给表单", () => {
    const onBlur = vi.fn();
    const ref = createRef<HTMLButtonElement>();
    const { rerender } = render(
      <Select
        ariaLabel="选择年级"
        onBlur={onBlur}
        onValueChange={() => undefined}
        options={options}
        ref={ref}
        value="grade-6"
      />,
    );

    expect(ref.current).toBe(screen.getByRole("combobox", { name: "选择年级" }));
    ref.current?.focus();
    ref.current?.blur();
    expect(onBlur).toHaveBeenCalledTimes(1);

    rerender(
      <Select
        ariaLabel="选择年级"
        onBlur={onBlur}
        onValueChange={() => undefined}
        options={options}
        ref={ref}
        value="grade-5"
      />,
    );
    expect(screen.getByRole("combobox", { name: "选择年级" })).toHaveTextContent("五年级");
  });

  it("禁用时不打开弹层", async () => {
    const user = userEvent.setup();
    render(
      <Select
        ariaLabel="选择年级"
        disabled
        onValueChange={() => undefined}
        options={options}
        value="grade-6"
      />,
    );

    const trigger = screen.getByRole("combobox", { name: "选择年级" });
    expect(trigger).toBeDisabled();
    await user.click(trigger);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("用语义状态和可访问文本表达成功与错误", () => {
    const { rerender } = render(
      <Select
        ariaLabel="选择年级"
        onValueChange={() => undefined}
        options={options}
        status="success"
        statusMessage="年级已保存"
        value="grade-6"
      />,
    );

    const trigger = screen.getByRole("combobox", { name: "选择年级" });
    expect(trigger).toHaveAttribute("data-validation-state", "success");
    expect(screen.getByRole("status")).toHaveTextContent("年级已保存");

    rerender(
      <Select
        ariaLabel="选择年级"
        onValueChange={() => undefined}
        options={options}
        status="error"
        statusMessage="请选择年级"
        value="grade-6"
      />,
    );
    expect(screen.getByRole("combobox", { name: "选择年级" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("请选择年级");
  });

  it("拒绝 Radix 不支持的空字符串选项值", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() =>
      render(
        <Select
          ariaLabel="选择年级"
          onValueChange={() => undefined}
          options={[{ label: "请选择", value: "" }]}
        />,
      ),
    ).toThrow("Select 选项值不能为空");
    consoleError.mockRestore();
  });
});
