import type { RTEvent } from "../../types";
import { t, useT } from "../../i18n";

function stallLabel(stall: string): string {
  const key: Record<string, string> = {
    none: "sup.none",
    infra: "sup.infra",
    method: "sup.method",
    chain: "sup.chain",
    postex: "sup.postex",
  };
  return key[stall] ? t(key[stall]) : stall;
}

function kindLabel(kind: string): string {
  const key: Record<string, string> = {
    plan: "sup.kindPlan",
    error: "sup.kindError",
    empty: "sup.kindEmpty",
    hold: "sup.kindHold",
    runtime_review: "sup.kindReview",
  };
  return key[kind] ? t(key[kind]) : t("sup.kindGeneric");
}

/** 御主栏只展示失败记录与模型生成的内容，不展示 skip/probe 等机械条目。 */
const VISIBLE_KINDS = new Set(["error", "empty", "plan", "hold", "runtime_review"]);

type SupervisorRow = {
  key: string;
  ts: number;
  kind: string;
  title: string;
  diagnosis?: string;
  body?: string;
  stall?: string;
  quality?: string;
  pivot?: number;
  turn?: number;
  rebind?: boolean;
  tags?: { label: string; items: string[] }[];
};

function chips(labelKey: string, items: unknown): { label: string; items: string[] } | null {
  if (!Array.isArray(items) || !items.length) return null;
  const out = items.map((x) => String(x || "").trim()).filter(Boolean);
  return out.length ? { label: labelKey, items: out } : null;
}

function fromSupervisorEvent(ev: RTEvent): SupervisorRow | null {
  const p = ev.payload || {};
  const kind = String(p.kind || "plan");
  if (!VISIBLE_KINDS.has(kind)) return null;
  const pivot = Number(p.pivot) || 0;
  const turn = Number(p.turn) || 0;
  const title =
    kind === "error"
      ? t("sup.callFailed")
      : kind === "empty"
      ? t("sup.emptyPlan")
      : kind === "hold"
      ? (
          String(p.reason || "") === "binding_ignored"
            ? (turn ? t("sup.rebindTurn", { n: turn }) : t("sup.rebind"))
            : (turn ? t("sup.holdTurn", { n: turn }) : t("sup.hold"))
        )
      : kind === "runtime_review"
      ? (
          (turn ? t("sup.reviewTurn", { n: turn }) : t("sup.review"))
          + (p.continue === false ? t("sup.pause") : t("sup.continue"))
        )
      : turn
      ? t("sup.planTurn", { n: turn })
      : pivot
      ? t("sup.planN", { n: pivot })
      : t("sup.plan");
  const tags = [
    chips("sup.chipIntent", p.must_intents),
    chips("sup.chipDelegate", p.subagents),
    chips("sup.chipTactics", p.prefer_tactics),
    chips("sup.chipDefer", p.defer_families),
    chips("sup.chipBan", p.ban_repeats),
  ].filter(Boolean) as { label: string; items: string[] }[];
  const body = p.next_plan || (kind === "error" ? String(p.error || "") : "") || "";
  const diagnosis = p.diagnosis || (kind === "error" ? p.error : "") || "";
  if (kind !== "error" && kind !== "empty" && !String(body || diagnosis).trim()) return null;
  return {
    key: String(ev.id ?? `sup-${ev.ts}`),
    ts: ev.ts,
    kind,
    title,
    diagnosis,
    body,
    stall: kind === "error" ? "" : p.stall || "",
    quality: kind === "error" ? "" : p.quality || "",
    pivot,
    turn: Number(p.turn) || 0,
    rebind: kind !== "error" && !!p.rebind_entry,
    tags,
  };
}

