import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "@/shared/ui/Button";

describe("Button", () => {
  it("默认调用方式保持可点击并消费纯色行动令牌", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>确认并继续</Button>);

    const button = screen.getByRole("button", { name: "确认并继续" });
    expect(button).toHaveAttribute("data-state", "idle");
    expect(button).not.toHaveAttribute("aria-busy");
    expect(button.className).toContain("var(--sh-action-primary)");
    expect(button.className).not.toContain("gradient");
    await user.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("加载态保留尺寸、阻止重复提交并公布状态", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button loading loadingText="正在保存" onClick={onClick}>
        保存修改
      </Button>,
    );

    const button = screen.getByRole("button", { name: "正在保存" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("data-state", "loading");
    expect(button.querySelector('[data-slot="button-content"]')).toHaveClass("invisible");
    expect(button.querySelector('[data-slot="button-state"]')).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("正在保存");
    await user.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("成功和错误态同时提供图标与可访问文本", () => {
    const { rerender } = render(
      <Button success successText="保存成功">
        保存修改
      </Button>,
    );
    expect(screen.getByRole("button", { name: "保存成功" })).toHaveAttribute(
      "data-state",
      "success",
    );
    expect(screen.getByRole("status")).toHaveTextContent("保存成功");

    rerender(
      <Button error errorText="保存失败">
        保存修改
      </Button>,
    );
    expect(screen.getByRole("button", { name: "保存失败" })).toHaveAttribute("data-state", "error");
    expect(screen.getByRole("alert")).toHaveTextContent("保存失败");
  });

  it("状态变化时保留显式按钮用途", () => {
    render(
      <Button aria-label="发送创作指令" loading loadingText="正在生成">
        发送
      </Button>,
    );

    expect(screen.getByRole("button", { name: "发送创作指令：正在生成" })).toBeDisabled();
  });

  it("asChild 加载态不会激活链接", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button asChild loading loadingText="正在打开" onClick={onClick}>
        <a href="/target">打开项目</a>
      </Button>,
    );

    const link = screen.getByRole("link", { name: "正在打开" });
    expect(link).toHaveAttribute("aria-disabled", "true");
    expect(link).toHaveAttribute("tabindex", "-1");
    await user.click(link);
    expect(onClick).not.toHaveBeenCalled();
  });
});
