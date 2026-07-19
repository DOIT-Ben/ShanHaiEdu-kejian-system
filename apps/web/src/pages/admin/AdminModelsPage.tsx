import { CheckCircle2, KeyRound, PlugZap, Plus, Server } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { getMockDraft, saveMockDraft } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { HorizontalScrollArea } from "@/shared/ui/HorizontalScrollArea";
import { Select } from "@/shared/ui/Select";

const MODELS_DRAFT_KEY = "admin.model-services";
const primaryModelOptions = [
  "主文本模型",
  "高质量图片模型",
  "10/15 秒视频模型",
  "普通话教师声音",
  "高质量模型",
  "快速模型",
];

type ModelService = {
  capability: string;
  primary: string;
  fallback: string;
  status: string;
  latency: string;
  timeout: string;
};

type ModelsDraft = { services: ModelService[]; tested: boolean };

const defaultServices: ModelService[] = [
  {
    capability: "文本生成",
    primary: "主文本模型",
    fallback: "备用文本模型",
    status: "正常",
    latency: "2.4 秒",
    timeout: "120",
  },
  {
    capability: "教学图片",
    primary: "高质量图片模型",
    fallback: "快速图片模型",
    status: "正常",
    latency: "18 秒",
    timeout: "120",
  },
  {
    capability: "课堂视频",
    primary: "10/15 秒视频模型",
    fallback: "备用视频模型",
    status: "需关注",
    latency: "4.8 分钟",
    timeout: "300",
  },
  {
    capability: "语音合成",
    primary: "普通话教师声音",
    fallback: "通用声音",
    status: "正常",
    latency: "3.1 秒",
    timeout: "120",
  },
];

function readModelsDraft(): ModelsDraft {
  return (
    getMockDraft<ModelsDraft>(MODELS_DRAFT_KEY)?.value ?? {
      services: defaultServices,
      tested: false,
    }
  );
}

function validateConfig(config: { primary: string; timeout: string }) {
  if (!config.primary) return "请选择主模型";
  if (!/^\d+$/.test(config.timeout)) return "超时时间须为 1 到 600 秒的整数";
  const timeout = Number(config.timeout);
  return timeout >= 1 && timeout <= 600 ? "" : "超时时间须为 1 到 600 秒的整数";
}

