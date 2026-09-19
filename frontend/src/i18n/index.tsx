import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getLocale, setLocale, subscribeLocale, type Locale } from "./locale";
import { t as tRaw, interpolate, type Vars } from "./t";

export type { Locale, Vars };
export { getLocale, setLocale, tRaw as tStatic, interpolate };

type Ctx = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, vars?: Vars, fallback?: string) => string;
};

const LocaleCtx = createContext<Ctx>({
  locale: "zh",
  setLocale,
  t: tRaw,
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLoc] = useState<Locale>(() => getLocale());
  useEffect(() => subscribeLocale(() => setLoc(getLocale())), []);
  const value = useMemo<Ctx>(() => ({
    locale,
    setLocale,
    t: tRaw,
  }), [locale]);
  return <LocaleCtx.Provider value={value}>{children}</LocaleCtx.Provider>;
}

export function useT() {
  return useContext(LocaleCtx);
}

export function t(key: string, vars?: Vars, fallback?: string): string {
  return tRaw(key, vars, fallback);
}
