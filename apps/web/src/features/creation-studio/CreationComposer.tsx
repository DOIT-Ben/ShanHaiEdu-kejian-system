import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUp, ImagePlus, LoaderCircle, Settings2, X } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { CreationParameterBar } from "@/features/creation-studio/CreationParameterBar";
import type {
  CreationSettings,
  CreationStage,
  StudioConfig,
  StudioType,
} from "@/features/creation-studio/model";
import { getCreationSettingsSummary } from "@/features/creation-studio/model";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

function generationLabel(type: StudioType, stage: CreationStage, primaryLabel: string) {
  if (stage === "draft") return primaryLabel;
  if (stage === "running") return "正在创作";
  return type === "image" ? "按新要求再画一组" : "按新要求再做一组";
}

export function CreationComposer({
  advancedOpen,
  advancedPanel,
  config,
  description,
  descriptionLabel,
  onAdvancedOpenChange,
  onDescriptionChange,
  onGenerate,
  onPromptReview,
  onSettingsChange,
  settings,
  stage,
  type,
}: {
  advancedOpen: boolean;
  advancedPanel: ReactNode;
  config: StudioConfig;
  description: string;
  descriptionLabel: string;
  onAdvancedOpenChange: (open: boolean) => void;
  onDescriptionChange: (description: string) => void;
  onGenerate: () => void;
  onPromptReview: () => void;
  onSettingsChange: (settings: Partial<CreationSettings>) => void;
  settings: CreationSettings;
  stage: CreationStage;
  type: StudioType;
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const reduceMotion = useReducedMotion();
  const referenceInputRef = useRef<HTMLInputElement>(null);
  const settingsPanelRef = useRef<HTMLDivElement>(null);
  const settingsTriggerRef = useRef<HTMLButtonElement>(null);
  const running = stage === "running";
  const inputLabel = stage === "draft" ? descriptionLabel : "创作要求";
  const generateLabel = generationLabel(type, stage, config.primaryLabel);
  const canGenerate = !running && description.trim().length > 0;
  const settingsSummary = getCreationSettingsSummary(type, settings);

  const referenceButton = (className?: string) => (
    <Button
      aria-label="添加参考图"
      className={className ?? "min-w-0 max-w-[min(48vw,220px)]"}
      disabled={running}
      onClick={() => referenceInputRef.current?.click()}
      size="sm"
      variant="secondary"
    >
      <ImagePlus aria-hidden="true" />
      <span className="truncate">{settings.referenceName || "参考图"}</span>
    </Button>
  );

  useEffect(() => {
    if (!settingsOpen) return;
    const frame = window.requestAnimationFrame(() => {
      settingsPanelRef.current
        ?.querySelector<HTMLButtonElement>('[role="combobox"]')
        ?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [settingsOpen]);

  useEffect(() => {
    if (!settingsOpen && !advancedOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setSettingsOpen(false);
      onAdvancedOpenChange(false);
      window.requestAnimationFrame(() => settingsTriggerRef.current?.focus());
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [advancedOpen, onAdvancedOpenChange, settingsOpen]);

  const toggleSettings = () => {
    onAdvancedOpenChange(false);
    setSettingsOpen((value) => !value);
  };

  const openAdvanced = () => {
    setSettingsOpen(false);
    onAdvancedOpenChange(true);
  };

  const closeAdvanced = () => {
    onAdvancedOpenChange(false);
    window.requestAnimationFrame(() => settingsTriggerRef.current?.focus());
  };

  const openPromptReview = () => {
    setSettingsOpen(false);
    onAdvancedOpenChange(false);
    onPromptReview();
  };

  const generate = () => {
    setSettingsOpen(false);
    onAdvancedOpenChange(false);
    onGenerate();
  };

  return (
    <section
      aria-label="创作输入区"
      className="relative z-30 shrink-0 bg-[var(--sh-surface-canvas)] px-3 pb-[calc(8px+env(safe-area-inset-bottom))] pt-1.5"
      data-testid="creation-composer"
    >
      <AnimatePresence initial={false} mode="wait">
        {advancedOpen ? (
          <motion.div
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="absolute bottom-[calc(100%-8px)] left-1/2 z-40 max-h-[min(52vh,460px)] w-[min(1040px,calc(100vw-24px))] -translate-x-1/2 overflow-y-auto rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-modal)]"
            exit={reduceMotion ? undefined : { opacity: 0, scale: 0.99, y: 4 }}
            id="creation-advanced-panel"
            initial={reduceMotion ? false : { opacity: 0, scale: 0.99, y: 6 }}
            key="advanced"
            transition={{ duration: reduceMotion ? 0 : 0.14, ease: [0.2, 0, 0, 1] }}
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="font-semibold text-[var(--sh-ink-strong)]">画面细节</p>
              <IconButton label="关闭画面细节" onClick={closeAdvanced}>
                <X aria-hidden="true" />
              </IconButton>
            </div>
            {advancedPanel}
          </motion.div>
        ) : settingsOpen ? (
          <motion.div
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="absolute bottom-[calc(100%-8px)] left-1/2 z-40 max-h-[min(52vh,360px)] w-[min(760px,calc(100vw-24px))] -translate-x-1/2 overflow-y-auto"
            exit={reduceMotion ? undefined : { opacity: 0, scale: 0.99, y: 4 }}
            id="creation-settings-panel"
            initial={reduceMotion ? false : { opacity: 0, scale: 0.99, y: 6 }}
            key="settings"
            ref={settingsPanelRef}
            transition={{ duration: reduceMotion ? 0 : 0.14, ease: [0.2, 0, 0, 1] }}
          >
            <CreationParameterBar
              advancedOpen={advancedOpen}
              disabled={running}
              onAdvancedOpenChange={(open) => {
                if (open) openAdvanced();
              }}
              onPromptReview={openPromptReview}
              referenceAction={referenceButton("max-w-full")}
              onSettingsChange={onSettingsChange}
              settings={settings}
              type={type}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div
        className="relative mx-auto max-w-[1040px] rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)]/96 p-2.5 shadow-[var(--sh-shadow-modal)] backdrop-blur-xl transition-[border-color,box-shadow] focus-within:border-[var(--sh-brand-300)] focus-within:shadow-[var(--sh-shadow-focus)]"
        data-testid="creation-composer-panel"
      >
        <label className="block min-w-0">
          <span className="sr-only">{inputLabel}</span>
          <textarea
            aria-keyshortcuts="Enter"
            aria-label={inputLabel}
            className="sh-creation-prompt min-h-20 max-h-32 w-full resize-none bg-transparent px-2 py-1.5 text-sm leading-6 text-[var(--sh-ink-default)] outline-none placeholder:text-[var(--sh-ink-faint)] disabled:cursor-wait disabled:opacity-65 sm:min-h-14 sm:max-h-24"
            disabled={running}
            onChange={(event) => onDescriptionChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
                return;
              }
              event.preventDefault();
              if (canGenerate) generate();
            }}
            placeholder="描述画面、动作、风格或希望调整的地方……"
            value={description}
          />
        </label>

        <div className="mt-2 flex min-w-0 items-center gap-2">
          <input
            accept="image/*"
            aria-hidden="true"
            className="sr-only"
            data-testid="reference-image-input"
            disabled={running}
            onChange={(event) =>
              onSettingsChange({ referenceName: event.target.files?.[0]?.name ?? "" })
            }
            ref={referenceInputRef}
            tabIndex={-1}
            type="file"
          />
          <div className="hidden sm:block">{referenceButton()}</div>
          <Button
            aria-controls="creation-settings-panel"
            aria-expanded={settingsOpen}
            aria-label="创作设置"
            className="min-w-0 flex-1 justify-start sm:flex-none sm:justify-center"
            disabled={running}
            onClick={toggleSettings}
            ref={settingsTriggerRef}
            size="sm"
            title={settingsSummary}
            variant="secondary"
          >
            <Settings2 aria-hidden="true" />
            <span className="hidden sm:inline">创作设置</span>
            <span className="min-w-0 truncate sm:hidden">{settingsSummary}</span>
          </Button>

          <IconButton
            aria-keyshortcuts="Enter"
            className="ml-auto size-11 rounded-full sm:size-10 [&_svg]:size-4"
            disabled={!canGenerate}
            label={generateLabel}
            onClick={generate}
            variant="primary"
          >
            {running ? (
              <LoaderCircle
                aria-hidden="true"
                className="animate-spin motion-reduce:animate-none"
              />
            ) : (
              <ArrowUp aria-hidden="true" />
            )}
          </IconButton>
        </div>
      </div>
    </section>
  );
}
