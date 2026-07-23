import { TooltipProvider } from "@radix-ui/react-tooltip";
import { Settings } from "lucide-react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { IconButton } from "@/shared/ui/IconButton";

function renderIconButton(props: Partial<React.ComponentProps<typeof IconButton>> = {}) {
  return render(
    <TooltipProvider>
      <IconButton label="创作设置" {...props}>
        <Settings aria-hidden="true" />
      </IconButton>
    </TooltipProvider>,
  );
}

describe("IconButton", () => {
  it("提供至少 44px 的触控目标", () => {
    renderIconButton();
    expect(screen.getByRole("button", { name: "创作设置" }).className).toContain("size-11");
  });

  it("主行动图标按钮复用全局纯色材质令牌", () => {
    renderIconButton({ label: "发送", variant: "primary" });
    const button = screen.getByRole("button", { name: "发送" });
    expect(button.className).toContain("var(--sh-action-primary)");
    expect(button.className).toContain("var(--sh-shadow-action)");
    expect(button.className).toContain("var(--sh-action-foreground)");
    expect(button.className).not.toContain("gradient");
  });

  it("加载态阻止重复提交并保留方形尺寸", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderIconButton({ loading: true, loadingText: "正在发送", onClick });

    const button = screen.getByRole("button", { name: "创作设置：正在发送" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("data-state", "loading");
    expect(button.className).toContain("size-11");
    expect(screen.getByRole("status")).toHaveTextContent("正在发送");
    await user.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("成功和错误态提供图标与可访问文本", () => {
    const { rerender } = render(
      <TooltipProvider>
        <IconButton label="发送" success successText="发送成功">
          <Settings aria-hidden="true" />
        </IconButton>
      </TooltipProvider>,
    );
    expect(screen.getByRole("button", { name: "发送：发送成功" })).toHaveAttribute(
      "data-state",
      "success",
    );
    expect(screen.getByRole("status")).toHaveTextContent("发送成功");

    rerender(
      <TooltipProvider>
        <IconButton error errorText="发送失败" label="发送">
          <Settings aria-hidden="true" />
        </IconButton>
      </TooltipProvider>,
    );
    expect(screen.getByRole("button", { name: "发送：发送失败" })).toHaveAttribute(
      "data-state",
      "error",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("发送失败");
  });
});
