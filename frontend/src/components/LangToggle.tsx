import { useT, type Locale } from "../i18n";

export function LangToggle({ compact = false, dark = false }: { compact?: boolean; dark?: boolean }) {
  const { locale, setLocale, t } = useT();
  const set = (next: Locale) => {
    if (next !== locale) setLocale(next);
  };
  return (
    <div className={`lang-toggle${dark ? " is-dark" : ""}`} role="group" aria-label={t("common.language")}>
      <button
        type="button"
        className={locale === "zh" ? "active" : ""}
        aria-pressed={locale === "zh"}
        onClick={() => set("zh")}
      >
        {t("common.langZh")}
      </button>
      <button
        type="button"
        className={locale === "en" ? "active" : ""}
        aria-pressed={locale === "en"}
        onClick={() => set("en")}
      >
        {t("common.langEn")}
      </button>
      {compact ? null : <span className="lang-toggle-hint muted">{t("common.language")}</span>}
    </div>
  );
}
