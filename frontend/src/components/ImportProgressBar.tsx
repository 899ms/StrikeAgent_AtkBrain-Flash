import { useT } from "../i18n";

export type ImportProgress = {
  phase?: string;
  done?: number;
  total?: number;
  created?: number;
  started?: number;
  current?: string;
  message?: string;
  importing?: boolean;
  stale?: boolean;
  group_count?: number;
  hosts?: number;
  policy?: string;
  groups?: { primary: string; zone?: string; vhosts?: string[]; ports?: number[] }[];
};

export function isImportRunning(p?: ImportProgress | null): boolean {
  const phase = (p?.phase || "").toLowerCase();
  if (!p || p.stale) return false;
  return phase === "parse" || phase === "merge" || phase === "spawn" || phase === "start";
}

export function isImportPaused(p?: ImportProgress | null): boolean {
  return (p?.phase || "").toLowerCase() === "paused";
}

export function ImportProgressBar({
  progress,
  title,
  onPause,
  onResume,
  busy,
}: {
  progress?: ImportProgress | null;
  title?: string;
  onPause?: () => void;
  onResume?: () => void;
  busy?: boolean;
}) {
  const { t } = useT();
  if (!progress) return null;
  const phase = (progress.phase || "").toLowerCase();
  if (!phase || phase === "idle" || progress.stale) return null;
  const phaseKey: Record<string, string> = {
    parse: "import.parse",
    merge: "import.merge",
    spawn: "import.spawn",
    start: "import.start",
    done: "import.done",
    error: "import.error",
    idle: "import.idle",
    paused: "import.paused",
  };
  const total = Math.max(0, Number(progress.total) || 0);
  const done = Math.max(0, Number(progress.done) || 0);
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : (phase === "done" ? 100 : 8);
  const label = phaseKey[phase] ? t(phaseKey[phase]) : phase;
  const err = phase === "error";
  const paused = phase === "paused";
  const running = isImportRunning(progress);
  return (
    <div className={`import-progress${err ? " is-error" : ""}${paused ? " is-paused" : ""}`} role="status" aria-live="polite">
      <div className="import-progress-head">
        <strong>{title || label}</strong>
        <span className="mono">
          {total > 0 ? `${done}/${total} · ${pct}%` : (progress.message || label)}
        </span>
      </div>
      <div className="import-progress-track">
        <div
          className={`import-progress-fill${total <= 0 && phase !== "done" && !paused ? " is-indeterminate" : ""}`}
          style={{ width: `${Math.max(err ? 100 : 4, pct)}%` }}
        />
      </div>
      <div className="import-progress-meta muted">
        {progress.message || (progress.current ? t("import.current", { name: progress.current }) : t("import.wait"))}
        {typeof progress.created === "number" && progress.created > 0 ? t("import.created", { n: progress.created }) : ""}
        {typeof progress.started === "number" && progress.started > 0 ? t("import.started", { n: progress.started }) : ""}
        {typeof progress.group_count === "number" && progress.group_count > 0
          ? (progress.policy === "product_zone" ? t("import.groupsZone", { n: progress.group_count }) : t("import.groupsHost", { n: progress.group_count }))
          : ""}
      </div>
      {Array.isArray(progress.groups) && progress.groups.length > 0 && (
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, maxHeight: 160, overflow: "auto", fontSize: 12 }}>
          {progress.groups.slice(0, 12).map((g) => {
            const n = g.vhosts?.length || 1;
            const active = progress.current === g.primary;
            return (
              <li key={g.primary} style={{ marginBottom: 2, fontWeight: active ? 600 : 400 }}>
                {g.primary}
                {g.zone ? ` · ${g.zone}` : ""}
                {n > 1 ? t("import.domains", { n }) : ""}
                {g.ports?.length ? ` · ${g.ports.join(",")}` : ""}
                {active ? " ←" : ""}
              </li>
            );
          })}
          {progress.groups.length > 12 && (
            <li className="muted">{t("import.more", { n: progress.groups.length - 12 })}</li>
          )}
        </ul>
      )}
      {(onPause || onResume) && (running || paused) && (
        <div className="import-progress-actions">
          {running && onPause && (
            <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={onPause}>
              {busy ? t("common.processing") : t("import.pause")}
            </button>
          )}
          {paused && onResume && (
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onResume}>
              {busy ? t("common.processing") : t("import.resume")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
