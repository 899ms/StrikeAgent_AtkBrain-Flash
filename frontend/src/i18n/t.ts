import { messages } from "./messages";
import { getLocale, type Locale } from "./locale";

export type Vars = Record<string, string | number>;

function lookup(locale: Locale, key: string): string | undefined {
  const row = messages[key];
  if (!row) return undefined;
  return row[locale] || row.zh;
}

export function interpolate(s: string, vars?: Vars): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] == null ? `{${k}}` : String(vars[k])));
}

export function t(key: string, vars?: Vars, fallback?: string): string {
  const locale = getLocale();
  const raw = lookup(locale, key) ?? lookup("zh", key) ?? fallback ?? key;
  return interpolate(raw, vars);
}
