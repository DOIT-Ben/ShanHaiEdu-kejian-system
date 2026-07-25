import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  MaterialParsePageDto,
  MaterialParseVersionDto,
} from "@/features/materials/api/materialsApi";
import { MaterialScopePanel } from "@/features/materials/components/MaterialScopePanel";

const workflow = vi.hoisted(() => ({
  approveMutate: vi.fn(),
  createMutate: vi.fn(),
}));

vi.mock("@/shared/api/client", () => ({ isCsrfTokenAvailable: () => true }));
vi.mock("@/features/materials/hooks/useMaterialScopeWorkflow", () => ({
  useApproveMaterialScopeMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: workflow.approveMutate,
  }),
  useCreateMaterialScopeMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: workflow.createMutate,
  }),
}));

const pages: MaterialParsePageDto[] = [1, 2, 3].map((pageNumber) => ({
  image_count: pageNumber === 2 ? 1 : 0,
  page_number: pageNumber,
  text_block_count: 1,
  text_preview: `第 ${String(pageNumber)} 页`,
}));
const parseVersion = {
  id: "parse-version-1",
  page_count: 3,
  status: "succeeded",
} as MaterialParseVersionDto;

function runtime(artifact?: Record<string, unknown>) {
  return {
    aggregateQuery: { refetch: vi.fn() },
    artifact,
    latestApproval: undefined,
    refetch: vi.fn().mockResolvedValue(undefined),
  } as never;
}

describe("MaterialScopePanel", () => {
  beforeEach(() => {
    workflow.approveMutate.mockReset();
    workflow.createMutate.mockReset();
  });

  it("saves the selected physical page range against the exact material parse", () => {
    render(
      <MaterialScopePanel
        materialId="material-1"
        pages={pages}
        parseVersion={parseVersion}
        projectId="project-1"
        runtime={runtime()}
      />,
    );

    fireEvent.change(screen.getByLabelText("起始物理页"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("结束物理页"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "保存教材范围" }));

    expect(workflow.createMutate).toHaveBeenCalledWith({
      material_parse_version_id: "parse-version-1",
      page_end: 3,
      page_start: 2,
      source_material_id: "material-1",
    });
  });

  it("approves only the exact current submitted scope version", () => {
    render(
      <MaterialScopePanel
        materialId="material-1"
        pages={pages}
        parseVersion={parseVersion}
        projectId="project-1"
        runtime={runtime({
          current_approved_version: null,
          current_submitted_version: {
            content: {
              material_parse_version_id: "parse-version-1",
              page_end: 3,
              page_start: 2,
              source_material_id: "material-1",
            },
            id: "scope-version-1",
          },
          status: "in_review",
        })}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "确认当前范围" }));
    expect(workflow.approveMutate).toHaveBeenCalledOnce();
    expect(screen.getByText(/物理页 2 至 3，等待教师确认/)).toBeVisible();
  });

  it("treats another textbook scope as absent on the current material", () => {
    render(
      <MaterialScopePanel
        materialId="material-2"
        pages={pages}
        parseVersion={parseVersion}
        projectId="project-1"
        runtime={runtime({
          current_approved_version: {
            content: {
              material_parse_version_id: "parse-version-other",
              page_end: 2,
              page_start: 1,
              source_material_id: "material-1",
            },
            id: "scope-version-1",
          },
          current_submitted_version: null,
          status: "approved",
        })}
      />,
    );

    expect(screen.getByRole("button", { name: "保存教材范围" })).toBeEnabled();
    expect(screen.queryByText(/已保存范围/)).not.toBeInTheDocument();
  });
});
