import { TooltipProvider } from "@radix-ui/react-tooltip";
import { Settings } from "lucide-react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IconButton } from "@/shared/ui/IconButton";

describe("IconButton", () => {
  it("提供至少 44px 的触控目标", () => {
    render(
      <TooltipProvider>
        <IconButton label="创作设置">
          <Settings aria-hidden="true" />
        </IconButton>
      </TooltipProvider>,
    );

    expect(screen.getByRole("button", { name: "创作设置" }).className).toContain("size-11");
  });
});
