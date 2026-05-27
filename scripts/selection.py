"""Probe-selection pipeline.

The priority order (cf. STIPO-R selection.py):

  1. Open hypothesis  → bank "discriminator" probe targeting it
  2. Uncovered selected scenario → bank "standard" probe, argmax of
     expected_score_per_minute, IF expected gain ≥ threshold
  3. Generation fallback → LLM candidate + critique, gated by quality
  4. Bank standard fallback → if generation gate fails
  5. Closure
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from critic import critique
from generator import LLMClient, generate_candidates
from models import (
    BankProbe,
    EvaluationState,
    ProbeCandidate,
    ProbeCritique,
    ProbeDecision,
    ProbeRef,
    risk_level_le,
)

QUALITY_GATE_SCORE = 0.5
MAX_GENERATION_RETRIES = 2
BANK_PREFERRED_GAIN_THRESHOLD = 0.35


# --------------------------------------------------------------------------- #
# Bank filtering
# --------------------------------------------------------------------------- #


def _applies_when_satisfied(probe: BankProbe, state: EvaluationState) -> bool:
    if not probe.applies_when:
        return True
    for cond in probe.applies_when:
        condition = cond.get("condition")
        value = cond.get("value")
        if condition == "always":
            continue
        if condition == "qa_selected":
            if value not in {s.qa for s in state.scenarios.values() if s.selected_for_analysis}:
                return False
        elif condition == "scenario_uncovered":
            uncovered_qas = {s.qa for s in state.uncovered_scenarios()}
            if value not in uncovered_qas:
                return False
        elif condition == "open_hypothesis":
            if value not in {h.id for h in state.open_hypotheses()}:
                return False
        elif condition == "previous_probe_deployed":
            if value not in state.deployed_probe_ids:
                return False
        elif condition == "phase":
            if value != state.current_phase:
                return False
        else:
            return False  # unknown condition -> fail closed
    return True


def _prerequisites_met(probe: BankProbe, state: EvaluationState) -> bool:
    return all(req in state.deployed_probe_ids for req in probe.prerequisites)


def filter_candidates(
    bank: Iterable[BankProbe], state: EvaluationState
) -> list[BankProbe]:
    out: list[BankProbe] = []
    for p in bank:
        if p.probe_id in state.deployed_probe_ids:
            continue
        if not _applies_when_satisfied(p, state):
            continue
        if not _prerequisites_met(p, state):
            continue
        if not risk_level_le(p.risk_level, state.allowed_risk_level):
            continue
        out.append(p)
    return out


# --------------------------------------------------------------------------- #
# Tier-based selection
# --------------------------------------------------------------------------- #


def _bank_discriminator_probe(
    bank: list[BankProbe], state: EvaluationState
) -> tuple[BankProbe, str] | None:
    """Return (probe, hypothesis_id) if there's a bank discriminator matching an open hypothesis."""
    open_hyp_ids = {h.id for h in state.open_hypotheses()}
    if not open_hyp_ids:
        return None
    best: tuple[BankProbe, str] | None = None
    best_gain: float = -1.0
    for p in bank:
        if p.priority_tier != "discriminator":
            continue
        matching = [d for d in p.discriminates_hypotheses if d in open_hyp_ids]
        if not matching:
            continue
        gain = p.expected_score_per_minute()
        if gain > best_gain:
            best = (p, matching[0])
            best_gain = gain
    return best


def _scenario_target_score(probe: BankProbe, state: EvaluationState) -> float:
    """Multiplier favouring probes that target an uncovered scenario's QA."""
    uncovered_qas = {s.qa for s in state.uncovered_scenarios()}
    return 1.5 if probe.target_qa in uncovered_qas else 1.0


def _scope_match_score(probe: BankProbe, state: EvaluationState) -> float:
    """Multiplier favouring probes whose scope matches the evaluation's scope."""
    eval_scope = state.goal.evaluation_scope or "subsystem"
    probe_scope = probe.scope or "subsystem"
    return 1.3 if eval_scope == probe_scope else 1.0


def _argmax_score_per_minute(
    bank: list[BankProbe], state: EvaluationState
) -> BankProbe | None:
    if not bank:
        return None
    return max(
        bank,
        key=lambda p: (
            p.expected_score_per_minute()
            * _scenario_target_score(p, state)
            * _scope_match_score(p, state)
        ),
    )


def _pick_scenario_for_probe(probe: BankProbe, state: EvaluationState) -> str | None:
    """Pick the highest-importance uncovered scenario whose QA matches the probe."""
    candidates = [s for s in state.uncovered_scenarios() if s.qa == probe.target_qa]
    if not candidates:
        return None
    rank = {"H": 0, "M": 1, "L": 2}
    candidates.sort(key=lambda s: (rank.get(s.importance, 9), rank.get(s.difficulty, 9)))
    return candidates[0].scenario_id


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #


