"""Probe-candidate generator.

In production the LLM driving the skill produces candidates by reasoning over
state and writing JSON to a side channel; this module supplies the contract
+ a stub that returns no candidates when no LLM client is attached.

Mirrors stipo-r's generator.py — the controller is happy with an empty list
(falls through to bank fallback) when generation is unavailable.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from models import EvaluationState, ProbeCandidate


class LLMClient(Protocol):
    def generate(self, prompt: str, *, n: int = 1) -> list[str]: ...


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def build_prompt(state: EvaluationState, K: int) -> str:
    """Construct the prompt the LLM would see if available."""
    uncovered = state.uncovered_scenarios()
    open_hyps = state.open_hypotheses()
    lines: list[str] = [
        "You are generating ATAM probing questions.",
        f"Goal: {state.goal.primary} | depth={state.goal.depth}",
        "",
        "Uncovered scenarios (QA, importance, difficulty, title):",
    ]
    for s in uncovered[:8]:
        lines.append(f"  - [{s.qa}/I={s.importance}/D={s.difficulty}] {s.title}")
    if open_hyps:
        lines.append("")
        lines.append("Open hypotheses to discriminate:")
        for h in open_hyps[:5]:
            lines.append(f"  - {h.claim_text}")
            if h.discriminating_question:
                lines.append(f"    discriminator: {h.discriminating_question}")
    lines.extend([
        "",
        f"Produce {K} candidate probing questions in JSON:",
        '  [{"text": "...", "intent": "...", "target_qa": "...", "scenario_id": "...",',
        '    "estimated_time_minutes": 5.0, "expected_saturation_gain": 0.3}]',
        "",
        "Constraints:",
        "  - Each probe targets ONE scenario and ONE QA refinement.",
        "  - Surface risks, sensitivity points, tradeoffs — not feature questions.",
        "  - Probes must be answerable from architecture + code, not guessed.",
    ])
    return "\n".join(lines)


def generate_candidates(
    state: EvaluationState,
    K: int = 4,
    llm: LLMClient | None = None,
) -> list[ProbeCandidate]:
    if llm is None:
        return []

    prompt = build_prompt(state, K)
    prompt_hash = _prompt_hash(prompt)
    raw = llm.generate(prompt, n=1)
    if not raw:
        return []

    import json

    try:
        parsed = json.loads(raw[0])
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []

    out: list[ProbeCandidate] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                ProbeCandidate(
                    text=str(item["text"]),
                    intent=str(item.get("intent", "")),
                    target_qa=str(item["target_qa"]),
                    scenario_id=str(item.get("scenario_id", "")),
                    estimated_time_minutes=float(item.get("estimated_time_minutes", 5.0)),
                    expected_saturation_gain=float(
                        item.get("expected_saturation_gain", 0.3)
                    ),
                    generation_prompt_hash=prompt_hash,
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return out
