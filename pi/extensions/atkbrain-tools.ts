import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { existsSync, realpathSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";

const BLOCKED = new Set(["bash", "powershell", "edit", "write", "grep", "find", "ls"]);

function underSkillsDir(cwd: string, rawPath: string): boolean {
  const skillsRoot = resolve(cwd, ".agents", "skills");
  const candidate = resolve(cwd, String(rawPath || ""));
  const rel = relative(skillsRoot, candidate);
  if (!rel || rel.startsWith("..") || isAbsolute(rel)) return false;
  try {
    if (!existsSync(skillsRoot)) return false;
    const realRoot = realpathSync(skillsRoot);
    const realTarget = existsSync(candidate) ? realpathSync(candidate) : candidate;
    const rel2 = relative(realRoot, realTarget);
    if (!rel2 || rel2.startsWith("..") || isAbsolute(rel2)) return false;
  } catch {
    return false;
  }
  return true;
}

function toType(schema: Record<string, unknown> | undefined) {
  const props = ((schema || {}).properties || {}) as Record<string, Record<string, unknown>>;
  const required = new Set<string>((schema || {}).required as string[] || []);
  const out: Record<string, unknown> = {};
  for (const [key, spec] of Object.entries(props)) {
    const desc = { description: String(spec?.description || "") };
    const t = String(spec?.type || "string");
    let field;
    if (t === "integer" || t === "number") field = Type.Number(desc);
    else if (t === "boolean") field = Type.Boolean(desc);
    else if (t === "array") {
      const items = (spec.items || {}) as Record<string, unknown>;
      const it = String(items.type || "string");
      if (it === "number" || it === "integer") field = Type.Array(Type.Number());
      else if (it === "boolean") field = Type.Array(Type.Boolean());
      else if (it === "object") field = Type.Array(Type.Object({}, { additionalProperties: true }));
      else field = Type.Array(Type.String());
    }
    else if (t === "object") field = Type.Object({}, { additionalProperties: true });
    else field = Type.String(desc);
    out[key] = required.has(key) ? field : Type.Optional(field);
  }
  return Type.Object(out, { additionalProperties: true });
}

export default async function (pi: ExtensionAPI) {
  const base = (process.env.ATKBRAIN_TOOLS_BASE || process.env.ATKBRAIN_API || "http://127.0.0.1:2333").replace(/\/$/, "");
  const pid = process.env.ATKBRAIN_PROJECT_ID || "";
  const token = (process.env.ATKBRAIN_API_TOKEN || "").trim();
  const role = (process.env.ATKBRAIN_PI_ROLE || "").trim();
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) headers["x-api-token"] = token;
  if (role) headers["x-atkbrain-role"] = role;
  let stopped = false;

  pi.on("tool_call", async (event, ctx) => {
    if (isToolCallEventType("read", event)) {
      const raw = String(event.input?.path || "");
      if (underSkillsDir(ctx.cwd, raw)) return {};
      return {
        block: true,
        reason: "内置 read 仅允许加载 cwd/.agents/skills 下的 SKILL.md；作业请用 run_cmd / http_request。",
      };
    }
    const n = String(event.toolName || "").toLowerCase();
    if (BLOCKED.has(n)) {
      return { block: true, reason: "内置文件系统/bash 已禁用，请用 run_cmd / http_request。" };
    }
    if (stopped) {
      return { block: true, reason: "本题已满分，停止工具。" };
    }
    return {};
  });

  if (!pid) return;

  const res = await fetch(`${base}/api/projects/${pid}/agent-tools`, { headers });
  if (!res.ok) {
    throw new Error(`atkbrain tools list HTTP ${res.status}`);
  }
  const body = await res.json();
  const tools = body.tools || [];
  for (const t of tools) {
    const name = String(t.name || "");
    if (!name) continue;
    pi.registerTool({
      name,
      label: name,
      description: t.description || name,
      parameters: toType(t.inputSchema || t.input_schema || {}),
      async execute(_toolCallId, params, signal) {
        const r = await fetch(`${base}/api/projects/${pid}/agent-tools/${encodeURIComponent(name)}`, {
          method: "POST",
          headers,
          body: JSON.stringify(params || {}),
          signal,
        });
        const out = await r.json().catch(() => ({ text: `HTTP ${r.status}`, is_error: true }));
        const text = String(out.text || "");
        // 只认工具接口正文开头的收工句。sqlite/日志里扫到历史「本题已满分」不能停本面。
        if (
          text.startsWith("本题已满分")
          || text.startsWith("本题 flag 已齐")
          || text.startsWith("本项目已达成终极目标")
        ) {
          stopped = true;
        }
        return {
          content: [{ type: "text", text }],
          details: { is_error: Boolean(out.is_error) },
        };
      },
    });
  }
}
