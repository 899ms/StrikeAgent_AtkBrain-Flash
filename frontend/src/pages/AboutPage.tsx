import { Link } from "react-router-dom";
import { LangToggle } from "../components/LangToggle";
import { LoginRipple } from "../components/LoginRipple";
import { Spike } from "../components/Spike";
import { useT } from "../i18n";

export function ProductIntro({
  ctaTo,
  ctaLabel,
  secondaryTo,
  secondaryLabel,
}: {
  ctaTo: string;
  ctaLabel: string;
  secondaryTo?: string;
  secondaryLabel?: string;
}) {
  const { t } = useT();
  return (
    <article className="about-card">
      <div className="about-brand">
        <Spike size={40} />
        <div>
          <p className="eyebrow">{t("about.eyebrow")}</p>
          <h1>StrikeAgent_AtkBrain-Flash</h1>
        </div>
      </div>
      <p className="about-lead">{t("about.lead")}</p>
      <p>{t("about.p1")}</p>
      <p>{t("about.p2")}</p>
      <p className="muted">{t("about.triad")}</p>
      <h2>{t("about.archTitle")}</h2>
      <p>{t("about.archBody")}</p>
      <h2>{t("about.tracksTitle")}</h2>
      <ul className="about-tracks">
        <li>{t("about.trackRed")}</li>
        <li>{t("about.trackCtf")}</li>
        <li>{t("about.trackSrc")}</li>
      </ul>
      <h2>{t("about.cybenchTitle")}</h2>
      <p>{t("about.cybenchBody")}</p>
      <p className="muted">{t("about.langNote")}</p>
      <div className="about-cta">
        <Link className="btn btn-primary" to={ctaTo}>{ctaLabel}</Link>
        {secondaryTo && secondaryLabel ? (
          <Link className="btn btn-secondary" to={secondaryTo}>{secondaryLabel}</Link>
        ) : null}
      </div>
    </article>
  );
}

export function AboutPage() {
  const { t } = useT();
  return (
    <div className="login-page about-page">
      <LoginRipple />
      <div className="about-wrap">
        <div className="about-toolbar">
          <LangToggle compact />
        </div>
        <ProductIntro
          ctaTo="/login"
          ctaLabel={t("about.ctaLogin")}
          secondaryTo="/"
          secondaryLabel={t("about.ctaConsole")}
        />
      </div>
    </div>
  );
}
