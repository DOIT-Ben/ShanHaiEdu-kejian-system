import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RuntimeLoginPage } from "@/pages/runtime/RuntimeLoginPage";

describe("RuntimeLoginPage", () => {
  it("只呈现真实登录边界，不伪造浏览器账号表单", () => {
    render(
      <MemoryRouter>
        <RuntimeLoginPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "使用学校账户进入" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回课堂工作区" })).toHaveAttribute(
      "href",
      "/app/projects",
    );
    expect(screen.queryByLabelText("账号")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("密码")).not.toBeInTheDocument();
  });
});
