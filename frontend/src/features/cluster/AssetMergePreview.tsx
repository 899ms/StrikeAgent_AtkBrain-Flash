import type { AssetPreviewResult } from "../../api";
import { useT } from "../../i18n";

const PREVIEW_CAP = 12;

export function AssetMergePreview({ data }: { data: AssetPreviewResult }) {
  const { t } = useT();
  const groups = data.groups || [];
  const extra = Math.max(0, groups.length - PREVIEW_CAP);
  const shown = groups.slice(0, PREVIEW_CAP);
  const headers = data.skipped_header || [];
  const policy = data.policy === "product_zone" ? t("merge.policySrc") : t("merge.policyRed");
  return (
    <div className="card-cream" style={{ margin: "10px 0 12px", padding: 14, fontSize: 13 }}>
      <div className="row" style={{ gap: 16, flexWrap: "wrap", marginBottom: 8 }}>
        <span>{t("merge.policy")} <b>{policy}</b></span>
        <span>{t("merge.hosts")} <b>{data.hosts}</b></span>
        <span>{t("merge.willCreate")} <b>{data.group_count}</b></span>
        {data.skipped_dup_count > 0 && <span>{t("merge.dupRows")} <b>{data.skipped_dup_count}</b></span>}
        {headers.length > 0 && <span>{t("merge.droppedHeaders")} <b>{headers.join(", ")}</b></span>}
      </div>
      {data.note && <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{data.note}</p>}
      {shown.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 18, maxHeight: 180, overflow: "auto" }}>
          {shown.map((g) => (
            <li key={g.primary} style={{ marginBottom: 4 }}>
              <b>{g.primary}</b>
              {g.zone ? <span className="muted"> · {g.zone}</span> : null}
              {g.vhosts.length > 1 ? t("import.domains", { n: g.vhosts.length }) : ""}
              {g.ports.length ? ` · ${t("merge.ports", { ports: g.ports.join(",") })}` : ""}
            </li>
          ))}
        </ul>
      )}
      {extra > 0 && <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>{t("merge.more", { n: extra })}</p>}
    </div>
  );
}
