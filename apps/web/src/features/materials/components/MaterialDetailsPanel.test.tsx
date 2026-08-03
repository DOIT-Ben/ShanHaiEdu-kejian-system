import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { FileAssetDto, MaterialParseVersionDto } from "@/features/materials/api/materialsApi";
import { MaterialDetailsPanel } from "@/features/materials/components/MaterialDetailsPanel";

describe("MaterialDetailsPanel", () => {
  it("首次读取时只展示可访问的加载状态", () => {
    render(<MaterialDetailsPanel loading onRefresh={vi.fn()} parseVersions={[]} />);

    expect(screen.getByRole("status")).toHaveTextContent("正在读取教材文件和解析记录");
    expect(screen.queryByText("尚未读取到教材文件。")).not.toBeInTheDocument();
    expect(screen.queryByText("暂无解析记录。")).not.toBeInTheDocument();
  });

  it("展示教材文件校验与解析失败事实", () => {
    const asset = {
      asset_key: "textbook.pdf",
      current_version: {
        byte_size: 4096,
        page_count: 12,
        scan_status: "clean",
        sha256: "a".repeat(64),
      },
      status: "active",
    } as FileAssetDto;
    const versions = [
      {
        error_code: "PDF_TEXT_EMPTY",
        id: "01960000-0000-7000-8000-000000000201",
        parser_name: "pdf-parser",
        parser_version: "1.0",
        status: "failed",
        version_no: 2,
      } as MaterialParseVersionDto,
    ];

    render(<MaterialDetailsPanel asset={asset} onRefresh={vi.fn()} parseVersions={versions} />);

    expect(screen.getByText("12 页")).toBeVisible();
    expect(screen.getByText("教材 PDF")).toBeVisible();
    expect(screen.queryByText("textbook.pdf")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("本次解析没有完成");
    expect(screen.queryByText("PDF_TEXT_EMPTY")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新教材状态" })).toBeEnabled();
  });

  it("只为 exact 当前文件的最新失败解析显示重新解析", () => {
    const onRetry = vi.fn();
    const asset = {
      current_version: {
        byte_size: 4096,
        id: "01960000-0000-7000-8000-000000000301",
        page_count: null,
        scan_status: "clean",
        sha256: "a".repeat(64),
      },
      status: "active",
    } as FileAssetDto;
    const failed = {
      error_code: "PDF_DAMAGED",
      file_asset_version_id: asset.current_version.id,
      id: "01960000-0000-7000-8000-000000000302",
      status: "failed",
      version_no: 2,
    } as MaterialParseVersionDto;
    const succeeded = {
      file_asset_version_id: asset.current_version.id,
      id: "01960000-0000-7000-8000-000000000303",
      status: "succeeded",
      version_no: 1,
    } as MaterialParseVersionDto;
    const { rerender } = render(
      <MaterialDetailsPanel
        asset={asset}
        onRefresh={vi.fn()}
        onRetry={onRetry}
        parseVersions={[failed, succeeded]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "重新解析" }));
    expect(onRetry).toHaveBeenCalledOnce();

    rerender(
      <MaterialDetailsPanel
        asset={asset}
        onRefresh={vi.fn()}
        onRetry={onRetry}
        parseVersions={[succeeded, failed]}
      />,
    );
    expect(screen.queryByRole("button", { name: "重新解析" })).not.toBeInTheDocument();

    rerender(
      <MaterialDetailsPanel
        asset={asset}
        onRefresh={vi.fn()}
        onRetry={onRetry}
        parseVersions={[
          { ...failed, file_asset_version_id: "01960000-0000-7000-8000-000000000399" },
        ]}
      />,
    );
    expect(screen.queryByRole("button", { name: "重新解析" })).not.toBeInTheDocument();
  });
});
