import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, Leaf, Moon, Palette, Sun } from "lucide-react";
import type { ComponentType } from "react";
import { cn } from "@/shared/lib/cn";
import {
  isThemeMode,
  setThemeMode,
  THEME_MODES,
  type ThemeMode,
  useThemeMode,
} from "@/shared/theme/theme";

type ThemeOption = {
  icon: ComponentType<{ "aria-hidden"?: boolean; className?: string }>;
  label: string;
  mode: ThemeMode;
};

const defaultThemeOption = {
  icon: Leaf,
  label: "护眼",
  mode: "eye-care",
} satisfies ThemeOption;

const themeOptionDetails: Record<ThemeMode, Omit<ThemeOption, "mode">> = {
  "eye-care": defaultThemeOption,
  day: { icon: Sun, label: "白天" },
  night: { icon: Moon, label: "黑夜" },
};

const themeOptions: ThemeOption[] = THEME_MODES.map((mode) => ({
  ...themeOptionDetails[mode],
  mode,
}));

function getThemeOption(mode: ThemeMode) {
  return themeOptions.find((option) => option.mode === mode) ?? defaultThemeOption;
}

function ThemeRadioItems({ current }: { current: ThemeMode }) {
  return (
    <DropdownMenu.RadioGroup
      onValueChange={(value) => {
        if (isThemeMode(value)) setThemeMode(value);
      }}
      value={current}
    >
      {themeOptions.map(({ icon: Icon, label, mode }) => (
        <DropdownMenu.RadioItem
          className="flex min-h-10 cursor-pointer items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 text-sm font-medium outline-none data-[highlighted]:bg-[var(--sh-surface-soft)] data-[highlighted]:text-[var(--sh-brand-700)]"
          key={mode}
          value={mode}
        >
          <Icon aria-hidden={true} className="size-4" />
          <span className="flex-1">{label}模式</span>
          <DropdownMenu.ItemIndicator>
            <Check aria-hidden={true} className="size-4 text-[var(--sh-brand-700)]" />
          </DropdownMenu.ItemIndicator>
        </DropdownMenu.RadioItem>
      ))}
    </DropdownMenu.RadioGroup>
  );
}

export function ThemeSwitcher({
  className = "",
  showLabel = false,
}: {
  className?: string;
  showLabel?: boolean;
}) {
  const current = useThemeMode();
  const currentOption = getThemeOption(current);
  const CurrentIcon = currentOption.icon;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          aria-label={`切换主题，当前${currentOption.label}模式`}
          className={cn(
            "inline-flex h-10 min-w-10 shrink-0 items-center justify-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] transition-colors hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-brand-700)] focus-visible:text-[var(--sh-brand-700)]",
            showLabel && "gap-2 px-3",
            className,
          )}
          title={`当前${currentOption.label}模式`}
          type="button"
        >
          <CurrentIcon aria-hidden={true} className="size-[18px]" />
          {showLabel ? <span className="text-sm font-medium">{currentOption.label}</span> : null}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          aria-label="选择界面主题"
          className="z-[80] min-w-44 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-1.5 text-[var(--sh-ink-default)] shadow-[var(--sh-shadow-floating)]"
          sideOffset={8}
        >
          <ThemeRadioItems current={current} />
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function ThemeMenuItems() {
  const current = useThemeMode();
  const currentOption = getThemeOption(current);
  return (
    <>
      <DropdownMenu.Separator className="my-1 h-px bg-[var(--sh-line-subtle)]" />
      <DropdownMenu.Label className="flex items-center gap-2 px-3 py-2 text-xs text-[var(--sh-ink-muted)]">
        <Palette aria-hidden="true" className="size-4 text-[var(--sh-ink-muted)]" />
        <span className="flex-1">界面主题</span>
        <span>{currentOption.label}</span>
      </DropdownMenu.Label>
      <ThemeRadioItems current={current} />
      <DropdownMenu.Separator className="my-1 h-px bg-[var(--sh-line-subtle)]" />
    </>
  );
}
