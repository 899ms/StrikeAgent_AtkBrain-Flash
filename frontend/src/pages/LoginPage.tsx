import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { animate } from "animejs";
import { api } from "../api";
import { useAuth } from "../AuthGate";
import { encryptLoginPassword } from "../authCrypto";
import { LangToggle } from "../components/LangToggle";
import { LoginRipple } from "../components/LoginRipple";
import { Spike } from "../components/Spike";
import { markShowUpdate } from "../components/UpdateModal";
import { useT } from "../i18n";

type LocState = { from?: string };

export function LoginPage() {
  const { t } = useT();
  const { me, refresh } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const from = (loc.state as LocState | null)?.from || "/";
  const cardRef = useRef<HTMLFormElement>(null);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [pendingId, setPendingId] = useState("");
  const [pem, setPem] = useState("");
  const [ticket, setTicket] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const loadPubkey = useCallback(async () => {
    const pk = await api.authPubkey();
    setPem(pk.pem);
    setTicket(pk.ticket || "");
  }, []);

  useEffect(() => {
    if (!me?.required || me.authenticated) return;
    loadPubkey().catch((e) => setErr(String(e?.message || e)));
  }, [loadPubkey, me]);

  const shake = () => {
    if (cardRef.current) {
      animate(cardRef.current, { translateX: [0, -11, 9, -6, 0], duration: 420, ease: "outQuad" });
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr("");
    try {
      if (pendingId) {
        const r = await api.authLogin({ pending_id: pendingId, totp: totp.trim(), username });
        if (r.ok) {
          await refresh();
          markShowUpdate();
          nav(from.startsWith("/login") ? "/" : from, { replace: true });
          return;
        }
        throw new Error(t("login.verifyFailed"));
      }
      if (!pem || !ticket) throw new Error(t("login.keyNotReady"));
      const cipher = await encryptLoginPassword(pem, password, ticket);
      const r = await api.authLogin({
        username: username.trim(),
        password_cipher: cipher,
        ticket,
      });
      if (r.need_totp && r.pending_id) {
        setPendingId(r.pending_id);
        setPassword("");
        return;
      }
      if (r.ok) {
        setPassword("");
        await refresh();
        markShowUpdate();
        nav(from.startsWith("/login") ? "/" : from, { replace: true });
        return;
      }
      throw new Error(t("login.verifyFailed"));
    } catch (ex: any) {
      shake();
      const extra = ex?.retryAfter ? t("login.retryAfter", { n: ex.retryAfter }) : "";
      setErr(`${ex?.message || t("login.verifyFailed")}${extra}`);
      setPendingId("");
      setTotp("");
      loadPubkey().catch(() => {});
    } finally {
      setBusy(false);
    }
  };

  if (!me) return <div className="login-boot">{t("common.loading")}</div>;
  if (!me.required || me.authenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="login-page">
      <LoginRipple />
      <form ref={cardRef} className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <Spike size={36} />
          <div>
            <p className="eyebrow">ACCESS</p>
            <h1>StrikeAgent_AtkBrain-Flash</h1>
            <p className="muted">{t("login.subtitle")}</p>
          </div>
        </div>
        {!pendingId ? (
          <>
            {me.show_default_creds ? (
              <p className="login-default-creds">
                {t("login.defaultCreds", { user: me.default_username || "admin" })}
              </p>
            ) : null}
            <label className="login-field">
              <span>{t("login.username")}</span>
              <input className="input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
            </label>
            <label className="login-field">
              <span>{t("login.password")}</span>
              <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
          </>
        ) : (
          <label className="login-field">
            <span>{t("login.totp")}</span>
            <input className="input" inputMode="numeric" autoComplete="one-time-code" value={totp} onChange={(e) => setTotp(e.target.value)} />
          </label>
        )}
        {err && <p className="error-text">{err}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? t("login.verifying") : (pendingId ? t("common.confirm") : t("login.submit"))}</button>
        <div className="login-card-foot">
          <Link className="muted" to="/about" style={{ fontSize: 13 }}>{t("login.about")}</Link>
          <LangToggle compact />
        </div>
      </form>
    </div>
  );
}
