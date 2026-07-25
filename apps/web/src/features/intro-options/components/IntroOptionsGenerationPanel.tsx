import { RefreshCw } from "lucide-react";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";

type IntroOptionsGenerationPanelProps = {
  artifactReady: boolean;
  canWrite: boolean;
  error: Error | null;
  jobLive: boolean;
  onRevisionChange: (value: string) => void;
  onStart: () => void;
  pending: boolean;
  revision: string;
};

export function IntroOptionsGenerationPanel({
  artifactReady,
  canWrite,
  error,
  jobLive,
  onRevisionChange,
  onStart,
  pending,
  revision,
}: IntroOptionsGenerationPanelProps) {
  return (
    <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">三类九套课堂导入</h2>
          <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
            {artifactReady
              ? "方案已生成，可编辑正文和推荐说明。"
              : "生成科普、应用、故事各三套方案。"}
          </p>
        </div>
        <Button disabled={!canWrite || pending || jobLive || artifactReady} onClick={onStart}>
          <RefreshCw aria-hidden="true" />
          {artifactReady ? "九套方案已生成" : "生成三类九套"}
        </Button>
      </div>
      {!artifactReady ? (
        <label className="mt-4 block text-sm font-medium text-[var(--sh-ink-default)]">
          本次生成要求
          <textarea
            className="mt-2 min-h-24 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-3 leading-6"
            maxLength={6000}
            onChange={(event) => onRevisionChange(event.target.value)}
            placeholder="可选：填写希望重点体现的课堂情境或导入方式"
            value={revision}
          />
        </label>
      ) : null}
      {!canWrite ? (
        <p className="mt-3 text-sm text-[var(--sh-warning)]" role="status">
          当前会话只能查看，刷新或重新登录后再执行写操作。
        </p>
      ) : null}
      {error ? (
        <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(error, "三类九套生成没有启动，请刷新后重试。")}
        </p>
      ) : null}
    </section>
  );
}
