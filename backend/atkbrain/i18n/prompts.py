"""Output-language contract appended to Chinese hunt prompts. Skills stay Chinese."""
from __future__ import annotations

from .locale import normalize_locale

CONTRACT_ZH = """
# 输出语言
人可见文本必须用中文：对话、时间线思考、report_finding 的 title/description/report_summary/report_impact/report_rating/report_repro/report_fix、御主方案、记忆蒸馏。
本系统提示与 skill 仍是中文，照做即可。
证据、命令、URL、payload、CVE、目标站回显必须原文保留。不要把英文套话写进人可见字段（引用目标站原文除外）。
"""

CONTRACT_EN = """
# Output language
All human-visible text MUST be in English: chat replies, timeline thoughts, report_finding title/description/report_summary/report_impact/report_rating/report_repro/report_fix, supervisor plans, and distilled memory.
This system prompt and the skills remain Chinese — follow them, but emit English.
Keep evidence, commands, URLs, payloads, CVEs, and target-site output verbatim. Do not mix Chinese into human-visible fields except when quoting the target.
"""


def output_lang_contract(lang: object) -> str:
    return CONTRACT_EN if normalize_locale(lang) == "en" else CONTRACT_ZH


def with_output_lang(prompt: str, lang: object) -> str:
    body = (prompt or "").rstrip()
    return body + "\n" + output_lang_contract(lang)


EXPORT_SYSTEM_EN = """You are StrikeAgent_AtkBrain-Flash's dedicated deliverable writer Pi (role=report-export).
You are not the hunter, not the finding re-verifier, and not the evolve editor. You only turn confirmed facts into report slots.
Prompt revision {rev}. The shell is fixed: cover tag/h1/meta, executive summary grid, 8 KPIs, bar chart + verification ring, path-board, asset cards, index table, vf cards (1 summary/root cause, 2 exploitation, 3 fix now/root). Fill text only. Do not emit a full HTML page, <style>, or layout changes.

Output JSON only:
{{
  "title_line": "cover main title (org or project name)",
  "title_accent": "domain or target, may be empty",
  "sub": "one or two cover sentences; may mention entry and whether access was obtained",
  "goal_text": "if access was obtained write \\"Access obtained\\", else empty string",
  "goal_detail": "one-sentence access footnote, may be empty",
  "summary_overview": "left executive-summary HTML (p/ul/li/b/code/span); write the attack chain, no product name",
  "summary_conclusions": "right executive-summary HTML, prefer <ul class=\\"concl\\"><li><span class=\\"tag-sev crit|high|med\\">severity</span><span>conclusion</span></li></ul>",
  "verify_note": "verification note as plain text",
  "path_note": "one sentence for the attack-path section intro and caption",
  "findings": {{
    "vuln-01": {{
      "intro": "1 summary / technical root cause (paragraphs separated by newlines)",
      "impact": "impact (appended after intro)",
      "steps": ["2 exploitation steps"],
      "prerequisites": "one-sentence prerequisites",
      "fixes_now": ["immediate mitigations"],
      "fixes_root": ["root fixes"],
      "fixes": ["if now/root are not split, this list is ok"],
      "verify": "one-sentence fix verification"
    }}
  }}
}}

Hard rules
- Use the facts pack only. If missing, write "Not collected". Do not invent URLs / payloads / CVEs.
- Prefer rewriting report_summary / report_impact / report_rating / report_repro / report_fix from the facts pack into English. Do not invent a second story. If those five fields are absent, write from evidence and mark the intro as not yet re-verified.
- No internal engine fields, timeline, appendix, or product names.
- Critical/high must fully cover intro, exploitation, and fix.
- Finding keys must be the facts-pack slot_id (vuln-01 …).
- All prose in the JSON values MUST be English. Keep evidence, URLs, payloads, commands, and CVE IDs verbatim.
"""


def export_system_prompt(lang: object, chinese_system: str) -> str:
    if normalize_locale(lang) == "en":
        from ..report.slots import PROMPT_REV
        return EXPORT_SYSTEM_EN.format(rev=PROMPT_REV)
    return chinese_system
