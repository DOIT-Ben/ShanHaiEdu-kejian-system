import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CreationBatchPage } from "@/pages/creation/CreationBatchPage";
import { AdminAuditPage } from "@/pages/admin/AdminAuditPage";
import { AdminContentPage } from "@/pages/admin/AdminContentPage";
import { AdminModelsPage } from "@/pages/admin/AdminModelsPage";
import { AdminUsagePage } from "@/pages/admin/AdminUsagePage";
import { AdminUsersPage } from "@/pages/admin/AdminUsersPage";
import { AdminWorkflowsPage } from "@/pages/admin/AdminWorkflowsPage";
import { ProjectResultsPage } from "@/pages/projects/ProjectResultsPage";
import { getMockRuntimeState, listMockTasks, resetMockRuntime } from "@/shared/api/mocks/runtime";
import { listMockSavedResults } from "@/shared/api/mocks/savedResults";
import { demoProjectId } from "@/shared/data/mockData";

function first(elements: HTMLElement[]) {
  const element = elements[0];
  if (!element) throw new Error("预期至少找到一个元素");
  return element;
}

async function chooseSelect(label: string, option: string) {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: label }));
  await user.click(await screen.findByRole("option", { name: option }));
}

describe("管理端 Mock 操作", () => {
  beforeEach(() => resetMockRuntime());

  it("完成内容包导入后重新挂载仍可见", async () => {
    const { unmount } = render(<AdminContentPage />);
    fireEvent.click(screen.getByRole("button", { name: "导入内容包" }));

    const next = screen.getByRole("button", { name: "继续" });
    expect(next).toBeDisabled();
    const metadata = JSON.stringify({
      schema: "shanhaiedu.content-package.mock/v1",
      title: "分数教学结构",
      kind: "内容结构",
      version: "5 个章节",
      usage: "0 个项目",
    });
    fireEvent.change(screen.getByLabelText("选择内容包文件"), {
      target: {
        files: [new File([metadata], "lesson-package.json", { type: "application/json" })],
      },
    });
    expect(await screen.findByText("JSON 元数据检查通过。")).toBeInTheDocument();
    expect(next).toBeEnabled();

    fireEvent.click(next);
    fireEvent.click(screen.getByRole("button", { name: "继续" }));
    fireEvent.click(screen.getByRole("button", { name: "继续" }));
    fireEvent.click(screen.getByRole("button", { name: "发布新版本" }));
    expect(screen.getByText("新版本已发布并加入内容列表")).toBeInTheDocument();
    expect(screen.getAllByText("分数教学结构").length).toBeGreaterThan(0);

    unmount();
    render(<AdminContentPage />);
    expect(screen.getByText("分数教学结构")).toBeInTheDocument();
  });

  it("保存并发布的工作流在重新挂载后恢复", () => {
    const { unmount } = render(<AdminWorkflowsPage />);
    fireEvent.click(screen.getByRole("button", { name: "增加步骤" }));
    expect(screen.getAllByText("新步骤 9")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));
    expect(screen.getByText("草稿已保存")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "运行发布检查" }));
    fireEvent.click(screen.getByRole("button", { name: "发布新版本" }));
    expect(screen.getByText("工作流 v1 已发布")).toBeInTheDocument();

    unmount();
    render(<AdminWorkflowsPage />);
    expect(screen.getAllByText("新步骤 9")).toHaveLength(1);
    expect(screen.getByText("当前已发布版本 v1")).toBeInTheDocument();
  });

  it("模型配置保存后更新列表并可恢复", async () => {
    const { unmount } = render(<AdminModelsPage />);
    fireEvent.click(first(screen.getAllByRole("button", { name: "配置" })));
    await chooseSelect("主模型", "快速模型");
    fireEvent.change(screen.getByLabelText("超时时间"), { target: { value: "180" } });
    fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
    unmount();
    render(<AdminModelsPage />);
    const row = screen.getByText("文本生成").closest("tr");
    if (!row) throw new Error("缺少文本生成服务行");
    expect(within(row).getByText("快速模型")).toBeInTheDocument();
  });

  it("成员权限保存后更新列表并可恢复", async () => {
    const { unmount } = render(<AdminUsersPage />);
    fireEvent.click(screen.getByRole("button", { name: "编辑林若晴的权限" }));
    await chooseSelect("角色", "内容管理员");
    await chooseSelect("权限范围", "全部项目");
    fireEvent.click(screen.getByRole("button", { name: "保存权限" }));
    unmount();
    render(<AdminUsersPage />);
    const row = screen.getByText("林若晴").closest("tr");
    if (!row) throw new Error("缺少林若晴成员行");
    expect(within(row).getByText("内容管理员")).toBeInTheDocument();
    expect(within(row).getByText("全部项目")).toBeInTheDocument();
    expect(screen.queryByText("lin.teacher@example.edu")).not.toBeInTheDocument();
  });

  it("取消添加成员不会写入，确认后才保存完整成员信息", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <TooltipProvider>
        <AdminUsersPage />
      </TooltipProvider>,
    );
    await user.click(screen.getByRole("button", { name: "添加成员" }));
    expect(screen.getByRole("dialog", { name: "添加成员" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("姓名"), { target: { value: "赵老师" } });
    fireEvent.change(screen.getByLabelText("账号"), { target: { value: "zhao@example.edu" } });
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByText("赵老师")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "添加成员" }));
    fireEvent.change(screen.getByLabelText("姓名"), { target: { value: "赵老师" } });
    fireEvent.change(screen.getByLabelText("账号"), { target: { value: "zhao@example.edu" } });
    await chooseSelect("角色", "内容管理员");
    await chooseSelect("权限范围", "内容中心");
    await user.click(screen.getByRole("button", { name: "确认添加" }));
    expect(screen.getByText("赵老师已加入")).toBeInTheDocument();

    unmount();
    render(
      <TooltipProvider>
        <AdminUsersPage />
      </TooltipProvider>,
    );
    const row = screen.getByText("赵老师").closest("tr");
    if (!row) throw new Error("缺少新成员行");
    expect(within(row).getByText("zhao@example.edu")).toBeInTheDocument();
    expect(within(row).getByText("内容管理员")).toBeInTheDocument();
    expect(within(row).getByText("内容中心")).toBeInTheDocument();
  });

  it("费用页重试创建统一任务并在重新挂载后恢复", () => {
    const { unmount } = render(<AdminUsagePage />);
    fireEvent.click(first(screen.getAllByRole("button", { name: "查看并重试" })));
    const task = listMockTasks().find((item) => item.title === "PPT 图片 · 百格光窗");
    expect(task).toMatchObject({ status: "queued", retry_count: 1, progress: 0 });
    expect(screen.getByRole("button", { name: "重试已提交" })).toBeDisabled();
    unmount();
    render(<AdminUsagePage />);
    expect(screen.getByRole("button", { name: "重试已提交" })).toBeDisabled();
  });

  it("审计日期筛选可恢复且导出真实 CSV 下载", () => {
    const clicked: Array<{ download: string; href: string }> = [];
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push({ download: this.download, href: this.href });
    });
    const { unmount } = render(<AdminAuditPage />);
    expect(screen.getByText("下载项目交付")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "最近 30 天" }));
    expect(screen.queryByText("下载项目交付")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "导出记录" }));
    expect(clicked[0]?.download).toBe("审计记录.csv");
    expect(decodeURIComponent(clicked[0]?.href ?? "")).toContain("批准教案");
    unmount();
    render(<AdminAuditPage />);
    expect(screen.getByRole("button", { name: "最近 7 天" })).toBeInTheDocument();
    expect(screen.queryByText("下载项目交付")).not.toBeInTheDocument();
    click.mockRestore();
  });
});

