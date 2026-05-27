"""Risk theme rollup and final-report assembly.

Mirrors stipo-r/synthesis.py: deterministic math, LLM-written narrative.
The controller calls these functions after Phase 8 to produce themes
and recommendations from the accumulated Finding records.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def cluster_risks_by_theme(findings: list[dict]) -> dict[str, list[dict]]:
    """Group Findings (finding_type='R') into themes by shared component_locus / affected_QA.

    A trivial clustering: signature = (sorted(affected_QAs), sorted(component_locus_ids)).
    Returns {theme_signature: [finding,...]}.
    """
    risks = [f for f in findings if f.get("attributes", {}).get("finding_type") == "R"]
    by_sig: dict[str, list[dict]] = defaultdict(list)
    for r in risks:
        links = r.get("links", {})
        affects = tuple(sorted(links.get("affects", []) or []))
        locus = tuple(sorted(links.get("locus", []) or []))
        sig = f"qas={list(affects)}|locus={list(locus)}"
        by_sig[sig].append(r)
    return dict(by_sig)


def find_threatened_drivers(
    theme_findings: list[dict], qa_to_drivers: dict[str, list[str]]
) -> list[str]:
    """Given findings in a theme and a QA→driver_shas map, return unique threatened drivers."""
    drivers: set[str] = set()
    for f in theme_findings:
        for qa_sha in f.get("links", {}).get("affects", []) or []:
            drivers.update(qa_to_drivers.get(qa_sha, []))
    return sorted(drivers)


def render_report_markdown(
    evaluation_attrs: dict[str, Any],
    business_drivers: list[dict],
    quality_attributes: list[dict],
    scenarios: list[dict],
    findings: list[dict],
    risk_themes: list[dict],
    recommendations: list[dict],
) -> str:
    """Render the consolidated ATAM report as Markdown.

    Structured baseline; the LLM can edit / augment the output file directly
    after generation (rationale, executive summary, treatment notes).
    """
    lines: list[str] = []
    lines.append("# ATAM Evaluation Report")
    lines.append("")
    lines.append(f"**System:** {evaluation_attrs.get('system_name', '<unknown>')}")
    lines.append(f"**Date:** {evaluation_attrs.get('start_date', '')}")
    lines.append(f"**Evaluator:** {evaluation_attrs.get('evaluator', '')}")
    lines.append("**Method:** ATAM (Kazman, Klein, Clements — SEI)")
    lines.append("")

    lines.append("## 1. Business drivers")
    for d in sorted(business_drivers, key=lambda x: x["attributes"].get("priority_rank", 99)):
        a = d["attributes"]
        lines.append(f"- **{d['title']}** — {a.get('description', '')} (rank {a.get('priority_rank', '-')})")
    lines.append("")

    lines.append("## 2. Quality attribute priorities")
    for qa in sorted(quality_attributes, key=lambda x: x["attributes"].get("priority_rank", 99)):
        lines.append(f"- {qa['title']} (rank {qa['attributes'].get('priority_rank', '-')})")
    lines.append("")

    lines.append("## 3. Findings")
    by_type = defaultdict(list)
    for f in findings:
        by_type[f["attributes"].get("finding_type", "?")].append(f)
    for kind, label in (
        ("R", "### 3.1 Risks"),
        ("TP", "### 3.2 Tradeoff points"),
        ("SP", "### 3.3 Sensitivity points"),
        ("NR", "### 3.4 Non-risks"),
    ):
        items = by_type.get(kind, [])
        if not items:
            continue
        lines.append(label)
        for f in items:
            a = f["attributes"]
            lines.append(f"- **{f['title']}** — {a.get('description', '')}")
            ev = f.get("links", {}).get("evidence", []) or []
            if ev:
                lines.append(f"  - evidence: {len(ev)} item(s)")
        lines.append("")

    lines.append("## 4. Risk themes")
    for t in risk_themes:
        a = t["attributes"]
        lines.append(f"### Theme: {t['title']}")
        lines.append(f"{a.get('description', '')}")
        members = t.get("links", {}).get("members", []) or []
        threats = t.get("links", {}).get("threatens", []) or []
        lines.append(f"- Risks rolled up: {len(members)}")
        lines.append(f"- Business drivers threatened: {len(threats)}")
        lines.append("")

    lines.append("## 5. Recommendations")
    for r in sorted(recommendations, key=lambda x: x["attributes"].get("priority", 99)):
        a = r["attributes"]
        lines.append(
            f"- **{r['title']}** — effort {a.get('effort', '-')}, owner {a.get('owner_role', '-')}, priority {a.get('priority', '-')}"
        )
    lines.append("")

    return "\n".join(lines)
