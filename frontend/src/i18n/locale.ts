export type Locale = "zh" | "en";

export const LOCALE_KEY = "atkbrain_locale";

const listeners = new Set<() => void>();
let current: Locale = "zh";

export function normalizeLocale(raw: string | null | undefined): Locale {
  const s = String(raw || "").trim().toLowerCase().replace("_", "-");
  if (s.startsWith("en")) return "en";
  return "zh";
}

export function detectLocale(): Locale {
  try {
    const stored = localStorage.getItem(LOCALE_KEY);
    if (stored === "zh" || stored === "en") return stored;
  } catch {
    /* ignore */
  }
  try {
    const nav = String(navigator.language || "").toLowerCase();
    return nav.startsWith("zh") ? "zh" : "en";
  } catch {
    return "zh";
  }
}

export function getLocale(): Locale {
  return current;
}

export function applyDocumentLocale(locale: Locale) {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale === "en" ? "en" : "zh-CN";
  document.title = locale === "en"
    ? "StrikeAgent_AtkBrain-Flash · Red-team AI pentest platform"
    : "StrikeAgent_AtkBrain-Flash · 红队 AI 渗透平台";
}

export function setLocale(next: Locale) {
  current = next === "en" ? "en" : "zh";
  try {
    localStorage.setItem(LOCALE_KEY, current);
  } catch {
    /* ignore */
  }
  applyDocumentLocale(current);
  listeners.forEach((fn) => fn());
}

export function subscribeLocale(fn: () => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

current = detectLocale();
applyDocumentLocale(current);
