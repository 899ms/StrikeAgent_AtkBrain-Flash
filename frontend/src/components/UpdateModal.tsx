import { useState } from "react";
import { api } from "../api";
import type { AppVersion } from "../types";
import { useT } from "../i18n";
import { Modal } from "./Modal";

export const SHOW_UPDATE_KEY = "atkbrain_show_update";

export function markShowUpdate(): void {
  try {
    sessionStorage.setItem(SHOW_UPDATE_KEY, "1");
  } catch {
    /* private mode */
  }
}

export function consumeShowUpdate(): boolean {
  try {
    if (sessionStorage.getItem(SHOW_UPDATE_KEY) !== "1") return false;
    sessionStorage.removeItem(SHOW_UPDATE_KEY);
    return true;
  } catch {
    return false;
  }
}

function fmtVer(raw?: string | null): string {
  const s = String(raw || "").trim();
  if (!s) return "—";
  return s.toLowerCase().startsWith("v") ? s : `v${s}`;
}

function splitVer(raw?: string | null): { core: string; pre: string } {
  const s = fmtVer(raw);
  const cut = s.search(/[-+]/);
  if (cut < 0) return { core: s, pre: "" };
  return { core: s.slice(0, cut), pre: s.slice(cut).replace(/^[-+]/, "") };
}

function normVer(raw?: string | null): string {
  const s = String(raw || "").trim().toLowerCase();
  return s.startsWith("v") ? s.slice(1) : s;
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitUntilUpdated(target: string): Promise<void> {
  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    await sleep(2000);
    try {
      const v = await api.version(true);
      const local = normVer(v.local);
      const want = normVer(target);
      if ((want && local === want) || v.is_latest || v.status === "latest") return;
    } catch {
      /* console restarting */
    }
  }
  throw new Error("timeout");
}

export function UpdateModal({
  ver, onClose,
}: { ver: AppVersion; onClose: () => void }) {
  const { t } = useT();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [phase, setPhase] = useState<"idle" | "applying" | "waiting">("idle");
  const target = ver.latest_tag || ver.latest || "";
  const here = splitVer(ver.local);
  const next = splitVer(ver.latest || ver.latest_tag);

  const apply = async () => {
    if (busy) return;
    setBusy(true);
    setErr("");
    setPhase("applying");
    try {
      let started = true;
      try {
        const r = await api.applyVersion();
        started = Boolean(r.started || r.already_latest);
        if (r.already_latest) {
          window.location.reload();
          return;
        }
      } catch (ex: any) {
        if (ex?.code === "hunts_live" || ex?.message === "hunts-live") {
          setErr(t("shell.updateHuntsLive"));
          setPhase("idle");
          setBusy(false);
          return;
        }
        const net = /Failed to fetch|backend|NetworkError|Load failed/i.test(String(ex?.message || ""));
        if (!net && ex?.status && ex.status !== 502 && ex.status !== 503) {
          setErr(ex?.message || t("shell.updateFailed"));
          setPhase("idle");
          setBusy(false);
          return;
        }
        started = true;
      }
      if (!started) {
        setBusy(false);
        setPhase("idle");
        return;
      }
      setPhase("waiting");
      await waitUntilUpdated(String(target));
      window.location.reload();
    } catch {
      setErr(t("shell.updateFailed"));
      setPhase("idle");
      setBusy(false);
    }
  };

  return (
    <Modal bare className="update-dialog" onClose={() => { if (!busy) onClose(); }}>
      <div className="update-modal">
        <header className="update-head">
          <p className="eyebrow">{t("shell.releaseKicker")}</p>
          <button type="button" className="update-close" onClick={onClose} disabled={busy} aria-label={t("shell.updateLater")}>✕</button>
          <h2>{t("shell.updateTitle")}</h2>
          <p className="update-lead">{t("shell.updateLead")}</p>
        </header>
        <div className="update-path" aria-hidden={false}>
          <div className="update-edition">
            <span>{t("shell.currentVersion")}</span>
            <strong>{here.core}</strong>
            {here.pre ? <small>{here.pre}</small> : null}
          </div>
          <div className="update-path-rail" aria-hidden>
            <i />
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="9" cy="9" r="8" stroke="currentColor" strokeWidth="1.2" />
              <path d="M6.5 9h5M9.5 6.5 12 9l-2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <i />
          </div>
          <div className="update-edition is-next">
            <span>{t("shell.latestVersion")}</span>
            <strong>{next.core}</strong>
            {next.pre ? <small>{next.pre}</small> : null}
          </div>
        </div>
        <section className="update-notes-panel">
          <p className="eyebrow">{t("shell.notesKicker")}</p>
          <div className="update-notes">{ver.notes?.trim() || t("shell.noNotes")}</div>
        </section>
        {err ? <p className="error-text">{err}</p> : null}
        {phase === "waiting" ? <p className="update-wait">{t("shell.updateWaiting")}</p> : null}
        <div className="update-actions">
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={onClose}>{t("shell.updateLater")}</button>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => { void apply(); }}>
            {busy ? t("shell.updating") : t("shell.updateNow")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
