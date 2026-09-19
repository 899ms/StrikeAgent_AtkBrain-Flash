import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, type AuthMe } from "./api";
import { PasswordChangeForm } from "./components/PasswordChangeForm";
import { t } from "./i18n";

type AuthCtx = {
  me: AuthMe | null;
  refresh: () => Promise<AuthMe | null>;
  logout: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>({
  me: null,
  refresh: async () => null,
  logout: async () => {},
});

const emptyMe = (required = false): AuthMe => ({
  required,
  authenticated: false,
  username: null,
  totp_enabled: false,
  must_change_password: false,
  show_default_creds: false,
});

export function useAuth() {
  return useContext(Ctx);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<AuthMe | null>(null);

  const refresh = useCallback(async () => {
    const r = await api.authMe();
    setMe(r);
    return r;
  }, []);

  const logout = useCallback(async () => {
    await api.authLogout().catch(() => {});
    setMe((cur) => emptyMe(cur?.required ?? true));
  }, []);

  useEffect(() => {
    refresh().catch(() => setMe(emptyMe(false)));
  }, [refresh]);

  return <Ctx.Provider value={{ me, refresh, logout }}>{children}</Ctx.Provider>;
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { me, refresh } = useAuth();
  const loc = useLocation();
  if (!me) return <div className="login-boot">{t("common.loading")}</div>;
  if (me.required && !me.authenticated) {
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }
  if (me.authenticated && me.must_change_password) {
    return (
      <div className="login-page">
        <div className="login-card force-password-card">
          <p className="eyebrow">PASSWORD</p>
          <h1>{t("password.forceTitle")}</h1>
          <PasswordChangeForm
            requireOld={false}
            hint={t("password.forceHint")}
            onDone={() => { void refresh(); }}
          />
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
