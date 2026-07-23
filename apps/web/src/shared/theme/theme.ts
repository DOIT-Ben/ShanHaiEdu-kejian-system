import { useSyncExternalStore } from "react";

export const THEME_MODES = ["eye-care", "day", "night", "atelier"] as const;
export type ThemeMode = (typeof THEME_MODES)[number];

export const DEFAULT_THEME: ThemeMode = "eye-care";
export const THEME_STORAGE_KEY = "shanhaiedu.theme";

const themeChangeEvent = "shanhaiedu-theme-change";
export function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === "string" && THEME_MODES.some((mode) => mode === value);
}

export function getThemeMode(): ThemeMode {
  if (typeof document === "undefined") return DEFAULT_THEME;
  const current = document.documentElement.dataset.theme;
  return isThemeMode(current) ? current : DEFAULT_THEME;
}

function applyThemeToDocument(mode: ThemeMode) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = mode;
  document.documentElement.style.colorScheme = mode === "night" ? "dark" : "light";
  const themeColor = getComputedStyle(document.documentElement)
    .getPropertyValue("--sh-theme-color")
    .trim();
  if (themeColor) {
    document
      .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
      ?.setAttribute("content", themeColor);
  }
}

export function setThemeMode(mode: ThemeMode) {
  applyThemeToDocument(mode);
  try {
    globalThis.localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // Theme selection still works when browser storage is unavailable.
  }
  globalThis.dispatchEvent(new Event(themeChangeEvent));
}

function subscribe(listener: () => void) {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === null || (event.key === THEME_STORAGE_KEY && event.newValue === null)) {
      applyThemeToDocument(DEFAULT_THEME);
      listener();
      return;
    }
    if (event.key !== THEME_STORAGE_KEY || !isThemeMode(event.newValue)) return;
    applyThemeToDocument(event.newValue);
    listener();
  };
  globalThis.addEventListener(themeChangeEvent, listener);
  globalThis.addEventListener("storage", handleStorage);
  return () => {
    globalThis.removeEventListener(themeChangeEvent, listener);
    globalThis.removeEventListener("storage", handleStorage);
  };
}

export function useThemeMode() {
  return useSyncExternalStore(subscribe, getThemeMode, () => DEFAULT_THEME);
}
