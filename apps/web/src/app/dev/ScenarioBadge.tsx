import { useSyncExternalStore } from "react";
import { FlaskConical } from "lucide-react";
import { env } from "@/shared/config/env";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/ui";

/** Mock 启动器挂载在 window 上的控制器（生产构建不存在）。 */
interface MockController {
  scenarioId: string;
  scenarios: Array<{ id: string; group: string; description: string }>;
  setScenario: (id: string) => void;
}

declare global {
  interface Window {
    __SHANHAI_MOCK__?: MockController;
  }
}

function subscribe(): () => void {
  return () => undefined;
}

/**
 * Mock 场景切换徽标（仅开发/演示环境渲染；
 * 通过 env 配置层判断运行模式，业务组件不感知）。
 */
export function ScenarioBadge() {
  const controller = useSyncExternalStore(
    subscribe,
    () => window.__SHANHAI_MOCK__,
    () => undefined,
  );
  if (env.apiMode !== "mock" || !controller) return null;

  const groups = new Map<string, MockController["scenarios"]>();
  for (const scenario of controller.scenarios) {
    const list = groups.get(scenario.group) ?? [];
    list.push(scenario);
    groups.set(scenario.group, list);
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-control border border-warning bg-warning-surface px-2.5 py-1 text-xs font-medium text-warning"
        >
          <FlaskConical className="size-3.5" aria-hidden />
          演示场景：{controller.scenarioId}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-[70vh] w-96 overflow-auto">
        <DropdownMenuLabel>切换 Mock 演示场景（将重载页面）</DropdownMenuLabel>
        {[...groups.entries()].map(([group, scenarios]) => (
          <div key={group}>
            <DropdownMenuSeparator />
            <p className="px-3 pt-2 text-xs font-semibold text-ink-muted">{group}</p>
            {scenarios.map((scenario) => (
              <DropdownMenuItem
                key={scenario.id}
                onSelect={() => controller.setScenario(scenario.id)}
                className="flex-col items-start gap-0.5"
              >
                <span className="text-sm text-ink-1">
                  {scenario.id}
                  {scenario.id === controller.scenarioId ? "（当前）" : ""}
                </span>
                <span className="text-xs text-ink-muted">{scenario.description}</span>
              </DropdownMenuItem>
            ))}
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