export function AdminModelsPage() {
  const [mobileLayout, setMobileLayout] = useState(
    () => typeof globalThis.matchMedia === "function" && matchMedia("(max-width: 767px)").matches,
  );
  const [draft, setDraft] = useState(readModelsDraft);
  const [selectedCapability, setSelectedCapability] = useState<string | null>(null);
  const [config, setConfig] = useState({ primary: "", timeout: "120" });
  const [message, setMessage] = useState("");
  const configHeadingRef = useRef<HTMLHeadingElement>(null);
  const configSectionRef = useRef<HTMLElement>(null);
  const save = (next: ModelsDraft) => {
    saveMockDraft(MODELS_DRAFT_KEY, next);
    setDraft(next);
  };
  const addService = () => {
    const capability = `新能力服务 ${String(draft.services.length + 1)}`;
    const service: ModelService = {
      capability,
      primary: "",
      fallback: "待选择",
      status: "待配置",
      latency: "--",
      timeout: "120",
    };
    save({ ...draft, services: [...draft.services, service] });
    setSelectedCapability(capability);
    setConfig({ primary: service.primary, timeout: service.timeout });
    setMessage("新模型服务已加入列表");
  };
  const openConfig = (service: ModelService) => {
    setSelectedCapability(service.capability);
    setConfig({ primary: service.primary, timeout: service.timeout });
    setMessage(`已打开${service.capability}配置`);
  };
  const selectedService = draft.services.find(
    (service) => service.capability === selectedCapability,
  );
  const configError = selectedService ? validateConfig(config) : "";
  useEffect(() => {
    if (!selectedService) return;
    configSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    configHeadingRef.current?.focus({ preventScroll: true });
  }, [selectedService]);
  useEffect(() => {
    if (typeof globalThis.matchMedia !== "function") return;
    const query = matchMedia("(max-width: 767px)");
    const update = () => setMobileLayout(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return (
    <div className="p-5 md:p-6">
      <FocusPageHeader
        action={
          <Button onClick={addService}>
            <Plus aria-hidden="true" />
            添加模型服务
          </Button>
        }
        description="业务节点引用逻辑能力；管理员配置主模型、备用模型、并发、超时和费用。测试请求不会进入教师项目。"
        title="模型服务"
      />
      <div className="mt-5 grid grid-cols-3 gap-2 sm:mt-7 sm:gap-4">
        <div className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 sm:p-5">
          <Server aria-hidden="true" className="size-4 text-[var(--sh-brand-600)] sm:size-5" />
          <p className="mt-2 text-xl font-bold text-[var(--sh-ink-strong)] sm:mt-3 sm:text-2xl">
            {draft.services.length}
          </p>
          <p className="text-[11px] leading-4 text-[var(--sh-ink-muted)] sm:text-sm">
            已配置逻辑能力
          </p>
        </div>
        <div className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 sm:p-5">
          <PlugZap aria-hidden="true" className="size-4 text-[var(--sh-success)] sm:size-5" />
          <p className="mt-2 text-xl font-bold text-[var(--sh-ink-strong)] sm:mt-3 sm:text-2xl">
            7 / 8
          </p>
          <p className="text-[11px] leading-4 text-[var(--sh-ink-muted)] sm:text-sm">连接正常</p>
        </div>
        <div className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 sm:p-5">
          <KeyRound aria-hidden="true" className="size-4 text-[var(--sh-warning)] sm:size-5" />
          <p className="mt-2 text-xl font-bold text-[var(--sh-ink-strong)] sm:mt-3 sm:text-2xl">
            8
          </p>
          <p className="text-[11px] leading-4 text-[var(--sh-ink-muted)] sm:text-sm">
            <span className="sm:hidden">密钥状态</span>
            <span className="hidden sm:inline">密钥已配置，仅显示状态</span>
          </p>
        </div>
      </div>
      {mobileLayout ? (
        <div aria-label="模型服务列表" className="mt-4 grid gap-3">
          {draft.services.map((service) => (
            <article
              className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4"
              key={service.capability}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-semibold text-[var(--sh-ink-strong)]">
                    {service.capability}
                  </h2>
                  <p className="mt-1 truncate text-sm text-[var(--sh-ink-muted)]">
                    {service.primary}
                  </p>
                </div>
                <span
                  className={`shrink-0 text-xs font-semibold ${service.status === "正常" ? "text-[var(--sh-success)]" : "text-[var(--sh-warning)]"}`}
                >
                  {service.status}
                </span>
              </div>
              <div className="mt-3 flex items-end justify-between gap-3 border-t border-[var(--sh-line-subtle)] pt-3">
                <div className="min-w-0 text-xs text-[var(--sh-ink-muted)]">
                  <p className="truncate">备用：{service.fallback}</p>
                  <p className="mt-1">近期响应：{service.latency}</p>
                </div>
                <Button
                  aria-label={`配置${service.capability}`}
                  onClick={() => openConfig(service)}
                  size="sm"
                  variant="secondary"
                >
                  配置
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <HorizontalScrollArea
          ariaLabel="模型服务列表"
          className="mt-6"
          hintTestId="admin-models-table-scroll-next"
          viewportClassName="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"
        >
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-[var(--sh-surface-soft)] text-xs text-[var(--sh-ink-muted)]">
              <tr>
                <th className="px-5 py-3">逻辑能力</th>
                <th className="px-5 py-3">主模型</th>
                <th className="px-5 py-3">备用模型</th>
                <th className="px-5 py-3">连接</th>
                <th className="px-5 py-3">近期响应</th>
                <th className="px-5 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--sh-line-subtle)]">
              {draft.services.map((service) => (
                <tr key={service.capability}>
                  <td className="px-5 py-4 font-semibold text-[var(--sh-ink-strong)]">
                    {service.capability}
                  </td>
                  <td className="px-5 py-4">{service.primary}</td>
                  <td className="px-5 py-4 text-[var(--sh-ink-muted)]">{service.fallback}</td>
                  <td
                    className={`px-5 py-4 font-semibold ${service.status === "正常" ? "text-[var(--sh-success)]" : "text-[var(--sh-warning)]"}`}
                  >
                    {service.status}
                  </td>
                  <td className="px-5 py-4">{service.latency}</td>
                  <td className="px-5 py-4">
                    <button
                      className="font-semibold text-[var(--sh-brand-600)]"
                      onClick={() => openConfig(service)}
                      type="button"
                    >
                      配置
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </HorizontalScrollArea>
      )}
      {selectedService ? (
        <section
          className="mt-5 rounded-[var(--sh-radius-md)] border border-[var(--sh-brand-100)] bg-[var(--sh-surface-elevated)] p-5"
          ref={configSectionRef}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--sh-brand-600)]">服务配置</p>
              <h2
                className="mt-1 text-lg font-bold text-[var(--sh-ink-strong)] outline-none"
                ref={configHeadingRef}
                tabIndex={-1}
              >
                正在配置：{selectedService.capability}
              </h2>
            </div>
            <Button onClick={() => setSelectedCapability(null)} size="sm" variant="quiet">
              关闭
            </Button>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-semibold">
              主模型
              <Select
                ariaLabel="主模型"
                className="mt-2 w-full font-normal"
                onValueChange={(primary) => setConfig({ ...config, primary })}
                options={primaryModelOptions.map((model) => ({ label: model, value: model }))}
                placeholder="请选择主模型"
                value={config.primary}
              />
            </label>
            <label className="text-sm font-semibold">
              超时时间
              <input
                aria-label="超时时间"
                className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3 font-normal"
                inputMode="numeric"
                max="600"
                min="1"
                onChange={(event) => setConfig({ ...config, timeout: event.target.value })}
                value={config.timeout}
              />
            </label>
          </div>
          {configError ? (
            <p className="mt-3 text-sm font-semibold text-[var(--sh-danger)]" role="alert">
              {configError}
            </p>
          ) : null}
          <Button
            className="mt-4"
            disabled={Boolean(configError)}
            onClick={() => {
              if (configError) return;
              const services = draft.services.map((service) =>
                service.capability === selectedService.capability
                  ? { ...service, primary: config.primary, timeout: config.timeout, status: "正常" }
                  : service,
              );
              save({ ...draft, services });
              setMessage(`${selectedService.capability}配置已保存`);
            }}
            size="sm"
          >
            保存配置
          </Button>
        </section>
      ) : null}
      <div className="mt-6 flex flex-wrap items-center gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">连接测试</h2>
          <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
            使用脱敏样例检查服务可用性、响应格式和超时。
          </p>
        </div>
        {draft.tested ? (
          <span className="flex items-center gap-2 text-sm font-semibold text-[var(--sh-success)]">
            <CheckCircle2 aria-hidden="true" className="size-4" />
            测试通过
          </span>
        ) : null}
        <Button
          onClick={() => {
            save({ ...draft, tested: true });
            setMessage("连接测试通过");
          }}
          variant="secondary"
        >
          运行连接测试
        </Button>
      </div>
      {message ? (
        <p aria-live="polite" className="mt-3 text-sm font-semibold text-[var(--sh-brand-700)]">
          {message}
        </p>
      ) : null}
    </div>
  );
}
