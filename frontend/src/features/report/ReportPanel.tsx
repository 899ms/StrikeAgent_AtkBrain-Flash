import { useEffect, useState } from "react";
import { api } from "../../api";
import { ReportExportControls } from "./ExportReport";
import { useT } from "../../i18n";

export function ReportPanel({ projectId }: { projectId: string }) {
  const { t } = useT();
  const [runs, setRuns] = useState<any[]>([]);
  useEffect(() => {
    api.runs(projectId).then(setRuns).catch(() => {});
  }, [projectId]);

  return (
    <div className="scroll-y" style={{ maxHeight: 520 }}>
      <div className="card-cream" style={{ padding: 16, marginBottom: 14 }}>
        <b style={{ fontSize: 15 }}>{t("report.panelTitle")}</b>
        <p className="muted" style={{ fontSize: 13, margin: "6px 0 12px" }}>
          {t("report.panelHint")}
        </p>
        <ReportExportControls projectId={projectId} />
      </div>

      <b style={{ fontSize: 14 }}>{t("report.runs")}</b>
      {runs.length === 0 && <p className="muted" style={{ fontSize: 13 }}>{t("report.noRuns")}</p>}
      {runs.map((r) => (
        <div key={r.id} className="card-cream" style={{ padding: 12, marginTop: 8 }}>
          <div className="spread">
            <span className="badge badge-pill">{r.status}</span>
            {r.goal_reached ? <span className="badge badge-coral">GETSHELL</span> : null}
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{t("report.turns", { n: r.turns })} · {r.summary ? r.summary.slice(0, 160) : "—"}</div>
        </div>
      ))}
    </div>
  );
}
