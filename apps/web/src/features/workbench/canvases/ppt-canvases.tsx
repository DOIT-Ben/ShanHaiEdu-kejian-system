import { useMemo, useState } from "react";
import { Download, ImageIcon, PencilLine, Presentation, Replace } from "lucide-react";
import {
  parseContent,
  pptExportContentSchema,
  pptLayoutLabels,
  pptOutlineContentSchema,
  pptPagesContentSchema,
  type PptPage,
} from "@/entities/content";
import { useDownloadFile } from "@/features/assets";
import { formatDateTime } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";
import { Badge, Button, Dialog, DialogContent, DialogFooter, FormField, Textarea } from "@/shared/ui";
import { AssetPicker } from "@/widgets";
import type { CanvasProps } from "../registry";
import { InvalidContent } from "./invalid-content";

/** PPT 大纲画布。 */
export function PptOutlineCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(pptOutlineContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="PPT大纲" />;
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-2">
        《{content.lesson_title}》 · 预计 {content.estimated_page_count} 页
      </p>
      <ol className="space-y-3">
        {content.sections.map((section, index) => (
          <li key={section.section_id} className="rounded-card border border-line bg-surface-1 p-4">
            <h4 className="text-sm font-semibold text-ink-1">
              {index + 1}. {section.title}
            </h4>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {section.page_titles.map((title, pageIndex) => (
                <li key={pageIndex} className="rounded-control bg-surface-2 px-2.5 py-1 text-xs text-ink-2">
                  {title}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  );
}

function PageCard({
  page,
  accent,
  pending,
  onRevise,
  onReplaceImage,
}: {
  page: PptPage;
  accent: string;
  pending?: boolean;
  onRevise: (instruction: string) => void;
  onReplaceImage: () => void;
}) {
  const [reviseOpen, setReviseOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const isCover = page.layout === "cover";
  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface-1">
      {/* 页面缩略渲染：封面为设计封面，正文页纯白底 */}
      <div
        className={cn("aspect-video w-full border-b border-line p-4", isCover ? "text-white" : "bg-white")}
        style={isCover ? { background: `linear-gradient(135deg, ${accent}, #10225E)` } : undefined}
      >
        <p className={cn("text-[10px]", isCover ? "text-white/70" : "text-ink-muted")}>
          第 {page.page_no} 页 · {pptLayoutLabels[page.layout]}
        </p>
        <p className={cn("mt-1 font-semibold", isCover ? "text-lg" : "text-sm")} style={isCover ? undefined : { color: "#182033" }}>
          {page.title}
        </p>
        <div className="mt-1.5 space-y-1">
          {page.blocks.slice(0, 3).map((block) =>
            block.type === "image" ? (
              <p key={block.block_id} className="flex items-center gap-1 text-[10px] text-ink-muted">
                <ImageIcon className="size-3" aria-hidden />
                {block.asset_id ? "已配图" : "待配图"}
              </p>
            ) : block.type === "bullets" ? (
              <ul key={block.block_id} className={cn("list-inside list-disc text-[10px] leading-4", isCover ? "text-white/85" : "text-ink-2")}>
                {block.items.slice(0, 3).map((item, index) => (
                  <li key={index} className="truncate">
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p key={block.block_id} className={cn("truncate text-[10px] leading-4", isCover ? "text-white/85" : "text-ink-2")}>
                {block.text}
              </p>
            ),
          )}
        </div>
      </div>
      <div className="space-y-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <Badge tone={page.status === "approved" ? "success" : page.status === "revision_required" ? "warning" : "neutral"}>
            {page.status === "approved" ? "已确认" : page.status === "revision_required" ? "需修改" : "待审核"}
          </Badge>
          <div className="flex items-center gap-1">
            <Button size="sm" variant="ghost" onClick={() => setReviseOpen(true)} disabled={pending}>
              <PencilLine className="size-3.5" aria-hidden />
              修改
            </Button>
            {page.blocks.some((block) => block.type === "image") ? (
              <Button size="sm" variant="ghost" onClick={onReplaceImage} disabled={pending} title="替换配图">
                <Replace className="size-3.5" aria-hidden />
              </Button>
            ) : null}
          </div>
        </div>
        {page.speaker_notes ? <p className="line-clamp-2 text-xs leading-5 text-ink-muted">讲稿：{page.speaker_notes}</p> : null}
      </div>

      <Dialog open={reviseOpen} onOpenChange={setReviseOpen}>
        <DialogContent title={`修改第 ${page.page_no} 页`} description="只调整这一页的内容与讲稿，其余页面不受影响。">
          <FormField label="修改意见" required>
            {({ id, describedBy }) => (
              <Textarea
                id={id}
                aria-describedby={describedBy}
                rows={3}
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder="例如：例题换成两位数的加法，图示更直观。"
              />
            )}
          </FormField>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setReviseOpen(false)}>
              取消
            </Button>
            <Button
              disabled={instruction.trim().length === 0}
              onClick={() => {
                onRevise(instruction.trim());
                setReviseOpen(false);
                setInstruction("");
              }}
            >
              提交修改
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** PPT 页面画布：页面网格 + 单页修订 + 替换配图。 */
export function PptPagesCanvas({ workspace, projectId, onItemAction, itemActionPending }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(pptPagesContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  const [pickerFor, setPickerFor] = useState<string | null>(null);
  if (!content) return <InvalidContent nodeTitle="PPT页面" />;
  return (
    <div>
      <p className="mb-3 text-sm text-ink-2">
        《{content.lesson_title}》 · 共 {content.pages.length} 页 · 封面为设计封面，正文页为纯白底
      </p>
      <div className="grid gap-3 xl:grid-cols-3 lg:grid-cols-2">
        {content.pages.map((page) => (
          <PageCard
            key={page.page_id}
            page={page}
            accent={content.theme.accent_color}
            pending={itemActionPending}
            onRevise={(instruction) => onItemAction({ itemId: page.page_id, action: "revise", instruction })}
            onReplaceImage={() => setPickerFor(page.page_id)}
          />
        ))}
      </div>
      <AssetPicker
        open={pickerFor !== null}
        onOpenChange={(open) => {
          if (!open) setPickerFor(null);
        }}
        projectId={projectId}
        defaultType="image"
        title="替换页面配图"
        onConfirm={(asset) => {
          if (pickerFor) {
            onItemAction({ itemId: pickerFor, action: "replace_image", payload: { asset_id: asset.asset_id } });
          }
        }}
      />
    </div>
  );
}

/** PPT 导出画布：PPTX 产物 + 下载 + 导出警告。 */
export function PptExportCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(pptExportContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  const download = useDownloadFile();
  if (!content) return <InvalidContent nodeTitle="PPT导出" />;
  const file = latest?.file_objects?.[0] ?? null;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 rounded-card border border-line bg-surface-1 p-5">
        <span className="flex size-12 items-center justify-center rounded-card bg-brand-selected text-brand">
          <Presentation className="size-6" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink-1">{file?.file_name ?? "课件.pptx"}</p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {content.page_count} 页 · 导出于 {formatDateTime(content.exported_at)}
          </p>
        </div>
        <Button
          onClick={() => {
            if (content.file_object_id) {
              download.mutate({ fileObjectId: content.file_object_id, fileName: file?.file_name });
            }
          }}
          loading={download.isPending}
          disabled={!content.file_object_id}
        >
          <Download className="size-4" aria-hidden />
          下载 PPTX
        </Button>
      </div>
      {content.warnings.length > 0 ? (
        <div className="rounded-control border border-warning/40 bg-warning-surface px-4 py-3">
          <p className="text-sm font-medium text-ink-1">导出提示</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-ink-2">
            {content.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