describe("成果与批次 Mock 操作", () => {
  it("查看、替换、下载并检查成果历史", () => {
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    render(
      <TooltipProvider>
        <ProjectResultsPage />
      </TooltipProvider>,
    );
    fireEvent.click(first(screen.getAllByRole("button", { name: "查看当前成果" })));
    expect(screen.getByText("正在查看：教案")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "替换当前版本" }));
    expect(screen.getByText(/已将“课堂导入设计附录”替换为版本 2/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下载作品说明" }));
    expect(screen.getByText(/已下载“课堂导入设计附录（调整版 2）”的成果说明/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看历史版本" }));
    const history = screen.getByRole("region", { name: "历史版本" });
    expect(within(history).getByText("版本 2 · 当前采用")).toBeInTheDocument();
    expect(within(history).getByText("版本 1 · 已归档")).toBeInTheDocument();
    expect(within(history).getByText("课堂导入设计附录（调整版 2）")).toBeInTheDocument();
    expect(within(history).getByText("课堂导入设计附录")).toBeInTheDocument();
    anchorClick.mockRestore();
  });

  it("切换备选作品、保存当前候选并查看创作要求", () => {
    render(
      <TooltipProvider>
        <MemoryRouter>
          <CreationBatchPage />
        </MemoryRouter>
      </TooltipProvider>,
    );
    const candidate = screen.getByRole("button", { name: "备选作品 2" });
    fireEvent.click(candidate);
    expect(candidate).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "就用这张" }));
    fireEvent.click(screen.getByRole("button", { name: "保存到项目" }));
    const saveDialog = screen.getByRole("dialog", { name: "保存到项目" });
    fireEvent.click(within(saveDialog).getByRole("button", { name: "保存到这个位置" }));
    expect(listMockSavedResults(getMockRuntimeState(), demoProjectId)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          preview: { candidate: 1, generation: 0, ratio: "1:1" },
        }),
      ]),
    );

    fireEvent.click(screen.getByRole("button", { name: /三张.*标签并排/ }));
    fireEvent.click(screen.getByRole("button", { name: "重新制作这张" }));
    expect(screen.getByText("这张已经重新做好，请从三张作品里挑一张。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "想改一改" }));
    expect(screen.getByRole("heading", { name: "想怎么改" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看完整创作要求" }));
    expect(screen.getByRole("heading", { name: "完整创作要求" })).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "完整创作要求" })).getByText(/不出现水印/),
    ).toBeInTheDocument();
  });
});
