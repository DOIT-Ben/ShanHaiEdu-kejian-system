import { useState } from "react";
import { Link } from "react-router";
import { ArrowRight, Pencil, Star } from "lucide-react";
import { INTRO_CATEGORY_LABELS } from "@/shared/lib/teacherLanguage";
import { sortByRecommendation, type IntroOption } from "@/entities/content";
import { useCurrentIntroSelection, useIntroOptions, useUpdateIntroOption } from "@/features/intro";
import { AppError } from "@/shared/api";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  FormField,
  Input,
  Skeleton,
  Textarea,
  toast,
} from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { StepScaffold, StaleBanner } from "../parts";

/** 查看三类九套：科普/应用/故事 三类，每类三套；可修改，推荐星标。 */
export function IntroOptionsCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun } = useStepNodeRun();
  const { data, isPending } = useIntroOptions(lessonId);
  const { data: selection } = useCurrentIntroSelection(lessonId);
  const [editing, setEditing] = useState<IntroOption | null>(null);

  if (isPending || !data) {
    return (
      <div className="grid gap-4 p-6 md:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-48 rounded-lg" />
        ))}
      </div>
    );
  }

  const { optionSet } = data;
  const recommended = sortByRecommendation(optionSet.options)[0];
  const categories = ["science", "application", "story"] as const;
  const selectUrl = `/app/projects/${projectId}/lessons/${lessonId}/work/intro-selection`;

  return (
    <StepScaffold
      title="查看三类九套导入方案"
      description="科普·应用·故事三条思路各三套；可以先修改任意一套，再去选择。"
      status={nodeRun?.status}
      primaryAction={
        <Button asChild>
          <Link to={selectUrl}>
            去选择一套方案
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </Button>
      }
    >
      {nodeRun?.status === "stale" ? <StaleBanner nodeRun={nodeRun} /> : null}
      {selection ? (
        <p className="mb-5 rounded-lg border border-success-200 bg-success-50 p-3.5 text-sm text-ink">
          已选择「
          {optionSet.options.find((o) => o.option_key === selection.option_key)?.title ?? selection.option_key}
          」作为课堂导入。重新选择会替换后续视频依据。
        </p>
      ) : null}
      <div className="space-y-8">
        {categories.map((category) => (
          <section key={category} aria-label={INTRO_CATEGORY_LABELS[category]}>
            <h2 className="text-base font-semibold text-ink-strong">{INTRO_CATEGORY_LABELS[category]}</h2>
            <div className="mt-3 grid gap-4 lg:grid-cols-3">
              {optionSet.options
                .filter((option) => option.category === category)
                .map((option) => (
                  <article
                    key={option.option_key}
                    className="flex flex-col rounded-lg border border-line-subtle bg-surface p-4 shadow-card"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-semibold text-ink-strong">{option.title}</h3>
                      {recommended?.option_key === option.option_key ? (
                        <Badge tone="brand" icon={<Star className="size-3" aria-hidden />}>
                          推荐
                        </Badge>
                      ) : null}
                    </div>
                    <dl className="mt-2.5 flex-1 space-y-2 text-sm">
                      <div>
                        <dt className="text-xs text-ink-faint">开场钩子</dt>
                        <dd className="mt-0.5 leading-relaxed text-ink">{option.hook}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-ink-faint">课堂第一问</dt>
                        <dd className="mt-0.5 leading-relaxed text-ink">{option.classroom_first_question}</dd>
                      </div>
                      <div className="flex gap-4 text-xs text-ink-muted">
                        <span>约 {option.duration_seconds} 秒</span>
                        <span>推荐度 {option.recommendation_score}</span>
                      </div>
                    </dl>
                    <div className="mt-3 border-t border-line-subtle pt-3">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(option)}>
                        <Pencil className="size-4" aria-hidden />
                        修改这套
                      </Button>
                    </div>
                  </article>
                ))}
            </div>
          </section>
        ))}
      </div>
      <EditOptionDialog
        lessonId={lessonId}
        option={editing}
        etag={data.etag ?? ""}
        onClose={() => setEditing(null)}
      />
    </StepScaffold>
  );
}

function EditOptionDialog({
  lessonId,
  option,
  etag,
  onClose,
}: {
  lessonId: string;
  option: IntroOption | null;
  etag: string;
  onClose: () => void;
}) {
  const update = useUpdateIntroOption(lessonId);
  const [draft, setDraft] = useState<Record<string, string>>({});

  const fields = [
    ["title", "标题", "input"],
    ["hook", "开场钩子", "textarea"],
    ["classroom_first_question", "课堂第一问", "textarea"],
    ["course_anchor", "与本课的连接", "textarea"],
    ["handoff_moment", "交接时刻", "textarea"],
  ] as const;

  const value = (key: string) => draft[key] ?? String((option as unknown as Record<string, unknown>)?.[key] ?? "");

  return (
    <Dialog open={Boolean(option)} onOpenChange={(open) => !open && (setDraft({}), onClose())}>
      <DialogContent title={`修改「${option?.title ?? ""}」`} description="修改后系统会保留你的版本用于选择与视频制作。">
        <div className="max-h-[52vh] space-y-4 overflow-y-auto pr-1">
          {fields.map(([key, label, kind]) => (
            <FormField key={key} label={label}>
              {({ id }) =>
                kind === "input" ? (
                  <Input id={id} value={value(key)} onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))} />
                ) : (
                  <Textarea
                    id={id}
                    rows={2}
                    value={value(key)}
                    onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                  />
                )
              }
            </FormField>
          ))}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button
            disabled={Object.keys(draft).length === 0}
            loading={update.isPending}
            loadingText="正在保存…"
            onClick={() => {
              if (!option) return;
              update.mutate(
                { optionKey: option.option_key, etag, patch: draft },
                {
                  onSuccess: () => {
                    setDraft({});
                    onClose();
                    toast({ tone: "success", title: "方案已更新" });
                  },
                  onError: (error) => {
                    const message =
                      error instanceof AppError && error.isEditConflict
                        ? "方案集已更新，请刷新后再修改。"
                        : error.message;
                    toast({ tone: "danger", title: "保存失败", description: message });
                  },
                },
              );
            }}
          >
            保存修改
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
