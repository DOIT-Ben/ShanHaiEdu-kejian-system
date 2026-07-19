import * as Tabs from "@radix-ui/react-tabs";
import { Check, ChevronRight, FileUp, FlaskConical, Plus, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { getMockDraft, saveMockDraft } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { HorizontalScrollArea } from "@/shared/ui/HorizontalScrollArea";
import { StatusBadge } from "@/shared/ui/StatusBadge";

const CONTENT_PACKAGES_KEY = "admin.content-packages";
const CONTENT_SCHEMA = "shanhaiedu.content-package.mock/v1";
const MAX_JSON_BYTES = 1_048_576;
const JSON_MIME_TYPES = new Set(["", "application/json", "text/json"]);
const packageKinds = ["内容结构", "创意与锚定规则", "PPT 工作手册", "视频生产规则"] as const;

type ContentPackage = {
  title: string;
  kind: (typeof packageKinds)[number] | "内容包归档";
  version: string;
  usage: string;
  status: "approved" | "draft";
};

type PendingPackage = ContentPackage & { source: "json" | "zip"; fileName: string };
type ImportStage = "upload" | "check" | "preview" | "trial" | "published";

const defaultPackages: ContentPackage[] = [
  {
    title: "小学数学默认教案",
    kind: "内容结构",
    version: "12 个顶级章节",
    usage: "18 个项目",
    status: "approved",
  },
  {
    title: "三类九套课堂导入",
    kind: "创意与锚定规则",
    version: "9 套方案",
    usage: "12 个项目",
    status: "approved",
  },
  {
    title: "白底图片化 PPT 手册",
    kind: "PPT 工作手册",
    version: "7 条强制规则",
    usage: "9 个项目",
    status: "approved",
  },
  {
    title: "课堂导入视频规则",
    kind: "视频生产规则",
    version: "10 个阶段",
    usage: "6 个项目",
    status: "draft",
  },
];

function readPackages() {
  return getMockDraft<ContentPackage[]>(CONTENT_PACKAGES_KEY)?.value ?? defaultPackages;
}

function readFileText(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("无法读取文件"));
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.readAsText(file, "UTF-8");
  });
}

function parseJsonPackage(value: unknown, fileName: string): PendingPackage {
  if (!value || typeof value !== "object") throw new Error("JSON 顶层必须是对象");
  const metadata = value as Record<string, unknown>;
  if (metadata.schema !== CONTENT_SCHEMA) throw new Error("JSON 的 schema 与当前内容包格式不匹配");
  if (typeof metadata.title !== "string" || !metadata.title.trim()) throw new Error("缺少 title");
  if (!packageKinds.includes(metadata.kind as (typeof packageKinds)[number]))
    throw new Error("kind 不在允许范围内");
  if (typeof metadata.version !== "string" || !metadata.version.trim())
    throw new Error("缺少 version");
  return {
    title: metadata.title.trim(),
    kind: metadata.kind as (typeof packageKinds)[number],
    version: metadata.version.trim(),
    usage:
      typeof metadata.usage === "string" && metadata.usage.trim()
        ? metadata.usage.trim()
        : "0 个项目",
    status: "approved",
    source: "json",
    fileName,
  };
}

async function validatePackageFile(file: File): Promise<PendingPackage> {
  if (/\.json$/i.test(file.name)) {
    if (!JSON_MIME_TYPES.has(file.type.toLowerCase())) throw new Error("JSON 文件类型无效");
    if (file.size > MAX_JSON_BYTES) throw new Error("JSON 文件不能超过 1 MB");
    let metadata: unknown;
    try {
      metadata = JSON.parse(await readFileText(file)) as unknown;
    } catch (reason) {
      if (reason instanceof SyntaxError) throw new Error("JSON 格式无效");
      throw reason;
    }
    return parseJsonPackage(metadata, file.name);
  }
  if (/\.zip$/i.test(file.name)) {
    const match = /^shanhai-content-([\p{L}\p{N}][\p{L}\p{N}-]*)-v([1-9]\d*)\.zip$/iu.exec(
      file.name,
    );
    if (!match) throw new Error("ZIP 文件名须为 shanhai-content-名称-v数字.zip");
    const slug = match[1];
    const version = match[2];
    if (!slug || !version) throw new Error("ZIP 文件名元数据不完整");
    return {
      title: slug.split("-").join(" "),
      kind: "内容包归档",
      version: `归档版本 v${version}`,
      usage: "0 个项目",
      status: "approved",
      source: "zip",
      fileName: file.name,
    };
  }
  throw new Error("仅支持 JSON 或 ZIP 文件");
}