@dataclass
class SelectionResult:
    decision: ProbeDecision
    candidates: list[ProbeCandidate]
    critiques: list[ProbeCritique]


def select_probe(
    state: EvaluationState,
    bank: Iterable[BankProbe],
    K: int = 4,
    llm_generator: LLMClient | None = None,
    llm_critic: LLMClient | None = None,
) -> SelectionResult:
    bank_list = list(bank)
    filtered = filter_candidates(bank_list, state)

    # 0. Closure short-circuit: no work left, no hunches left → done.
    if not state.uncovered_scenarios() and not state.open_hypotheses():
        return SelectionResult(decision=ProbeDecision.closure(), candidates=[], critiques=[])

    # 1. Open hypothesis → bank discriminator
    disc = _bank_discriminator_probe(filtered, state)
    if disc is not None:
        probe, hyp_id = disc
        return SelectionResult(
            decision=ProbeDecision(
                chosen_probe=ProbeRef(
                    probe_id=probe.probe_id,
                    text_snapshot=probe.text,
                    target_qa=probe.target_qa,
                    intent=probe.intent,
                    scenario_id=_pick_scenario_for_probe(probe, state),
                ),
                source="bank",
                reason=f"Bank discriminator probe targeting open hypothesis {hyp_id}.",
                bank_probe_sha=probe.record_sha256,
                discriminates_hypothesis_id=hyp_id,
            ),
            candidates=[],
            critiques=[],
        )

    # 2. Uncovered scenario → bank standard probe
    standard = [p for p in filtered if p.priority_tier == "standard"]
    best_bank = _argmax_score_per_minute(standard, state)
    if (
        best_bank is not None
        and best_bank.expected_saturation_gain >= BANK_PREFERRED_GAIN_THRESHOLD
    ):
        return SelectionResult(
            decision=ProbeDecision(
                chosen_probe=ProbeRef(
                    probe_id=best_bank.probe_id,
                    text_snapshot=best_bank.text,
                    target_qa=best_bank.target_qa,
                    intent=best_bank.intent,
                    scenario_id=_pick_scenario_for_probe(best_bank, state),
                ),
                source="bank",
                reason=(
                    f"Bank standard probe; QA={best_bank.target_qa}; "
                    f"expected gain {best_bank.expected_saturation_gain:.2f} "
                    f"≥ threshold {BANK_PREFERRED_GAIN_THRESHOLD}."
                ),
                bank_probe_sha=best_bank.record_sha256,
            ),
            candidates=[],
            critiques=[],
        )

    # 3. Generation phase (only if something to probe)
    if state.uncovered_scenarios() or state.open_hypotheses():
        for _attempt in range(MAX_GENERATION_RETRIES + 1):
            candidates = generate_candidates(state, K=K, llm=llm_generator)
            if not candidates:
                continue
            critiques = critique(candidates, state, llm=llm_critic)
            if not critiques:
                continue
            top = max(critiques, key=lambda c: c.score)
            if top.verdict == "select" and top.score >= QUALITY_GATE_SCORE:
                cand = top.candidate
                pid = f"ai-generated-{cand.generation_prompt_hash[:8]}-{cand.target_qa}"
                return SelectionResult(
                    decision=ProbeDecision(
                        chosen_probe=ProbeRef(
                            probe_id=pid,
                            text_snapshot=cand.text,
                            target_qa=cand.target_qa,
                            intent=cand.intent,
                            scenario_id=cand.scenario_id,
                        ),
                        source="generated",
                        alternatives=tuple(
                            ProbeRef(
                                probe_id=f"ai-cand-{c.candidate.target_qa}",
                                text_snapshot=c.candidate.text,
                                target_qa=c.candidate.target_qa,
                            )
                            for c in critiques
                            if c is not top
                        ),
                        reason=(
                            f"Generated probe selected; critic score "
                            f"{top.score:.2f}: {top.rationale_text}"
                        ),
                    ),
                    candidates=candidates,
                    critiques=critiques,
                )

        # 4. Fallback bank
        fb = _argmax_score_per_minute(standard, state)
        if fb is not None:
            return SelectionResult(
                decision=ProbeDecision(
                    chosen_probe=ProbeRef(
                        probe_id=fb.probe_id,
                        text_snapshot=fb.text,
                        target_qa=fb.target_qa,
                        intent=fb.intent,
                        scenario_id=_pick_scenario_for_probe(fb, state),
                    ),
                    source="fallback-bank",
                    reason=(
                        "Generation quality gate failed; using bank standard fallback."
                    ),
                    bank_probe_sha=fb.record_sha256,
                ),
                candidates=[],
                critiques=[],
            )

    # 5. Closure
    return SelectionResult(decision=ProbeDecision.closure(), candidates=[], critiques=[])