function fromLegacy(ev: RTEvent): SupervisorRow | null {
  const p = ev.payload || {};
  if (ev.type === "steer") {
    const src = String(p.source || p.from || "");
    const content = String(p.content || "");
    if (/换路兜底|机械模板/.test(content)) return null;
    if (src !== "supervisor" && !content.includes("【AI监督") && !content.includes("【指挥官") && !content.includes("【御主")) return null;
    const m = content.match(/方案\s*#(\d+)/);
    const pivot = m ? Number(m[1]) : 0;
    const diag = (content.match(/判断：([^\n]+)/) || [])[1] || "";
    return {
      key: String(ev.id ?? `steer-${ev.ts}`),
      ts: ev.ts,
      kind: "plan",
      title: pivot ? t("sup.planN", { n: pivot }) : t("sup.planTitle"),
      diagnosis: diag,
      body: content,
      pivot,
    };
  }
  if (ev.type !== "log") return null;
  const msg = String(p.message || "");
  if (/换路兜底|机械模板|指挥官就绪|御主就绪|顾问就绪|未到周期性|本轮不改方向/.test(msg)) return null;
  if (/调用失败/.test(msg) && /AI监督/.test(msg)) {
    return {
      key: String(ev.id ?? `log-${ev.ts}`),
      ts: ev.ts,
      kind: "error",
      title: t("sup.legacyFail"),
      body: msg.replace(/^AI监督调用失败（本轮不注入方案）：/, ""),
    };
  }
  if (/未下达任务/.test(msg) && /指挥官|御主/.test(msg)) {
    return {
      key: String(ev.id ?? `log-${ev.ts}`),
      ts: ev.ts,
      kind: "error",
      title: t("sup.legacyTimeout"),
      body: msg,
    };
  }
  if (/空方案/.test(msg) && (/AI监督/.test(msg) || /指挥官/.test(msg) || /御主/.test(msg))) {
    return { key: String(ev.id ?? `log-${ev.ts}`), ts: ev.ts, kind: "empty", title: t("sup.legacyEmpty"), body: msg };
  }
  return null;
}

/** 有结构化 supervisor 事件时，丢掉同一次方案的 log/steer 摘要，避免三份重复。 */
function collectRows(events: RTEvent[]): SupervisorRow[] {
  const structured = events.filter((e) => e.type === "supervisor");
  const skipLegacy = new Set<string>();
  for (const ev of structured) {
    const p = ev.payload || {};
    const kind = String(p.kind || "plan");
    if (!VISIBLE_KINDS.has(kind)) continue;
    const pivot = Number(p.pivot) || 0;
    if (pivot) skipLegacy.add(`plan:${pivot}`);
    if (kind === "error") skipLegacy.add("error");
    if (kind === "empty") skipLegacy.add("empty");
    if (kind === "hold") skipLegacy.add("hold");
    if (kind === "runtime_review") skipLegacy.add("runtime_review");
  }

  const rows: SupervisorRow[] = [];
  for (const ev of events) {
    if (ev.type === "supervisor") {
      const row = fromSupervisorEvent(ev);
      if (row) rows.push(row);
      continue;
    }
    const row = fromLegacy(ev);
    if (!row) continue;
    if (row.kind === "plan" && row.pivot && skipLegacy.has(`plan:${row.pivot}`)) continue;
    if ((row.kind === "error" || row.kind === "empty" || row.kind === "hold") && skipLegacy.has(row.kind)) continue;
    rows.push(row);
  }
  return rows;
}

export function countSupervisorRecords(events: RTEvent[]): number {
  return collectRows(events).length;
}

export function SupervisorPanel({ events }: { events: RTEvent[] }) {
  const { t: tr } = useT();
  const rows = collectRows(events).slice().sort((a, b) => (b.ts || 0) - (a.ts || 0));
  if (!rows.length) {
    return (
      <p className="muted" style={{ padding: 16 }}>
        {tr("sup.emptyHint")}
      </p>
    );
  }
  return (
    <div className="advisor-panel">
      {rows.map((row) => (
        <article key={row.key} className={`advisor-record supervisor-${row.kind}`}>
          <div>
            <span className="badge badge-pill">{kindLabel(row.kind)}</span>
            <time>{row.ts ? new Date(row.ts * 1000).toLocaleString() : ""}</time>
          </div>
          <b>{row.title}</b>
          <div className="supervisor-meta">
            {row.turn ? <span>{tr("sup.turnN", { n: row.turn })}</span> : null}
            {row.stall && row.stall !== "none" ? <span>{tr("sup.stall", { text: stallLabel(row.stall) })}</span> : null}
            {row.quality && row.quality !== "none" ? <span>{tr("sup.progress", { text: row.quality })}</span> : null}
            {row.rebind ? <span>{tr("sup.rebindEntry")}</span> : null}
          </div>
          {row.diagnosis && row.diagnosis !== row.body ? <p className="supervisor-diag">{row.diagnosis}</p> : null}
          {row.body && <p>{row.body}</p>}
          {row.tags?.map((tag) => (
            <div key={tag.label} className="supervisor-tags">
              <span className="muted">{tr(tag.label)}</span>
              {tag.items.map((item) => (
                <span key={`${tag.label}-${item}`} className="badge badge-pill">{item}</span>
              ))}
            </div>
          ))}
        </article>
      ))}
    </div>
  );
}
