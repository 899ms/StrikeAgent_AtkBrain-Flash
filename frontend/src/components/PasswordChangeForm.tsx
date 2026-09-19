import { useState, type FormEvent } from "react";
import { api } from "../api";
import { encryptLoginPassword } from "../authCrypto";
import { useT } from "../i18n";

function policyCode(pw: string): "len" | "upper" | "lower" | "digit" | null {
  if (pw.length < 8) return "len";
  if (!/[A-Z]/.test(pw)) return "upper";
  if (!/[a-z]/.test(pw)) return "lower";
  if (!/[0-9]/.test(pw)) return "digit";
  return null;
}

type Props = {
  requireOld?: boolean;
  title?: string;
  hint?: string;
  onDone?: () => void;
};

export function PasswordChangeForm({ requireOld = true, title, hint, onDone }: Props) {
  const { t } = useT();
  const [oldPw, setOldPw] = useState("");
  const [nextPw, setNextPw] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setErr("");
    setOk("");
    if (nextPw !== again) {
      setErr(t("password.mismatch"));
      return;
    }
    const code = policyCode(nextPw);
    if (code) {
      setErr(t(`password.${code}`));
      return;
    }
    if (requireOld && !oldPw) {
      setErr(t("password.needOld"));
      return;
    }
    setBusy(true);
    try {
      const pk = await api.authPubkey();
      const ticket = pk.ticket || "";
      const new_cipher = await encryptLoginPassword(pk.pem, nextPw, ticket);
      const body: { ticket: string; new_cipher: string; old_cipher?: string } = { ticket, new_cipher };
      if (requireOld) {
        body.old_cipher = await encryptLoginPassword(pk.pem, oldPw, ticket);
      }
      await api.authPassword(body);
      setOldPw("");
      setNextPw("");
      setAgain("");
      setOk(t("password.changed"));
      onDone?.();
    } catch (ex: any) {
      const code = String(ex?.code || "");
      if (code && ["len", "upper", "lower", "digit"].includes(code)) setErr(t(`password.${code}`));
      else if (String(ex?.message || "").includes("need-old-password")) setErr(t("password.needOld"));
      else setErr(String(ex?.message || t("login.verifyFailed")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      {title ? <h3>{title}</h3> : null}
      {hint ? <p className="muted">{hint}</p> : null}
      {requireOld ? (
        <label className="login-field">
          <span>{t("password.old")}</span>
          <input className="input" type="password" autoComplete="current-password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
        </label>
      ) : null}
      <label className="login-field">
        <span>{t("password.next")}</span>
        <input className="input" type="password" autoComplete="new-password" value={nextPw} onChange={(e) => setNextPw(e.target.value)} />
      </label>
      <label className="login-field">
        <span>{t("password.again")}</span>
        <input className="input" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
      </label>
      {err ? <p className="error-text">{err}</p> : null}
      {ok ? <p className="muted">{ok}</p> : null}
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy ? t("common.saving") : t("password.submit")}
      </button>
    </form>
  );
}
