import { useEffect, useState } from "react";
import { api } from "../api";

export function SettingsPage() {
  const [message, setMessage] = useState("");
  const [custom, setCustom] = useState("");
  const [backup, setBackup] = useState("");
  const [proxy, setProxy] = useState<any>(null);
  const [yakit, setYakit] = useState<any>(null);
  useEffect(() => {
    let first = true;
    let yakitFirst = true;
    const load = () => {
      api.getProxyPool().then((r) => {
        setProxy(r);
        if (first) {
          setCustom(String(r?.custom_text || ""));
          first = false;
        }
      }).catch(() => {});
      api.yakitStatus().then((r) => {
        setYakit(r);
        if (yakitFirst) {
          setBackup(String(r?.backup_text || ""));
          yakitFirst = false;
        }
      }).catch(() => {});
    };
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);

  const savePool = async () => {
    setMessage("");
    try {
      const r = await api.saveProxyPool(custom);
      setProxy(r);
      setMessage("自建代理池已保存");
    } catch (e: any) {
      setMessage(String(e?.message || e));
    }
  };

  const toggleYakit = async () => {
    setMessage("");
    try {
      const r = await api.setYakitEnabled(!yakit?.enabled);
      setYakit(r);
    } catch (e: any) {
      setMessage(String(e?.message || e));
    }
  };

  const saveBackup = async () => {
    setMessage("");
    try {
      const r = await api.saveYakitBackup(backup);
      setYakit(r);
      setMessage("Yakit 备用下游已保存");
    } catch (e: any) {
      setMessage(String(e?.message || e));
    }
  };

  const downloadCert = async () => {
    setMessage("");
    try {
      const r = await api.downloadYakitCert();
      setYakit(r);
      setMessage("MITM 证书已保存");
    } catch (e: any) {
      setMessage(String(e?.message || e));
    }
  };

  return (
    <div className="page-container settings-page">
      <header className="page-heading">
        <p className="eyebrow">SYSTEM</p>
        <h1>设置</h1>
        <p>出口代理池与 Yakit MITM。</p>
      </header>
      {message && <p className={/失败|Error|error/i.test(message) ? "error-text" : "muted"}>{message}</p>}
      <div className="settings-grid">
        <section className="card-cream" style={{ gridColumn: "1 / -1" }}>
          <h3>出口代理池</h3>
          <p className="muted">红队/SRC 打目标时必须走代理，无存活节点则拒绝出网，不会回落真实 IP。CTF 始终直连。一行一条，支持 <span className="mono">http://ip:port</span>、<span className="mono">socks5://ip:port</span> 或 <span className="mono">ip:port</span>。</p>
          <dl className="settings-list">
            <dt>开关</dt><dd>{proxy?.enabled ? "开" : "关"}（顶栏切换）</dd>
            <dt>存活</dt><dd>{proxy?.live ?? 0}</dd>
            <dt>最近出口 IP</dt><dd className="mono">{proxy?.exit_ip || "-"}</dd>
            {proxy?.error ? <><dt>状态</dt><dd className="error-text">{proxy.error}</dd></> : null}
          </dl>
          <textarea
            className="input"
            style={{ width: "100%", minHeight: 140, marginTop: 14, fontFamily: "var(--font-mono)", fontSize: 12 }}
            placeholder={"http://203.0.113.10:8080\nsocks5://198.51.100.2:1080"}
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
          />
          <div className="row" style={{ gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" type="button" onClick={() => { void savePool(); }}>保存自建池</button>
          </div>
        </section>
        <section className="card-cream" style={{ gridColumn: "1 / -1" }}>
          <h3>Yakit</h3>
          <p className="muted">红队/SRC 打开后从者 HTTP 走本机 MITM（默认 127.0.0.1:8084），下游写入出口池；池子连不上时用下面的备用节点。出口 IP 必须验收通过才放行，不会回落本机。CTF 默认不抓包。证书异常时请下载 CA。</p>
          <dl className="settings-list">
            <dt>开关</dt>
            <dd>
              <button
                type="button"
                className={`proxy-switch${yakit?.enabled ? " is-on" : ""}`}
                aria-pressed={!!yakit?.enabled}
                onClick={() => { void toggleYakit(); }}
              >
                <span className="proxy-switch-knob" />
              </button>
              <span style={{ marginLeft: 8 }}>{yakit?.enabled ? "开" : "关"}</span>
            </dd>
            <dt>引擎</dt>
            <dd>
              <span className="pulse-dot" style={{ background: yakit?.engine?.ready ? "var(--success)" : "var(--error)", marginRight: 8 }} />
              {yakit?.engine?.ready ? "Yakit 就绪" : "Yakit 未就绪"}
              <span className="mono table-sub" style={{ marginLeft: 8 }}>{yakit?.engine?.url || "-"}</span>
            </dd>
            <dt>证书</dt>
            <dd>
              <span className="pulse-dot" style={{ background: yakit?.cert?.ready ? "var(--success)" : "var(--error)", marginRight: 8 }} />
              {yakit?.cert?.ready ? "证书就绪" : "证书异常"}
            </dd>
            <dt>指纹</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{yakit?.cert?.fingerprint || "-"}</dd>
            <dt>过期</dt><dd className="mono">{yakit?.cert?.expires_at || "-"}</dd>
            <dt>MITM</dt>
            <dd className="mono">{yakit?.mitm?.host || "127.0.0.1"}:{yakit?.mitm?.port || 8084} {yakit?.mitm?.listening ? "监听中" : "未监听"}</dd>
            <dt>下游</dt><dd className="mono">{yakit?.mitm?.downstream || "（空）"}</dd>
            <dt>验收出口</dt>
            <dd className="mono">
              {yakit?.mitm?.verified ? (yakit?.mitm?.exit_ip || "已验收") : "未验收"}
            </dd>
            <dt>MCP 工具</dt>
            <dd>{yakit?.tools_count ?? 0}{yakit?.oob_ready ? " · DNS/反连已导出" : ""}</dd>
            {yakit?.engine?.error || yakit?.cert?.error || yakit?.error ? (
              <>
                <dt>状态</dt>
                <dd className="error-text">{yakit?.error || yakit?.engine?.error || yakit?.cert?.error}</dd>
              </>
            ) : null}
          </dl>
          <textarea
            className="input"
            style={{ width: "100%", minHeight: 88, marginTop: 14, fontFamily: "var(--font-mono)", fontSize: 12 }}
            placeholder={"备用下游（池子失效时用）\nhttp://203.0.113.10:8080"}
            value={backup}
            onChange={(e) => setBackup(e.target.value)}
          />
          <div className="row" style={{ gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary btn-sm" type="button" onClick={() => { void saveBackup(); }}>保存备用下游</button>
            <button className="btn btn-secondary btn-sm" type="button" onClick={() => { void downloadCert(); }}>下载 MITM 证书</button>
          </div>
        </section>
      </div>
    </div>
  );
}
