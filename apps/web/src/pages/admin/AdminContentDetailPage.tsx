import { useParams, Link } from "react-router";
import { ArrowLeft, FlaskConical, Rocket } from "lucide-react";
import { useContentPackage, useDryRunContentPackage, usePublishContentPackage } from "@/features/admin";
import { ContentDefinitionRenderer } from "@/features/content-definition";
import { parseContentDefinition } from "@/entities/content";
import { formatDateTime } from "@/shared/lib/format";
import { AppError } from "@/shared/api";
import { Badge, Button, Panel, PanelBody, PanelHeader, Skeleton, toast } from "@/shared/ui";
import { DOMAIN_LABELS, PACKAGE_STATUS_META } from "./AdminContentPage";

/** 内容包详情：检查结果 → 预览 → 试运行 → 发布（版本不可变）。 */
export default function AdminContentDetailPage() {
  const { contentPackageId: packageId = "" } = useParams();
  const { data, isPending } = useContentPackage(packageId);
  const dryRun = useDryRunContentPackage(packageId);
  const publish = usePublishContentPackage(packageId);

  if (isPending || !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-96 rounded-lg" />
      </div>
    );
  }

  const pkg = data.package;
  const meta = PACKAGE_STATUS_META[pkg.status] ?? { label: pkg.status, tone: "neutral" as const };
  const issues = data.validation_issues ?? [];
  const errors = issues.filter((i) => i.severity === "error");
  let definition = null;
  try {
    definition = data.definition ? parseContentDefinition(data.definition) : null;
  } catch {
    definition = null;
  }

  const onActionError = (title: string) => (error: Error) => {
    const message =
      error instanceof AppError
        ? error.code === "PACKAGE_CHECKING"
          ? "系统检查还没有完成，请稍候。"
          : error.code === "DRY_RUN_REQUIRED"
            ? "发布前需要先完成试运行。"
            : error.code === "TEST_CASES_FAILING"
              ? "试运行未通过，请先解决检查结果中的问题。"
              : error.message
        : error.message;
    toast({ tone: "danger", title, description: message });
  };

  return (
    <div>
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to="/admin/content">
          <ArrowLeft className="size-4" aria-hidden />
          内容中心
        </Link>
      </Button>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-ink-strong">{pkg.title}</h1>
        <Badge tone={meta.tone}>{meta.label}</Badge>
        <span className="text-sm text-ink-muted">
          {DOMAIN_LABELS[pkg.domain] ?? pkg.domain} · 第 {pkg.current_version_no} 版
        </span>
        <span className="ml-auto flex gap-2">
          <Button
            variant="outline"
            disabled={pkg.status === "checking" || errors.length > 0}
            loading={dryRun.isPending}
            loadingText="正在试运行…"
            onClick={() =>
              dryRun.mutate(undefined, {
                onSuccess: () => toast({ tone: "info", title: "试运行已开始", description: "用样例数据完整渲染一遍。" }),
                onError: onActionError("无法试运行"),
              })
            }
          >
            <FlaskConical className="size-4" aria-hidden />
            试运行
          </Button>
          <Button
            disabled={pkg.status !== "dry_run"}
            loading={publish.isPending}
            loadingText="正在发布…"
            onClick={() =>
              publish.mutate(undefined, {
                onSuccess: () => toast({ tone: "success", title: "已发布新版本", description: "新项目将使用该版本。" }),
                onError: onActionError("无法发布"),
              })
            }
          >
            <Rocket className="size-4" aria-hidden />
            发布新版本
          </Button>
        </span>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_320px]">
        <Panel>
          <PanelHeader title="结构预览" description="按当前定义渲染的空白结构（老师看到的样子）。" />
          <PanelBody>
            {definition ? (
              <div className="sh-paper-canvas rounded-lg border border-line-subtle p-6">
                <ContentDefinitionRenderer definition={definition} value={{}} readOnly />
              </div>
            ) : (
              <p className="text-sm text-ink-muted">没有可预览的内容定义。</p>
            )}
          </PanelBody>
        </Panel>
        <div className="space-y-6">
          <Panel>
            <PanelHeader title={`检查结果（${issues.length}）`} />
            <PanelBody>
              {issues.length === 0 ? (
                <p className="text-sm text-ink-muted">没有发现问题。</p>
              ) : (
                <ul className="space-y-2">
                  {issues.map((issue, index) => (
                    <li
                      key={index}
                      className={
                        issue.severity === "error"
                          ? "rounded-md border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700"
                          : "rounded-md border border-warning-200 bg-warning-50 p-3 text-sm text-warning-700"
                      }
                    >
                      {issue.message}
                    </li>
                  ))}
                </ul>
              )}
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="版本记录" />
            <PanelBody>
              {data.versions && data.versions.length > 0 ? (
                <ol className="space-y-2 text-sm">
                  {data.versions.map((version) => (
                    <li key={version.version_no} className="flex items-baseline justify-between gap-3">
                      <span className="font-medium text-ink-strong">第 {version.version_no} 版</span>
                      <span className="text-xs text-ink-muted">{formatDateTime(version.published_at)}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-ink-muted">还没有发布过版本。</p>
              )}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </div>
  );
}
