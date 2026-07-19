import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { AdminContentPage } from "@/pages/admin/AdminContentPage";
import { AdminModelsPage } from "@/pages/admin/AdminModelsPage";
import { AdminUsagePage } from "@/pages/admin/AdminUsagePage";
import { AdminWorkflowsPage } from "@/pages/admin/AdminWorkflowsPage";
import {
  getMockDraft,
  listMockTasks,
  resetMockRuntime,
  updateMockTask,
} from "@/shared/api/mocks/runtime";

type StoredWorkflow = {
  draft: { steps: Array<{ name: string; capability: string }> };
  publishedVersions: Array<{
    version: number;
    steps: Array<{ name: string; capability: string }>;
  }>;
};

async function chooseSelect(label: string, option: string) {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: label }));
  await user.click(await screen.findByRole("option", { name: option }));
}

async function publishContentVersion(version: string) {
  fireEvent.click(screen.getByRole("button", { name: "导入内容包" }));
  const metadata = JSON.stringify({
    schema: "shanhaiedu.content-package.mock/v1",
    title: "同名教学结构",
    kind: "内容结构",
    version,
  });
  fireEvent.change(screen.getByLabelText("选择内容包文件"), {
    target: {
      files: [new File([metadata], `content-${version}.json`, { type: "application/json" })],
    },
  });
  await screen.findByText("JSON 元数据检查通过。");
  fireEvent.click(screen.getByRole("button", { name: "继续" }));
  fireEvent.click(screen.getByRole("button", { name: "继续" }));
  fireEvent.click(screen.getByRole("button", { name: "继续" }));
  fireEvent.click(screen.getByRole("button", { name: "发布新版本" }));
}

describe("管理端持久化规则", () => {
  beforeEach(() => resetMockRuntime());

  it("同标题不同版本的内容包作为不可变版本并存", async () => {
    render(<AdminContentPage />);
    await publishContentVersion("v1");
    await publishContentVersion("v2");

    const rows = screen.getAllByText("同名教学结构").map((title) => title.closest("tr"));
    expect(rows).toHaveLength(2);
    expect(rows.every(Boolean)).toBe(true);
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
  });

  it("JSON 内容包拒绝错误 MIME 和超大文件", async () => {
    render(<AdminContentPage />);
    fireEvent.click(screen.getByRole("button", { name: "导入内容包" }));
    fireEvent.change(screen.getByLabelText("选择内容包文件"), {
      target: { files: [new File(["{}"], "content.json", { type: "image/png" })] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("JSON 文件类型无效");

    fireEvent.change(screen.getByLabelText("选择内容包文件"), {
      target: {
        files: [new File([new Uint8Array(1_048_577)], "large.json", { type: "application/json" })],
      },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("JSON 文件不能超过 1 MB");
  });

  it("工作流配置按步骤隔离且发布快照不可被后续草稿修改", async () => {
    render(<AdminWorkflowsPage />);
    await chooseSelect("能力包", "PPT 页面设计");
    fireEvent.click(screen.getByRole("button", { name: "运行发布检查" }));
    fireEvent.click(screen.getByRole("button", { name: "发布新版本" }));

    await chooseSelect("能力包", "课程锚点生成");
    fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));
    fireEvent.click(screen.getByRole("button", { name: /教材解析/ }));
    expect(screen.getByRole("combobox", { name: "能力包" })).toHaveTextContent("小学数学教案生成");

    const stored = getMockDraft<StoredWorkflow>("admin.workflow.editor")?.value;
    expect(stored?.draft.steps[2]?.capability).toBe("课程锚点生成");
    expect(stored?.publishedVersions[0]?.steps[2]?.capability).toBe("PPT 页面设计");
  });

  it("模型配置无效时不能保存为正常", async () => {
    render(<AdminModelsPage />);
    fireEvent.click(screen.getByRole("button", { name: "添加模型服务" }));
    const save = screen.getByRole("button", { name: "保存配置" });
    expect(save).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("请选择主模型");

    await chooseSelect("主模型", "快速模型");
    fireEvent.change(screen.getByLabelText("超时时间"), { target: { value: "0" } });
    expect(save).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("超时时间须为 1 到 600 秒的整数");

    fireEvent.change(screen.getByLabelText("超时时间"), { target: { value: "180" } });
    fireEvent.click(save);
    const row = screen.getByText("新能力服务 5").closest("tr");
    if (!row) throw new Error("缺少新增服务行");
    expect(within(row).getByText("正常")).toBeInTheDocument();
  });

  it("费用页直接展示运行时任务状态", () => {
    render(<AdminUsagePage />);
    const retry = screen.getAllByRole("button", { name: "查看并重试" })[0];
    if (!retry) throw new Error("缺少重试按钮");
    fireEvent.click(retry);
    const task = listMockTasks().find((item) => item.title === "PPT 图片 · 百格光窗");
    if (!task) throw new Error("重试任务未创建");

    act(() => {
      updateMockTask(task.id, { status: "running", stage: "重新生成" });
    });
    expect(screen.getByText("制作中")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试进行中" })).toBeDisabled();

    act(() => {
      updateMockTask(task.id, { status: "approved", progress: 100, stage: "已完成" });
    });
    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试已完成" })).toBeDisabled();
  });
});
