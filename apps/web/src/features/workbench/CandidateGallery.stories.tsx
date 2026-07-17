import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CandidateGallery } from "./parts";
import { Button } from "@/shared/ui";
import type { GenerationResult } from "@/shared/api";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function svgPreview(label: string): string {
  return `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="%23315ef5" opacity="0.12"/><text x="320" y="190" font-size="28" text-anchor="middle" fill="%23315ef5">${encodeURIComponent(label)}</text></svg>`;
}

function result(partial: Partial<GenerationResult>): GenerationResult {
  return {
    id: partial.id ?? "r-1",
    item_key: "ITEM-01",
    media_type: "image",
    review_state: "pending",
    technical_check: "passed",
    preview_url: svgPreview(partial.id ?? "候选"),
    created_at: "2026-07-16T10:00:00Z",
    ...partial,
  } as GenerationResult;
}

const meta: Meta<typeof CandidateGallery> = {
  title: "工作台/候选画廊",
  component: CandidateGallery,
  decorators: [
    (Story) => (
      <QueryClientProvider client={queryClient}>
        <div className="max-w-3xl">
          <Story />
        </div>
      </QueryClientProvider>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof CandidateGallery>;

/** 多候选：大图 + 缩略图切换 + 每个候选的质量检查。 */
export const 多候选: Story = {
  args: {
    results: [
      result({ id: "候选A" }),
      result({ id: "候选B", technical_check: "failed", technical_check_detail: "画面主体被裁切。" }),
      result({ id: "候选C", review_state: "adopted" }),
    ],
    renderActions: (r) => (
      <Button size="sm" disabled={r.review_state === "adopted"}>
        {r.review_state === "adopted" ? "已采用" : "采用这个结果"}
      </Button>
    ),
  },
};

/** 空态：不出现假的占位候选。 */
export const 空态: Story = {
  args: { results: [], emptyHint: "点击「开始生成」制作候选。" },
};
