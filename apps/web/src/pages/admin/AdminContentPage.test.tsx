import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminContentPage } from "@/pages/admin/AdminContentPage";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";

describe("AdminContentPage tabs", () => {
  beforeEach(() => resetMockRuntime());

  it("为每个标签提供对应的可访问内容面板", () => {
    render(<AdminContentPage />);

    for (const tabName of ["全部内容", "内容结构", "规则与指令"]) {
      fireEvent.mouseDown(screen.getByRole("tab", { name: tabName }), { button: 0 });
      expect(screen.getByRole("tabpanel", { name: tabName })).toBeInTheDocument();
    }
  });

  it("拒绝缺少规定元数据的 JSON", async () => {
    render(<AdminContentPage />);
    fireEvent.click(screen.getByRole("button", { name: "导入内容包" }));
    fireEvent.change(screen.getByLabelText("选择内容包文件"), {
      target: { files: [new File(["{}"], "invalid.json", { type: "application/json" })] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "JSON 的 schema 与当前内容包格式不匹配",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("shanhaiedu.content-package.mock");
    expect(screen.getByRole("button", { name: "继续" })).toBeDisabled();
  });

  it("ZIP 只按明确文件名规则校验且不声称读取内容", async () => {
    render(<AdminContentPage />);
    fireEvent.click(screen.getByRole("button", { name: "导入内容包" }));
    fireEvent.change(screen.getByLabelText("选择内容包文件"), {
      target: {
        files: [new File(["not-a-real-archive"], "shanhai-content-fraction-kit-v2.zip")],
      },
    });
    expect(
      await screen.findByText("ZIP 文件名元数据符合规则；未读取压缩包内容。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续" })).toBeEnabled();
  });

  it("连续选择 JSON 时只保留最后一次选择的异步结果", async () => {
    const readers: Array<{
      reader: DeferredFileReader;
      file: File;
    }> = [];
    class DeferredFileReader {
      result: string | ArrayBuffer | null = null;
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;

      readAsText(file: File) {
        readers.push({ reader: this, file });
      }
    }
    const nativeFileReader = globalThis.FileReader;
    vi.stubGlobal("FileReader", DeferredFileReader);

    try {
      render(<AdminContentPage />);
      fireEvent.click(screen.getByRole("button", { name: "导入内容包" }));
      const input = screen.getByLabelText("选择内容包文件");
      const firstMetadata = JSON.stringify({
        schema: "shanhaiedu.content-package.mock/v1",
        title: "先选内容结构",
        kind: "内容结构",
        version: "v1",
      });
      const latestMetadata = JSON.stringify({
        schema: "shanhaiedu.content-package.mock/v1",
        title: "后选内容结构",
        kind: "内容结构",
        version: "v2",
      });

      fireEvent.change(input, {
        target: {
          files: [new File([firstMetadata], "first.json", { type: "application/json" })],
        },
      });
      fireEvent.change(input, {
        target: {
          files: [new File([latestMetadata], "latest.json", { type: "application/json" })],
        },
      });
      expect(readers).toHaveLength(2);

      const latestReader = readers[1]?.reader;
      if (!latestReader) throw new Error("缺少后选文件读取器");
      await act(async () => {
        latestReader.result = latestMetadata;
        latestReader.onload?.();
        await Promise.resolve();
      });
      expect(await screen.findByText("JSON 元数据检查通过。")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "继续" }));
      fireEvent.click(screen.getByRole("button", { name: "继续" }));
      expect(screen.getByText(/将发布“后选内容结构”/)).toBeInTheDocument();

      const firstReader = readers[0]?.reader;
      if (!firstReader) throw new Error("缺少先选文件读取器");
      await act(async () => {
        firstReader.result = firstMetadata;
        firstReader.onload?.();
        await Promise.resolve();
      });
      expect(screen.getByText(/将发布“后选内容结构”/)).toBeInTheDocument();
      expect(screen.queryByText(/将发布“先选内容结构”/)).not.toBeInTheDocument();
    } finally {
      vi.stubGlobal("FileReader", nativeFileReader);
    }
  });
});