function ContentPackagesTable({
  items,
  onSelect,
}: {
  items: ContentPackage[];
  onSelect: (item: ContentPackage) => void;
}) {
  return (
    <HorizontalScrollArea
      ariaLabel="内容包列表"
      className="mt-5"
      hintTestId="admin-content-table-scroll-next"
      viewportClassName="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"
    >
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead className="bg-[var(--sh-surface-soft)] text-xs text-[var(--sh-ink-muted)]">
          <tr>
            <th className="px-5 py-3 font-semibold">名称</th>
            <th className="px-5 py-3 font-semibold">类型</th>
            <th className="px-5 py-3 font-semibold">当前内容</th>
            <th className="px-5 py-3 font-semibold">使用情况</th>
            <th className="px-5 py-3 font-semibold">状态</th>
            <th className="px-5 py-3 font-semibold">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--sh-line-subtle)]">
          {items.map((item) => (
            <tr key={`${item.title}-${item.version}`}>
              <td className="px-5 py-4 font-semibold text-[var(--sh-ink-strong)]">{item.title}</td>
              <td className="px-5 py-4 text-[var(--sh-ink-muted)]">{item.kind}</td>
              <td className="px-5 py-4">{item.version}</td>
              <td className="px-5 py-4">{item.usage}</td>
              <td className="whitespace-nowrap px-4 py-4">
                <StatusBadge status={item.status} />
              </td>
              <td className="whitespace-nowrap px-4 py-4">
                <button
                  className="font-semibold text-[var(--sh-brand-600)]"
                  onClick={() => onSelect(item)}
                  type="button"
                >
                  查看详情
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </HorizontalScrollArea>
  );
}

export function AdminContentPage() {
  const [packages, setPackages] = useState(readPackages);
  const [importOpen, setImportOpen] = useState(false);
  const [fileName, setFileName] = useState("");
  const [pending, setPending] = useState<PendingPackage | null>(null);
  const [validation, setValidation] = useState("");
  const [selectedPackage, setSelectedPackage] = useState<ContentPackage | null>(null);
  const [stage, setStage] = useState<ImportStage>("upload");
  const fileSelectionId = useRef(0);
  const openImport = () => {
    fileSelectionId.current += 1;
    setFileName("");
    setPending(null);
    setValidation("");
    setStage("upload");
    setImportOpen(true);
  };
  const closeImport = () => {
    fileSelectionId.current += 1;
    setImportOpen(false);
  };
  const chooseFile = async (file?: File) => {
    const selectionId = ++fileSelectionId.current;
    setFileName(file?.name ?? "");
    setPending(null);
    setValidation("");
    if (!file) return;
    try {
      const metadata = await validatePackageFile(file);
      if (selectionId !== fileSelectionId.current) return;
      setPending(metadata);
      setValidation(
        metadata.source === "zip"
          ? "ZIP 文件名元数据符合规则；未读取压缩包内容。"
          : "JSON 元数据检查通过。",
      );
    } catch (reason) {
      if (selectionId !== fileSelectionId.current) return;
      setValidation(reason instanceof Error ? reason.message : "文件元数据无效");
    }
  };
  const next = () => {
    if (!pending) return;
    if (stage === "upload") return setStage("check");
    if (stage === "check") return setStage("preview");
    if (stage === "preview") return setStage("trial");
    if (stage === "trial") {
      const published: ContentPackage = {
        title: pending.title,
        kind: pending.kind,
        version: pending.version,
        usage: pending.usage,
        status: "approved",
      };
      if (
        packages.some(
          (item) => item.title === published.title && item.version === published.version,
        )
      ) {
        setPending(null);
        setValidation("同名同版本内容包已经发布，请提高版本号后再导入。");
        setStage("upload");
        return;
      }
      const nextPackages = [...packages, published];
      saveMockDraft(CONTENT_PACKAGES_KEY, nextPackages);
      setPackages(nextPackages);
      setStage("published");
    }
  };
  return (
    <div className="p-5 md:p-6">
      <FocusPageHeader
        action={
          <Button onClick={openImport}>
            <Plus aria-hidden="true" />
            导入内容包
          </Button>
        }
        description="管理教案结构、生成指令、课堂导入、PPT、视频和质量检查规则。已发布版本不可原地覆盖。"
        title="内容中心"
      />
      {importOpen ? (
        <section className="mt-6 rounded-[var(--sh-radius-md)] border border-[var(--sh-brand-100)] bg-[var(--sh-surface-elevated)] p-6 shadow-[var(--sh-shadow-card)]">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-[var(--sh-brand-600)]">标准导入流程</p>
              <h2 className="mt-1 text-lg font-bold text-[var(--sh-ink-strong)]">导入新的内容包</h2>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-[var(--sh-ink-muted)]">
              <span>上传</span>
              <ChevronRight aria-hidden="true" className="size-3 shrink-0" />
              <span>元数据检查</span>
              <ChevronRight aria-hidden="true" className="size-3 shrink-0" />
              <span>预览变化</span>
              <ChevronRight aria-hidden="true" className="size-3 shrink-0" />
              <span>试运行</span>
              <ChevronRight aria-hidden="true" className="size-3 shrink-0" />
              <span>发布</span>
            </div>
          </div>
          {stage === "upload" ? (
            <label className="mt-6 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-[var(--sh-radius-sm)] border border-dashed border-[var(--sh-line-strong)] bg-[var(--sh-surface-soft)] px-5 text-center">
              <UploadCloud aria-hidden="true" className="size-8 text-[var(--sh-brand-600)]" />
              <span className="mt-3 text-sm font-semibold">选择内容包文件</span>
              <span className="mt-1 text-xs text-[var(--sh-ink-muted)]">
                JSON 需包含规定 schema、title、kind、version；ZIP 只校验文件名元数据。
              </span>
              <input
                accept=".json,.zip"
                aria-label="选择内容包文件"
                className="sr-only"
                onChange={(event) => void chooseFile(event.target.files?.[0])}
                type="file"
              />
              {fileName ? (
                <span className="mt-3 rounded-full bg-[var(--sh-surface-elevated)] px-3 py-1 text-xs font-semibold text-[var(--sh-brand-700)]">
                  {fileName}
                </span>
              ) : null}
              {validation ? (
                <span
                  className={`mt-2 text-xs font-semibold ${pending ? "text-[var(--sh-success)]" : "text-[var(--sh-danger)]"}`}
                  role={pending ? "status" : "alert"}
                >
                  {validation}
                </span>
              ) : null}
            </label>
          ) : (
            <div className="mt-6 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-5">
              <p className="flex items-center gap-2 font-semibold text-[var(--sh-ink-strong)]">
                {stage === "check" ? (
                  <FileUp aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
                ) : stage === "trial" ? (
                  <FlaskConical aria-hidden="true" className="size-5 text-[var(--sh-warning)]" />
                ) : (
                  <Check aria-hidden="true" className="size-5 text-[var(--sh-success)]" />
                )}
                {stage === "check"
                  ? validation
                  : stage === "preview"
                    ? `将发布“${pending?.title ?? "内容包"}”${pending?.version ?? ""}`
                    : stage === "trial"
                      ? "试运行通过"
                      : "新版本已发布并加入内容列表"}
              </p>
              <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
                已有项目继续使用原版本，新项目可以选择本次发布版本。
              </p>
            </div>
          )}
          <div className="mt-5 flex justify-end gap-2">
            <Button onClick={closeImport} variant="quiet">
              取消
            </Button>
            <Button disabled={stage === "published" || !pending} onClick={next}>
              {stage === "trial" ? "发布新版本" : stage === "published" ? "已发布" : "继续"}
            </Button>
          </div>
        </section>
      ) : null}
      <Tabs.Root className="mt-7" defaultValue="all">
        <Tabs.List className="flex gap-1 border-b border-[var(--sh-line-subtle)]">
          <Tabs.Trigger
            className="border-b-2 border-transparent px-4 py-3 text-sm data-[state=active]:border-[var(--sh-brand-500)] data-[state=active]:font-semibold"
            value="all"
          >
            全部内容
          </Tabs.Trigger>
          <Tabs.Trigger
            className="border-b-2 border-transparent px-4 py-3 text-sm data-[state=active]:border-[var(--sh-brand-500)] data-[state=active]:font-semibold"
            value="structure"
          >
            内容结构
          </Tabs.Trigger>
          <Tabs.Trigger
            className="border-b-2 border-transparent px-4 py-3 text-sm data-[state=active]:border-[var(--sh-brand-500)] data-[state=active]:font-semibold"
            value="rules"
          >
            规则与指令
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content aria-label="全部内容" className="outline-none" value="all">
          <ContentPackagesTable items={packages} onSelect={setSelectedPackage} />
        </Tabs.Content>
        <Tabs.Content aria-label="内容结构" className="outline-none" value="structure">
          <ContentPackagesTable
            items={packages.filter((item) => item.kind === "内容结构")}
            onSelect={setSelectedPackage}
          />
        </Tabs.Content>
        <Tabs.Content aria-label="规则与指令" className="outline-none" value="rules">
          <ContentPackagesTable
            items={packages.filter((item) => item.kind !== "内容结构")}
            onSelect={setSelectedPackage}
          />
        </Tabs.Content>
      </Tabs.Root>
      {selectedPackage ? (
        <section
          aria-label={`${selectedPackage.title}详情`}
          className="mt-5 rounded-[var(--sh-radius-md)] border border-[var(--sh-brand-100)] bg-[var(--sh-surface-elevated)] p-5"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--sh-brand-600)]">内容包详情</p>
              <h2 className="mt-1 text-lg font-bold text-[var(--sh-ink-strong)]">
                {selectedPackage.title}
              </h2>
            </div>
            <Button onClick={() => setSelectedPackage(null)} size="sm" variant="quiet">
              关闭
            </Button>
          </div>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-[var(--sh-ink-muted)]">类型</dt>
              <dd className="mt-1 font-semibold">{selectedPackage.kind}</dd>
            </div>
            <div>
              <dt className="text-[var(--sh-ink-muted)]">当前内容</dt>
              <dd className="mt-1 font-semibold">{selectedPackage.version}</dd>
            </div>
            <div>
              <dt className="text-[var(--sh-ink-muted)]">使用情况</dt>
              <dd className="mt-1 font-semibold">{selectedPackage.usage}</dd>
            </div>
          </dl>
        </section>
      ) : null}
    </div>
  );
}
