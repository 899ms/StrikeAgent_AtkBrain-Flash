import { useEffect, useMemo, useRef, useState } from "react";
import type { RTEvent } from "../../types";
import { coalesceStreamEvents } from "../timeline/coalesce";
import { t, useT } from "../../i18n";

interface Msg { role: "user" | "agent" | "sys"; text: string; id: string | number }

function toMessages(events: RTEvent[]): Msg[] {
  const out: Msg[] = [];
  let lastSupervisor = "";
  const push = (msg: Msg) => {
    const prev = out[out.length - 1];
    if (prev && prev.role === msg.role && prev.text === msg.text) return;
    out.push(msg);
  };
  for (const ev of events) {
    const p = ev.payload || {};
    const id = ev.id ?? `${ev.ts}-${ev.type}-${out.length}`;
    if (ev.type === "text" && p.text?.trim()) push({ role: "agent", text: p.text.trim(), id });
    else if (ev.type === "steer" && p.content) {
      if (p.source === "supervisor") {
        const text = `🧭 ${String(p.content)}`;
        if (text === lastSupervisor) continue;
        lastSupervisor = text;
        push({ role: "sys", text, id });
        continue;
      }
      if (p.source) continue;
      push({ role: "user", text: String(p.content), id });
    }
    else if (ev.type === "shell") push({ role: "sys", text: `🎯 ${t("chat.getshell")}${p.access || ""}`, id });
    else if (ev.type === "lateral") push({ role: "sys", text: `🌐 ${t("chat.lateral")}${p.hosts_footed ? t("timeline.hosts", { n: p.hosts_footed }) : ""}`, id });
    else if (ev.type === "finding_review") {
      const n = Number(p.count || (p.titles || []).length || 0);
      const titles = Array.isArray(p.titles) ? p.titles.filter(Boolean).slice(0, 4).join("；") : "";
      if (p.status === "running") {
        push({ role: "sys", text: `🔎 ${t("chat.reviewRun", { n })}${titles ? t("chat.paren", { text: titles }) : ""}`, id });
      } else if (p.status === "done") {
        push({ role: "sys", text: n ? `🔎 ${t("chat.reviewDoneN", { n })}` : `🔎 ${t("chat.reviewDone")}`, id });
      }
    }
    else if (ev.type === "report_export") {
      if (p.status === "running") push({ role: "sys", text: `📄 ${t("timeline.exportRun")}`, id });
      else if (p.status === "error") push({ role: "sys", text: `📄 ${t("timeline.exportErr", { msg: String(p.message || "").slice(0, 200) })}`, id });
      else if (p.status === "done") push({ role: "sys", text: `📄 ${t("timeline.exportDone")}`, id });
    }
    else if (ev.type === "log" && (p.level === "warn" || p.level === "error")) push({ role: "sys", text: String(p.message || "").slice(0, 400), id });
    else if (ev.type === "status" && ["goal_reached", "completed", "stopped", "error", "running"].includes(p.status) && p.turn === undefined) {
      push({ role: "sys", text: `● ${t("chat.status", { status: p.status })}`, id });
    }
  }
  return out.length > 200 ? out.slice(-200) : out;
}

export function ChatDock({
  events, running, queued, onSend, onStart, onStop, startLabel,
}: { events: RTEvent[]; running: boolean; queued?: boolean; onSend: (m: string) => void; onStart: () => void; onStop: () => void; startLabel?: string }) {
  const { t: tr, locale } = useT();
  const [text, setText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const msgs = useMemo(() => toMessages(coalesceStreamEvents(events)), [events, locale]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [msgs.length]);

  const send = () => {
    const next = text.trim();
    if (!next) return;
    onSend(next);
    setText("");
  };

  return (
    <div className="card-cream" style={{ display: "flex", flexDirection: "column", height: 320 }}>
      <div className="spread" style={{ marginBottom: 10 }}>
        <div className="row" style={{ gap: 8 }}>
          <span className="pulse-dot" style={{ background: queued ? "var(--warning)" : running ? "var(--success)" : "var(--muted-soft)" }} />
          <b style={{ fontSize: 15 }}>{tr("chat.title")}</b>
          <span className="muted" style={{ fontSize: 12 }}>
            {queued
              ? tr("chat.queued")
              : running
              ? tr("chat.running")
              : tr("chat.stopped")}
          </span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {running ? (
            <button className="btn btn-sm btn-danger" onClick={onStop}>{tr("common.stop")}</button>
          ) : (
            <button className="btn btn-sm btn-primary" onClick={onStart}>{startLabel || tr("project.startAuto")}</button>
          )}
        </div>
      </div>

      <div ref={listRef} className="scroll-y" style={{ flex: 1, background: "var(--canvas)", borderRadius: 8, padding: 12, border: "1px solid var(--hairline)" }}>
        {msgs.length === 0 && <p className="muted" style={{ fontSize: 13 }}>{tr("chat.empty")}</p>}
        {msgs.map((m) => (
          <div
            key={m.id}
            className={`chat-bubble ${
              m.role === "user" ? "chat-user"
                : m.role === "sys" ? "chat-sys"
                : "chat-agent"
            }`}
            style={{ whiteSpace: "pre-wrap" }}
          >{m.text}</div>
        ))}
      </div>

      <div className="row" style={{ marginTop: 10, gap: 8 }}>
        <input
          className="input" placeholder={tr("chat.ph")}
          value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button className="btn btn-primary" onClick={send}>{tr("chat.send")}</button>
      </div>
    </div>
  );
}
