import { useEffect, useState } from "react";
import { api } from "../../api";
import { colors } from "../../theme";
import { useT } from "../../i18n";

type MemoryRow = {
  id: string;
  target_fp?: string;
  version?: number;
  outcome?: string;
  rule?: string;
  chain?: string;
  do?: string[];
  avoid?: string[];
  confidence?: number;
  wins?: number;
  content?: {
    techniques?: string[];
    winning_path?: string;
    approach?: string;
    rule?: string;
    chain?: string;
    do?: string[];
    avoid?: string[];
    confidence?: number;
    wins?: number;
  };
  created_at?: number;
};

export function MemoryPanel({ projectId }: { projectId: string }) {
  const { t } = useT();
  const [episodes, setEpisodes] = useState<MemoryRow[]>([]);
  const [playbook, setPlaybook] = useState<MemoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    api.projectMemory(projectId)
      .then((data) => {
        if (!live) return;
        setEpisodes(data.episodes || []);
        setPlaybook(data.playbook || []);
      })
      .catch((e) => live && setError(String(e?.message || e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [projectId]);

  if (loading) return <p className="muted" style={{ padding: 16 }}>{t("memory.loading")}</p>;
  if (error) return <p style={{ padding: 16, color: colors.error }}>{t("memory.loadFailed", { msg: error })}</p>;
  if (!episodes.length && !playbook.length) {
    return <p className="muted" style={{ padding: 16 }}>{t("memory.emptyLong")}</p>;
  }

  return (
    <div style={{ padding: "14px 2px", display: "grid", gap: 16 }}>
      <section>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <b>{t("memory.playbookTitle")}</b>
          <span className="badge">{t("memory.count", { n: playbook.length })}</span>
        </div>
        {!playbook.length && (
          <p className="muted" style={{ fontSize: 13 }}>{t("memory.noPlaybook")}</p>
        )}
        {playbook.map((ls) => {
          const c = ls.content;
          const rule = ls.rule || c?.rule || c?.approach;
          const chain = ls.chain || c?.chain;
          const conf = ls.confidence ?? c?.confidence;
          return (
            <div key={ls.id} style={{ borderTop: "1px solid var(--hairline)", padding: "10px 0" }}>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <span className="badge badge-coral">playbook</span>
                {conf != null && (
                  <span className="muted" style={{ fontSize: 12 }}>{t("memory.conf", { n: Number(conf).toFixed(2) })}</span>
                )}
                <span className="mono muted" style={{ fontSize: 12 }}>{ls.target_fp || t("memory.generic")}</span>
              </div>
              {rule && (
                <p style={{ fontSize: 13, margin: "7px 0 0", lineHeight: 1.5 }}>{rule}</p>
              )}
              {!!(ls.do || c?.do)?.length && (
                <p className="muted" style={{ fontSize: 12, margin: "6px 0 0" }}>
                  {t("memory.prefer", { text: (ls.do || c?.do || []).join(" · ") })}
                </p>
              )}
              {!!(ls.avoid || c?.avoid)?.length && (
                <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
                  {t("memory.avoid", { text: (ls.avoid || c?.avoid || []).join(" · ") })}
                </p>
              )}
              {chain && (
                <p className="mono" style={{ fontSize: 11, lineHeight: 1.5, margin: "7px 0 0", overflowWrap: "anywhere" }}>
                  {chain}
                </p>
              )}
            </div>
          );
        })}
      </section>
      <section>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <b>{t("memory.episodes")}</b>
          <span className="badge">{t("memory.episodeCount", { n: episodes.length })}</span>
        </div>
        {!episodes.length && (
          <p className="muted" style={{ fontSize: 13 }}>{t("memory.noEpisodes")}</p>
        )}
        {episodes.map((ep) => (
          <div key={ep.id} style={{ borderTop: "1px solid var(--hairline)", padding: "10px 0" }}>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <span className="badge badge-coral">{ep.outcome || "unknown"}</span>
              <span className="mono muted" style={{ fontSize: 12 }}>{ep.target_fp || t("memory.unclassified")}</span>
              <span className="muted" style={{ fontSize: 12 }}>v{ep.version || 1}</span>
            </div>
            {!!ep.content?.techniques?.length && (
              <p className="muted" style={{ fontSize: 12, margin: "7px 0 0" }}>
                {t("memory.tech", { text: ep.content.techniques.join(" · ") })}
              </p>
            )}
            {(ep.content?.approach || ep.content?.winning_path) && (
              <p className="mono" style={{ fontSize: 11, lineHeight: 1.5, margin: "7px 0 0", overflowWrap: "anywhere" }}>
                {ep.content.approach || ep.content.winning_path}
              </p>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
