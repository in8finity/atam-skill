"""Probe-candidate critic.

Scores generated candidates along six dimensions and emits a verdict.
Default impl is rule-based (no LLM); a pluggable LLMClient can override
by supplying scored JSON directly.
"""

from __future__ import annotations

from typing import Protocol

from models import (
    CritiqueBreakdown,
    EvaluationState,
    ProbeCandidate,
    ProbeCritique,
)


class LLMClient(Protocol):
    def generate(self, prompt: str, *, n: int = 1) -> list[str]: ...


SELECT_THRESHOLD = 0.55
REVISE_THRESHOLD = 0.35


def _info_value(c: ProbeCandidate, state: EvaluationState) -> float:
    # Higher if it targets a high-importance uncovered scenario
    rank = {"H": 1.0, "M": 0.6, "L": 0.3}
    for s in state.uncovered_scenarios():
        if s.scenario_id == c.scenario_id:
            return rank.get(s.importance, 0.4)
    return 0.4


def _cost_eff(c: ProbeCandidate) -> float:
    if c.estimated_time_minutes <= 0:
        return 0.0
    return min(1.0, c.expected_saturation_gain / max(c.estimated_time_minutes, 1.0) * 10)


def _specificity(c: ProbeCandidate) -> float:
    # Crude heuristic: longer, more numeric/concrete text scores higher
    text = c.text
    score = min(1.0, len(text) / 200.0)
    if any(ch.isdigit() for ch in text):
        score = min(1.0, score + 0.15)
    if "?" in text:
        score = min(1.0, score + 0.1)
    return score


def _safety(c: ProbeCandidate) -> float:
    # No PII/credential prompts; default 1.0
    text_l = c.text.lower()
    if any(w in text_l for w in ("password", "private key", "credential")):
        return 0.4
    return 1.0


def _novelty(c: ProbeCandidate, state: EvaluationState) -> float:
    # Already-deployed probe ids penalize novelty
    for pid in state.deployed_probe_ids:
        if pid.endswith(c.target_qa):
            return 0.6
    return 1.0


def _qa_alignment(c: ProbeCandidate, state: EvaluationState) -> float:
    target_qas = {s.qa for s in state.uncovered_scenarios()}
    return 1.0 if c.target_qa in target_qas else 0.3


def critique(
    candidates: list[ProbeCandidate],
    state: EvaluationState,
    llm: LLMClient | None = None,
) -> list[ProbeCritique]:
    out: list[ProbeCritique] = []
    for c in candidates:
        br = CritiqueBreakdown(
            info_value=_info_value(c, state),
            cost_eff=_cost_eff(c),
            specificity=_specificity(c),
            safety=_safety(c),
            novelty=_novelty(c, state),
            qa_alignment=_qa_alignment(c, state),
        )
        score = (
            0.30 * br.info_value
            + 0.15 * br.cost_eff
            + 0.15 * br.specificity
            + 0.15 * br.safety
            + 0.10 * br.novelty
            + 0.15 * br.qa_alignment
        )
        if score >= SELECT_THRESHOLD:
            verdict = "select"
        elif score >= REVISE_THRESHOLD:
            verdict = "revise"
        else:
            verdict = "reject"
        rationale = (
            f"info={br.info_value:.2f} cost={br.cost_eff:.2f} "
            f"spec={br.specificity:.2f} safety={br.safety:.2f} "
            f"novelty={br.novelty:.2f} qa_align={br.qa_alignment:.2f}"
        )
        out.append(
            ProbeCritique(
                candidate=c,
                score=score,
                breakdown=br,
                verdict=verdict,
                rationale_text=rationale,
            )
        )
    return out
