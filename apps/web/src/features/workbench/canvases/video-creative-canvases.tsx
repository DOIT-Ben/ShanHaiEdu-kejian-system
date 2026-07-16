import { useMemo } from "react";
import { ImageIcon } from "lucide-react";
import {
  masterImageContentSchema,
  masterScriptContentSchema,
  parseContent,
  visualDirectionContentSchema,
} from "@/entities/content";
import { useAssetDetail } from "@/features/assets";
import { cn } from "@/shared/lib/cn";
import { Badge, Button, Skeleton } from "@/shared/ui";
import type { CanvasProps } from "../registry";
import { InvalidContent } from "./invalid-content";

/** 母版剧本画布：选定创意 → 场景脚本。 */
export function MasterScriptCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(masterScriptContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="母版剧本" />;
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-2">
        基于导入创意「{content.intro_option_title}」 · 总时长约 {content.total_duration_seconds} 秒
      </p>
      <ol className="space-y-3">
        {content.scenes.map((scene) => (
          <li key={scene.scene_id} className="rounded-card border border-line bg-surface-1 p-4">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-ink-1">
                场景{scene.scene_no}｜{scene.title}
              </h4>
              <span className="text-xs text-ink-muted">{scene.duration_seconds} 秒</span>
            </div>
            <p className="mt-1.5 text-sm leading-6 text-ink-2">旁白：{scene.narration}</p>
            {scene.visual_idea ? <p className="mt-1 text-xs leading-5 text-ink-muted">画面：{scene.visual_idea}</p> : null}
            {scene.anchor_id ? <Badge tone="brand" className="mt-2">承载课程锚点</Badge> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** 视觉方向画布：风格关键词 / 色板 / 角色与场景说明。 */
export function VisualDirectionCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(visualDirectionContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="视觉方向" />;
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-semibold text-ink-1">{content.style_name}</h4>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {content.style_keywords.map((keyword) => (
            <span key={keyword} className="rounded-control bg-surface-2 px-2.5 py-1 text-xs text-ink-2">
              {keyword}
            </span>
          ))}
        </div>
      </div>
      {content.palette.length > 0 ? (
        <div>
          <p className="mb-1.5 text-xs font-medium text-ink-muted">色板</p>
          <div className="flex gap-2">
            {content.palette.map((color) => (
              <span key={color} className="flex flex-col items-center gap-1">
                <span className="size-9 rounded-control border border-line" style={{ backgroundColor: color }} />
                <span className="font-mono text-[10px] text-ink-muted">{color}</span>
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {content.character_notes ? (
        <p className="text-sm leading-6 text-ink-2">
          <span className="font-medium text-ink-1">角色：</span>
          {content.character_notes}
        </p>
      ) : null}
      {content.scene_notes ? (
        <p className="text-sm leading-6 text-ink-2">
          <span className="font-medium text-ink-1">场景：</span>
          {content.scene_notes}
        </p>
      ) : null}
    </div>
  );
}

function CandidateImage({
  assetId,
  selected,
  promptSummary,
  onSelect,
  pending,
}: {
  assetId: string;
  selected: boolean;
  promptSummary: string;
  onSelect: () => void;
  pending?: boolean;
}) {
  const asset = useAssetDetail(assetId);
  if (asset.isPending) return <Skeleton className="h-48" />;
  const data = asset.data?.asset;
  return (
    <figure
      className={cn(
        "overflow-hidden rounded-card border bg-surface-1 transition-shadow",
        selected ? "border-brand ring-2 ring-brand/25" : "border-line hover:shadow-sm",
      )}
    >
      {data?.thumbnail_url ? (
        <img src={data.thumbnail_url} alt={data.name} className="aspect-video w-full object-cover" />
      ) : (
        <span className="flex aspect-video items-center justify-center bg-surface-2 text-ink-muted">
          <ImageIcon className="size-6" aria-hidden />
        </span>
      )}
      <figcaption className="space-y-2 p-3">
        <p className="line-clamp-2 text-xs leading-5 text-ink-2">{promptSummary}</p>
        <div className="flex items-center justify-between">
          {selected ? <Badge tone="brand">已选为母图</Badge> : <span />}
          {!selected ? (
            <Button size="sm" variant="secondary" onClick={onSelect} disabled={pending}>
              选为视觉母图
            </Button>
          ) : null}
        </div>
      </figcaption>
    </figure>
  );
}

/** 视觉母图画布：3 张候选，选定其一作为整片视觉基准。 */
export function MasterImageCanvas({ workspace, onSaveEdited, savePending }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(masterImageContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="视觉母图" />;

  const select = (candidateId: string, assetId: string) => {
    onSaveEdited({
      candidates: content.candidates.map((candidate) => ({ ...candidate, selected: candidate.candidate_id === candidateId })),
      selected_asset_id: assetId,
    });
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-2">选定一张作为整片的视觉基准；后续图片资产将以母图风格为准生成。</p>
      <div className="grid gap-3 lg:grid-cols-3 md:grid-cols-2">
        {content.candidates.map((candidate) => (
          <CandidateImage
            key={candidate.candidate_id}
            assetId={candidate.asset_id}
            selected={content.selected_asset_id === candidate.asset_id}
            promptSummary={candidate.prompt_summary}
            pending={savePending}
            onSelect={() => select(candidate.candidate_id, candidate.asset_id)}
          />
        ))}
      </div>
    </div>
  );
}
