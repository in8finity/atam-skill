"""AtamController — the high-level evaluation driver.

Pulls state from hashharness via the adapter, calls `select_probe` for the
next move, persists the decision trail, and provides verbs for recording
the answer (ProbingQuestion + Finding + Evidence + Coverage update).

Mirrors stipo-r/controller.py in shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from generator import LLMClient
from mcp_adapter import ItemSpec, McpAdapter
from models import (
    BankProbe,
    Coverage,
    EvaluationGoal,
    EvaluationState,
    Hypothesis,
    ScenarioRef,
)
from selection import SelectionResult, select_probe


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class AtamController:
    evaluation_workpackage: str
    instrument_version_id: str
    instrument_version_ref: str  # record_sha256 of AtamInstrumentVersion
    mcp: McpAdapter
    evaluation_sha: str | None = None
    llm_generator: LLMClient | None = None
    llm_critic: LLMClient | None = None

    # ----- lifecycle ----- #

    def open_evaluation(
        self, system_name: str, evaluator: str, goal: EvaluationGoal | None = None
    ) -> str:
        goal = goal or EvaluationGoal()
        spec = ItemSpec(
            type="AtamEvaluation",
            work_package_id=self.evaluation_workpackage,
            title=f"ATAM: {system_name}",
            text=f"atam.eval:{self.evaluation_workpackage}",
            attributes={
                "system_name": system_name,
                "evaluator": evaluator,
                "start_date": _now_iso()[:10],
                "instrument_version_ref": self.instrument_version_id,
                "goal": {
                    "primary": goal.primary,
                    "secondary": list(goal.secondary),
                    "scope_minutes": goal.scope_minutes,
                    "depth": goal.depth,
                    "target_qas": list(goal.target_qas),
                    "evaluation_scope": goal.evaluation_scope,
                },
                "opened_at": _now_iso(),
            },
            links={},
        )
        self.evaluation_sha = self.mcp.create_item(spec)
        # First PhaseGate(0)
        gate = ItemSpec(
            type="PhaseGate",
            work_package_id=self.evaluation_workpackage,
            title="Phase 0 — Setup",
            text=f"atam.gate:{self.evaluation_workpackage}.p0",
            attributes={
                "phase": 0,
                "decision": "approved",
                "note": "Evaluation opened.",
                "at": _now_iso(),
            },
            links={"evaluation": self.evaluation_sha},
        )
        self.mcp.create_item(gate)
        return self.evaluation_sha

    def close_phase(
        self, phase: int, decision: str, note: str, prev_gate_sha: str
    ) -> str:
        spec = ItemSpec(
            type="PhaseGate",
            work_package_id=self.evaluation_workpackage,
            title=f"Phase {phase} gate",
            text=f"atam.gate:{self.evaluation_workpackage}.p{phase}",
            attributes={
                "phase": phase,
                "decision": decision,
                "note": note,
                "at": _now_iso(),
            },
            links={"evaluation": self.evaluation_sha, "prevGate": prev_gate_sha},
        )
        return self.mcp.create_item(spec)

    # ----- state assembly ----- #

    def load_bank(self) -> list[BankProbe]:
        refdata_wp = f"atam.refdata.{self.instrument_version_id}"
        # §1: get_work_package returns the full bank unbounded; find_items
        # capped at 50 by default and silently truncated for larger banks.
        records = self.mcp.get_work_package(refdata_wp, type="AtamBankProbe")
        bank: list[BankProbe] = []
        for r in records:
            a = r["attributes"]
            links = r.get("links", {})
            bank.append(
                BankProbe(
                    record_sha256=r["record_sha256"],
                    probe_id=a["probe_id"],
                    target_qa=a["target_qa"],
                    text=a["text"],
                    intent=a.get("intent", ""),
                    priority_tier=a["priority_tier"],
                    estimated_time_minutes=float(a["estimated_time_minutes"]),
                    expected_saturation_gain=float(a["expected_saturation_gain"]),
                    expected_findings=float(a.get("expected_findings", 1.0)),
                    risk_level=a.get("risk_level", "benign"),
                    discriminates_hypotheses=tuple(a.get("discriminates_hypotheses", [])),
                    applies_when=tuple(a.get("applies_when", [])),
                    prerequisites=tuple(links.get("prerequisites") or ()),
                    targets_components=tuple(a.get("targets_components", [])),
                    finding_types_targeted=tuple(a.get("finding_types_targeted", [])),
                    scope=a.get("scope", "subsystem"),
                )
            )
        return bank

    def state(self, phase: int = 6) -> EvaluationState:
        if not self.evaluation_sha:
            raise RuntimeError("open_evaluation() must be called before state()")
        wp = self.evaluation_workpackage

        # §5 (perf-integration 2026-05-30): load the whole evaluation wp once,
        # partition in memory. Replaces 6+ per-type round trips with one.
        # Also fixes §1 silent-truncation (the old find_items limits could be
        # crossed quietly on long-running evaluations).
        all_items = self.mcp.get_work_package(wp)
        by_type: dict[str, list[dict]] = {}
        for it in all_items:
            by_type.setdefault(it.get("type", ""), []).append(it)

        scenario_records = by_type.get("Scenario", [])
        rating_records = by_type.get("ScenarioRating", [])
        # Latest rating per scenario_sha — sort by created_at asc so last-write-wins gives newest
        rating_records.sort(key=lambda r: r.get("created_at", ""))
        latest_rating: dict[str, dict] = {}
        for r in rating_records:
            sc_sha = (r.get("links", {}) or {}).get("scenario")
            if not sc_sha:
                continue
            latest_rating[sc_sha] = r

        scenarios: dict[str, ScenarioRef] = {}
        for s in scenario_records:
            sc_sha = s["record_sha256"]
            rating = latest_rating.get(sc_sha, {})
            ra = rating.get("attributes", {})
            sa = s["attributes"]
            scenarios[s["text"]] = ScenarioRef(
                record_sha256=sc_sha,
                scenario_id=s["text"],
                title=s["title"],
                qa=sa.get("qa", ""),
                importance=ra.get("importance", "M"),
                difficulty=ra.get("difficulty", "M"),
                selected_for_analysis=bool(ra.get("selected_for_analysis", True)),
                category=sa.get("category", "anticipated"),
            )

        # Coverage: latest AtamCoverage per scenario — sort asc so last-write-wins is newest
        cov_records = by_type.get("AtamCoverage", [])
        cov_records.sort(key=lambda c: c.get("created_at", ""))
        latest_cov: dict[str, dict] = {}
        for c in cov_records:
            sc_sha = (c.get("links", {}) or {}).get("scenario")
            if not sc_sha:
                continue
            latest_cov[sc_sha] = c

        coverage: dict[str, Coverage] = {}
        for sid, sref in scenarios.items():
            c = latest_cov.get(sref.record_sha256)
            if c is None:
                coverage[sid] = Coverage(
                    scenario_id=sid, status="untouched", saturation=0.0
                )
                continue
            ca = c["attributes"]
            coverage[sid] = Coverage(
                scenario_id=sid,
                status=ca.get("status", "untouched"),
                saturation=float(ca.get("saturation", 0.0)),
                gaps=tuple(ca.get("gaps", [])),
                findings_count=int(ca.get("findings_count", 0)),
                questions_asked=int(ca.get("questions_asked", 0)),
            )

        # Hypotheses (open) — sort updates asc so last-write-wins is the newest status
        hyp_records = by_type.get("AtamHypothesis", [])
        update_records = by_type.get("AtamHypothesisUpdate", [])
        update_records.sort(key=lambda u: u.get("created_at", ""))
        latest_status_by_hyp: dict[str, str] = {}
        for u in update_records:
            hyp_sha = (u.get("links", {}) or {}).get("hypothesis")
            if not hyp_sha:
                continue
            latest_status_by_hyp[hyp_sha] = u["attributes"].get("status", "open")

        hypotheses: list[Hypothesis] = []
        for h in hyp_records:
            a = h["attributes"]
            status = latest_status_by_hyp.get(h["record_sha256"], a.get("status", "open"))
            hypotheses.append(
                Hypothesis(
                    id=h["text"],
                    claim_text=a.get("claim_text", ""),
                    status=status,
                    discriminating_question=a.get("discriminating_question"),
                    discriminates_probe_ids=tuple(a.get("discriminates_probe_ids", [])),
                    relevant_qas=tuple(a.get("relevant_qas", [])),
                    scenario_id=a.get("scenario_id"),
                )
            )

        # Deployed probes (from ProbingQuestion records)
        q_records = by_type.get("ProbingQuestion", [])
        deployed: set[str] = set()
        for q in q_records:
            pid = q["attributes"].get("probe_id")
            if pid:
                deployed.add(pid)

        # Evaluation goal — AtamEvaluation is already in by_type if the eval is open
        eval_recs = by_type.get("AtamEvaluation", [])
        eval_rec = next(
            (r for r in eval_recs if r.get("record_sha256") == self.evaluation_sha),
            None,
        )
        if eval_rec is None:
            eval_rec = self.mcp.get_item_by_hash(self.evaluation_sha)
        g = (eval_rec or {}).get("attributes", {}).get("goal", {})
        goal = EvaluationGoal(
            primary=g.get("primary", "find-tradeoffs-and-risks"),
            secondary=tuple(g.get("secondary", [])),
            scope_minutes=int(g.get("scope_minutes", 240)),
            depth=g.get("depth", "screening"),
            target_qas=tuple(g.get("target_qas", [])),
            evaluation_scope=g.get("evaluation_scope", "subsystem"),
        )

        return EvaluationState(
            evaluation_workpackage=wp,
            evaluation_sha=self.evaluation_sha,
            instrument_version_id=self.instrument_version_id,
            goal=goal,
            scenarios=scenarios,
            coverage=coverage,
            hypotheses=hypotheses,
            deployed_probe_ids=deployed,
            current_phase=phase,
        )

    # ----- decision + emission ----- #

    def next_probe(self, state: EvaluationState | None = None) -> SelectionResult:
        state = state or self.state()
        bank = self.load_bank()
        return select_probe(
            state, bank, llm_generator=self.llm_generator, llm_critic=self.llm_critic
        )

    def emit_decision_trail(
        self, result: SelectionResult, plan_index: int
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        if not self.evaluation_sha:
            raise RuntimeError("evaluation not open")

        # Plan
        plan = ItemSpec(
            type="AtamPlan",
            work_package_id=self.evaluation_workpackage,
            title=f"Plan #{plan_index}",
            text=f"atam.plan:{self.evaluation_workpackage}.p{plan_index}",
            attributes={
                "candidate_probes": [
                    {
                        "probe_id": alt.probe_id,
                        "text_snapshot": alt.text_snapshot,
                        "target_qa": alt.target_qa,
                        "priority": i + 1,
                    }
                    for i, alt in enumerate(result.decision.alternatives)
                ],
                "generated_at": _now_iso(),
            },
            links={"evaluation": self.evaluation_sha},
        )
        out["plan"] = self.mcp.create_item(plan)

        # AdaptiveDecision
        chosen = result.decision.chosen_probe
        decision_links: dict = {
            "plan": out["plan"],
            "evaluation": self.evaluation_sha,
        }
        if result.decision.bank_probe_sha:
            decision_links["bankProbe"] = result.decision.bank_probe_sha
        if result.decision.discriminates_hypothesis_id:
            # We need to look up the hypothesis record_sha by text-id
            hyp_records = self.mcp.find_items(
                type="AtamHypothesis", work_package_id=self.evaluation_workpackage, limit=200
            )
            for h in hyp_records:
                if h["text"] == result.decision.discriminates_hypothesis_id:
                    decision_links["discriminatesHypothesis"] = h["record_sha256"]
                    break

        decision = ItemSpec(
            type="AtamAdaptiveDecision",
            work_package_id=self.evaluation_workpackage,
            title=f"Decision #{plan_index}",
            text=f"atam.decision:{self.evaluation_workpackage}.d{plan_index}",
            attributes={
                "chosen_probe": (
                    {
                        "probe_id": chosen.probe_id,
                        "text_snapshot": chosen.text_snapshot,
                        "target_qa": chosen.target_qa,
                        "intent": chosen.intent,
                        "scenario_id": chosen.scenario_id,
                    }
                    if chosen
                    else None
                ),
                "source": result.decision.source,
                "reason": result.decision.reason,
                "decided_at": _now_iso(),
            },
            links=decision_links,
        )
        out["decision"] = self.mcp.create_item(decision)

        # Persist generated candidates + critiques
        for i, (cand, crit) in enumerate(zip(result.candidates, result.critiques)):
            cand_spec = ItemSpec(
                type="AtamProbeCandidate",
                work_package_id=self.evaluation_workpackage,
                title=f"Candidate #{plan_index}.{i}",
                text=f"atam.cand:{self.evaluation_workpackage}.p{plan_index}.c{i}",
                attributes={
                    "text": cand.text,
                    "intent": cand.intent,
                    "target_qa": cand.target_qa,
                    "scenario_id": cand.scenario_id,
                    "proposed_priority_tier": cand.proposed_priority_tier,
                    "proposed_risk_level": cand.proposed_risk_level,
                    "estimated_time_minutes": cand.estimated_time_minutes,
                    "expected_saturation_gain": cand.expected_saturation_gain,
                    "generation_prompt_hash": cand.generation_prompt_hash,
                },
                links={"evaluation": self.evaluation_sha, "plan": out["plan"]},
            )
            cand_sha = self.mcp.create_item(cand_spec)

            crit_spec = ItemSpec(
                type="AtamProbeCritique",
                work_package_id=self.evaluation_workpackage,
                title=f"Critique #{plan_index}.{i}",
                text=f"atam.crit:{self.evaluation_workpackage}.p{plan_index}.c{i}",
                attributes={
                    "score": crit.score,
                    "breakdown": {
                        "info_value": crit.breakdown.info_value,
                        "cost_eff": crit.breakdown.cost_eff,
                        "specificity": crit.breakdown.specificity,
                        "safety": crit.breakdown.safety,
                        "novelty": crit.breakdown.novelty,
                        "qa_alignment": crit.breakdown.qa_alignment,
                    },
                    "verdict": crit.verdict,
                    "rationale_text": crit.rationale_text,
                },
                links={"candidate": cand_sha, "evaluation": self.evaluation_sha},
            )
            self.mcp.create_item(crit_spec)

        return out
