"""ATAM controller CLI — Mode B execution path.

Invoked by the LLM running the skill once per analysis tick (Phase 6 / 8).
Each verb does one operation against hashharness via HashharnessAdapter
and prints JSON to stdout.

Usage:
  python cli.py open-evaluation   --workpackage WP --system NAME --evaluator EV \
                                   --instrument-version V
  python cli.py open-phase         --workpackage WP --phase N --prev-gate-sha SHA
  python cli.py close-phase        --workpackage WP --phase N --decision D \
                                   --prev-gate-sha SHA [--note "..."]
  python cli.py next-probe         --workpackage WP
  python cli.py record-question    --workpackage WP --decision-sha SHA \
                                   --scenario-sha SHA --probe-id PID \
                                   --probe-text TEXT --target-qa QA \
                                   [--source-bank-probe-sha SHA] [--probe-kind K]
  python cli.py record-finding     --workpackage WP --evaluation-sha SHA \
                                   --question-sha SHA --scenario-sha SHA \
                                   --finding-type R|NR|SP|TP \
                                   --title T --description D \
                                   --evidence-shas SHA1,SHA2 \
                                   --affects-qa-shas SHA1,SHA2 \
                                   [--locus-shas SHA1,SHA2] [--severity high|med|low]
  python cli.py record-evidence    --workpackage WP --evaluation-sha SHA \
                                   --kind K --pointer P --quoted-text TEXT \
                                   [--cites-decision-sha SHA] [--cites-component-sha SHA]
  python cli.py update-coverage    --workpackage WP --evaluation-sha SHA \
                                   --scenario-sha SHA --decision-sha SHA \
                                   --status S --saturation N \
                                   [--gaps G1,G2] [--findings-count N] [--questions-asked N]
  python cli.py open-hypothesis    --workpackage WP --evaluation-sha SHA \
                                   --scenario-sha SHA --claim T \
                                   --discriminating-question Q \
                                   [--relevant-qas QA1,QA2]
  python cli.py update-hypothesis  --workpackage WP --hypothesis-sha SHA \
                                   --status confirmed|refuted|dropped \
                                   [--evidence-shas SHA1,SHA2] [--prev-update-sha SHA]
  python cli.py state              --workpackage WP

All verbs print {"ok": true, ...} JSON on success; {"ok": false, "error": "..."} on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _bootstrap_paths() -> None:
    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))
    venv_site = (
        Path.home() / ".hashharness" / "venv" / "lib" / "python3.14" / "site-packages"
    )
    if venv_site.exists() and str(venv_site) not in sys.path:
        sys.path.insert(0, str(venv_site))


_bootstrap_paths()


from controller import AtamController  # noqa: E402
from hashharness_adapter import HashharnessAdapter  # noqa: E402
from mcp_adapter import ItemSpec  # noqa: E402
from models import EvaluationGoal  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ok(**kw) -> None:
    print(json.dumps({"ok": True, **kw}, default=str))


def _err(msg: str, code: int = 1) -> None:
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(code)


def _find_instrument_version_ref(adapter: HashharnessAdapter, version_id: str) -> str:
    refdata_wp = f"atam.refdata.{version_id}"
    items = adapter.find_items(type="AtamInstrumentVersion", work_package_id=refdata_wp)
    if not items:
        raise RuntimeError(
            f"AtamInstrumentVersion '{version_id}' not found in {refdata_wp}"
        )
    return items[0]["record_sha256"]


def _split_csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


# --------------------------------------------------------------------------- #
# Verb handlers
# --------------------------------------------------------------------------- #


def verb_open_evaluation(args) -> None:
    adapter = HashharnessAdapter()
    iv_ref = _find_instrument_version_ref(adapter, args.instrument_version)
    controller = AtamController(
        evaluation_workpackage=args.workpackage,
        instrument_version_id=args.instrument_version,
        instrument_version_ref=iv_ref,
        mcp=adapter,
    )
    goal = EvaluationGoal(
        primary=args.goal_primary,
        scope_minutes=args.goal_scope_minutes,
        depth=args.goal_depth,
        target_qas=tuple(_split_csv(args.goal_target_qas)),
        evaluation_scope=args.goal_scope,
    )
    eval_sha = controller.open_evaluation(
        system_name=args.system, evaluator=args.evaluator, goal=goal
    )
    gates = adapter.find_items(type="PhaseGate", work_package_id=args.workpackage)
    p0_sha = gates[0]["record_sha256"] if gates else None
    _ok(evaluation_sha=eval_sha, p0_gate_sha=p0_sha, instrument_version_ref=iv_ref)


def verb_close_phase(args) -> None:
    adapter = HashharnessAdapter()
    iv_ref = _find_instrument_version_ref(adapter, args.instrument_version)
    case_items = adapter.find_items(type="AtamEvaluation", work_package_id=args.workpackage)
    if not case_items:
        _err(f"No AtamEvaluation in {args.workpackage}")
    eval_sha = case_items[0]["record_sha256"]
    controller = AtamController(
        evaluation_workpackage=args.workpackage,
        instrument_version_id=args.instrument_version,
        instrument_version_ref=iv_ref,
        mcp=adapter,
        evaluation_sha=eval_sha,
    )
    gate_sha = controller.close_phase(
        phase=args.phase,
        decision=args.decision,
        note=args.note,
        prev_gate_sha=args.prev_gate_sha,
    )
    _ok(gate_sha=gate_sha)


def verb_state(args) -> None:
    adapter = HashharnessAdapter()
    iv_ref = _find_instrument_version_ref(adapter, args.instrument_version)
    case_items = adapter.find_items(type="AtamEvaluation", work_package_id=args.workpackage)
    if not case_items:
        _err(f"No AtamEvaluation in {args.workpackage}")
    eval_sha = case_items[0]["record_sha256"]
    controller = AtamController(
        evaluation_workpackage=args.workpackage,
        instrument_version_id=args.instrument_version,
        instrument_version_ref=iv_ref,
        mcp=adapter,
        evaluation_sha=eval_sha,
    )
    state = controller.state(phase=args.phase)
    bank = controller.load_bank()
    _ok(
        evaluation_sha=eval_sha,
        phase=args.phase,
        scenarios_count=len(state.scenarios),
        coverage={
            sid: {
                "status": c.status,
                "saturation": c.saturation,
                "findings": c.findings_count,
            }
            for sid, c in state.coverage.items()
        },
        uncovered_scenarios=[s.scenario_id for s in state.uncovered_scenarios()],
        open_hypotheses=[h.id for h in state.open_hypotheses()],
        deployed_probe_ids=sorted(state.deployed_probe_ids),
        bank_size=len(bank),
    )


def verb_next_probe(args) -> None:
    adapter = HashharnessAdapter()
    iv_ref = _find_instrument_version_ref(adapter, args.instrument_version)
    case_items = adapter.find_items(type="AtamEvaluation", work_package_id=args.workpackage)
    if not case_items:
        _err(f"No AtamEvaluation in {args.workpackage}")
    eval_sha = case_items[0]["record_sha256"]
    controller = AtamController(
        evaluation_workpackage=args.workpackage,
        instrument_version_id=args.instrument_version,
        instrument_version_ref=iv_ref,
        mcp=adapter,
        evaluation_sha=eval_sha,
    )
    state = controller.state(phase=args.phase)
    result = controller.next_probe(state)
    plans = adapter.find_items(type="AtamPlan", work_package_id=args.workpackage, limit=500)
    refs = controller.emit_decision_trail(result, plan_index=len(plans) + 1)
    chosen = result.decision.chosen_probe
    _ok(
        source=result.decision.source,
        chosen_probe=(
            {
                "probe_id": chosen.probe_id,
                "text": chosen.text_snapshot,
                "target_qa": chosen.target_qa,
                "intent": chosen.intent,
                "scenario_id": chosen.scenario_id,
            }
            if chosen
            else None
        ),
        reason=result.decision.reason,
        plan_sha=refs.get("plan"),
        decision_sha=refs.get("decision"),
        candidates_count=len(result.candidates),
    )


def verb_record_question(args) -> None:
    adapter = HashharnessAdapter()
    questions = adapter.find_items(
        type="ProbingQuestion", work_package_id=args.workpackage, limit=500
    )
    q_index = len(questions) + 1
    spec = ItemSpec(
        type="ProbingQuestion",
        work_package_id=args.workpackage,
        title=f"Q{q_index}: {args.probe_id}",
        text=f"atam.question:{args.workpackage}.q{q_index}",
        attributes={
            "probe_id": args.probe_id,
            "text": args.probe_text,
            "target_qa": args.target_qa,
            "probe_kind": args.probe_kind,
            "phase": args.phase,
            "asked_at": _now_iso(),
            "answer_summary": args.answer_summary,
        },
        links={
            "evaluation": args.evaluation_sha,
            "scenario": args.scenario_sha,
            "decision": args.decision_sha,
            **(
                {"sourceBankProbe": args.source_bank_probe_sha}
                if args.source_bank_probe_sha
                else {}
            ),
        },
    )
    q_sha = adapter.create_item(spec)
    _ok(question_sha=q_sha, question_index=q_index)


def verb_record_evidence(args) -> None:
    adapter = HashharnessAdapter()
    evs = adapter.find_items(type="AtamEvidence", work_package_id=args.workpackage, limit=500)
    n = len(evs) + 1
    links: dict = {"evaluation": args.evaluation_sha}
    if args.cites_decision_sha:
        links["citesDecision"] = args.cites_decision_sha
    if args.cites_component_sha:
        links["citesComponent"] = args.cites_component_sha
    spec = ItemSpec(
        type="AtamEvidence",
        work_package_id=args.workpackage,
        title=args.pointer[:60],
        text=f"atam.evidence:{args.workpackage}.e{n}",
        attributes={
            "kind": args.kind,
            "pointer": args.pointer,
            "quoted_text": args.quoted_text,
            "recorded_at": _now_iso(),
        },
        links=links,
    )
    ev_sha = adapter.create_item(spec)
    _ok(evidence_sha=ev_sha)


def verb_record_finding(args) -> None:
    adapter = HashharnessAdapter()
    findings = adapter.find_items(type="Finding", work_package_id=args.workpackage, limit=500)
    n = len(findings) + 1
    ev_shas = _split_csv(args.evidence_shas)
    qa_shas = _split_csv(args.affects_qa_shas)
    locus_shas = _split_csv(args.locus_shas) if args.locus_shas else []

    if not ev_shas:
        _err("record-finding requires --evidence-shas (≥1); quote-or-no-finding rule.")

    links: dict = {
        "evaluation": args.evaluation_sha,
        "scenario": args.scenario_sha,
        "answeringQuestion": args.question_sha,
        "evidence": ev_shas,
        "affects": qa_shas,
    }
    if locus_shas:
        links["locus"] = locus_shas
    if args.supersedes:
        links["supersedes"] = args.supersedes
    if args.approach_sha:
        links["approach"] = args.approach_sha

    spec = ItemSpec(
        type="Finding",
        work_package_id=args.workpackage,
        title=args.title,
        text=f"atam.finding:{args.workpackage}.f{n}",
        attributes={
            "finding_type": args.finding_type,
            "description": args.description,
            "phase": args.phase,
            "severity": args.severity,
            "promotion_reason": args.promotion_reason,
            "recorded_at": _now_iso(),
        },
        links=links,
    )
    f_sha = adapter.create_item(spec)
    _ok(finding_sha=f_sha, finding_type=args.finding_type)


def verb_update_coverage(args) -> None:
    adapter = HashharnessAdapter()
    covs = adapter.find_items(type="AtamCoverage", work_package_id=args.workpackage, limit=1000)
    n = len(covs) + 1
    # Find prior for this scenario
    prior_sha = None
    for c in covs:
        if (c.get("links") or {}).get("scenario") == args.scenario_sha:
            prior_sha = c["record_sha256"]  # last write wins
    links: dict = {
        "evaluation": args.evaluation_sha,
        "scenario": args.scenario_sha,
        "decision": args.decision_sha,
    }
    if prior_sha:
        links["previous"] = prior_sha
    spec = ItemSpec(
        type="AtamCoverage",
        work_package_id=args.workpackage,
        title=f"Coverage #{n}",
        text=f"atam.coverage:{args.workpackage}.c{n}",
        attributes={
            "status": args.status,
            "saturation": args.saturation,
            "gaps": _split_csv(args.gaps) if args.gaps else [],
            "findings_count": args.findings_count,
            "questions_asked": args.questions_asked,
            "updated_at": _now_iso(),
        },
        links=links,
    )
    cov_sha = adapter.create_item(spec)
    _ok(coverage_sha=cov_sha)


def verb_open_hypothesis(args) -> None:
    adapter = HashharnessAdapter()
    hyps = adapter.find_items(type="AtamHypothesis", work_package_id=args.workpackage, limit=500)
    n = len(hyps) + 1
    links: dict = {"evaluation": args.evaluation_sha}
    if args.scenario_sha:
        links["scenario"] = args.scenario_sha
    spec = ItemSpec(
        type="AtamHypothesis",
        work_package_id=args.workpackage,
        title=args.claim[:60],
        text=f"atam.hypothesis:{args.workpackage}.h{n}",
        attributes={
            "claim_text": args.claim,
            "status": "open",
            "discriminating_question": args.discriminating_question,
            "relevant_qas": _split_csv(args.relevant_qas) if args.relevant_qas else [],
            "discriminates_probe_ids": _split_csv(args.discriminates_probe_ids) if args.discriminates_probe_ids else [],
            "opened_at": _now_iso(),
        },
        links=links,
    )
    h_sha = adapter.create_item(spec)
    _ok(hypothesis_sha=h_sha, hypothesis_id=spec.text)


# --------------------------------------------------------------------------- #
# Challenge step — prepare a CQ review for a Finding (see SKILL.md §11)
# --------------------------------------------------------------------------- #


SCHEME_CATALOG = {
    "negative_consequences": [
        ("CQ1", "A", "likelihood_of_consequence", "How likely is the negative consequence to actually occur?"),
        ("CQ2", "B", "evidence_for_consequence_claim", "Is the body of evidence here strong enough?"),
        ("CQ3", "C", "opposite_consequences_to_consider", "Are there positive consequences that outweigh the negative?"),
    ],
    "cause_to_effect": [
        ("CQ4", "A", "generalization_holds", "Does the general causal rule actually hold in this domain?"),
        ("CQ5", "A", "no_intervening_cause", "Is the effect attributable to the named cause, or to something else (e.g. ownership, missing review)?"),
        ("CQ6", "B", "no_blocker", "Is there a blocker (a workaround already in place) that prevents the causal mechanism from completing?"),
    ],
    "sign": [
        ("CQ7", "B", "sign_event_correlation_strength", "How strongly does this observation correlate with the claimed systemic property? One incident vs many?"),
        ("CQ8", "A", "alternative_event_accounting_for_sign", "Could the past incident be explained by something other than the named cause (e.g. one-off refactor)?"),
    ],
    "evidence_to_hypothesis": [
        ("CQ9", "C", "hypothesis_entails_observation", "Does the hypothesis actually predict the observations we see?"),
        ("CQ10", "C", "observation_actually_made", "Are the claimed observations accurate and current?"),
        ("CQ11", "A", "alternative_reason_for_observation", "Could the observation be explained by an alternative hypothesis (e.g. deliberate layer-appropriate design vs accidental duplication)?"),
    ],
    "abductive": [
        ("CQ12", "B", "satisfactoriness_of_explanation", "Does the explanation actually explain the symptoms, or is it a label without explanatory power?"),
        ("CQ13", "A", "comparison_with_alternatives", "Is the risk reading better than the alternative 'the team is working as designed and absorbing low-frequency drift cheaply'?"),
        ("CQ14", "C", "thoroughness_of_inquiry", "Has the finding been investigated thoroughly, or reached after one read?"),
        ("CQ15", "C", "continue_inquiry_vs_close", "Should more evidence be gathered before treating this as established?"),
    ],
    "precedent": [
        ("CQ16", "A", "rule_applies_to_present_case", "Does the cited precedent actually apply, or is the present case different in load-bearing respects?"),
        ("CQ17", "A", "cited_case_legitimate", "Is the cited precedent genuinely similar, or only superficially?"),
        ("CQ18", "B", "recognized_exception_already_exists", "Has the team adopted a practice that legitimately covers cases like this?"),
    ],
    "practical_reasoning": [
        ("PR-OM", "A", "other_means", "Are there other means that achieve the goal more cheaply?"),
        ("PR-BM", "B", "best_means", "Is the proposed means the best, considering side effects?"),
        ("PR-SE", "A", "side_effects", "Will the means produce undesirable side effects (cost, dependencies, write amplification)?"),
        ("PR-PO", "B", "possibility", "Is the means feasible given existing constraints (ownership, third-party dependencies)?"),
    ],
}


def _infer_schemes(finding_attrs: dict, finding_links: dict) -> list[str]:
    """Heuristic scheme detection based on a Finding's shape."""
    schemes: list[str] = []
    ftype = finding_attrs.get("finding_type", "")
    severity = finding_attrs.get("severity", "")
    description = (finding_attrs.get("description") or "").lower()
    title = (finding_attrs.get("title") or "").lower()
    text = title + " " + description

    # Every R/TP/SP finding invokes negative_consequences implicitly
    if ftype in ("R", "TP", "SP"):
        schemes.append("negative_consequences")
    # Causal language → cause_to_effect
    if any(w in text for w in (" → ", "->", "causes", "leads to", "results in", "enables", "triggers")):
        schemes.append("cause_to_effect")
    # Past-incident citation → sign
    if any(w in text for w in ("incident", "already happened", "already lived through", "documented drift", "precedent")):
        schemes.append("sign")
    # Architecture-property claim → evidence_to_hypothesis
    if any(w in text for w in ("duplicat", "missing contract", "lacks", "no circuit", "no audit", "no idempotency")):
        schemes.append("evidence_to_hypothesis")
    # Sibling-finding reference → precedent
    if any(w in text for w in ("h1 in miniature", "sibling", "similar to", "instance of", "like f")):
        schemes.append("precedent")
    # Synthesis / risk-theme membership → abductive
    if severity == "high" and ftype == "R":
        schemes.append("abductive")
    # Recommendation → practical_reasoning (handled separately when challenging Recommendation records)
    return list(dict.fromkeys(schemes))  # preserve order, dedup


def verb_challenge(args) -> None:
    """Prepare a CQ review for one Finding (or Recommendation). Hands off to aif-arguments."""
    adapter = HashharnessAdapter()
    target = adapter.get_item_by_hash(args.finding_sha)
    if not target:
        _err(f"Record not found: {args.finding_sha}")
    rec_type = target.get("type", "")
    if rec_type not in ("Finding", "Recommendation"):
        _err(f"challenge expects Finding or Recommendation, got {rec_type}")

    attrs = target.get("attributes", {}) or {}
    links = target.get("links", {}) or {}

    # Scheme selection: explicit override, else inferred (Recommendation always practical_reasoning).
    if args.scheme:
        schemes = [args.scheme]
    elif rec_type == "Recommendation":
        schemes = ["practical_reasoning"]
    else:
        schemes = _infer_schemes(attrs, links)
        if not schemes:
            schemes = ["negative_consequences"]  # safe fallback

    # Build the CQ list
    cqs: list[dict] = []
    for scheme in schemes:
        for cq_id, tier, name, question in SCHEME_CATALOG.get(scheme, []):
            if args.tier_only and tier not in args.tier_only:
                continue
            cqs.append({
                "scheme": scheme,
                "cq_id": cq_id,
                "tier": tier,
                "name": name,
                "question": question,
            })

    # Load evidence summaries to give the LLM context for answering
    evidence_summaries: list[dict] = []
    for ev_sha in (links.get("evidence") or []):
        ev = adapter.get_item_by_hash(ev_sha)
        if ev:
            evidence_summaries.append({
                "sha": ev_sha,
                "pointer": ev.get("attributes", {}).get("pointer", ""),
                "kind": ev.get("attributes", {}).get("kind", ""),
                "quoted_text_snippet": (ev.get("attributes", {}).get("quoted_text", "") or "")[:200],
            })

    _ok(
        record_type=rec_type,
        target_sha=args.finding_sha,
        target_title=target.get("title", ""),
        target_severity=attrs.get("severity", ""),
        target_finding_type=attrs.get("finding_type", ""),
        schemes_invoked=schemes,
        evidence_count=len(evidence_summaries),
        evidence_summaries=evidence_summaries,
        critical_questions=cqs,
        next_step=(
            "Hand off to aif-arguments skill: pass the target, schemes, and CQ list. "
            "aif-arguments builds I/RA/CA/PA nodes for the exchange. "
            "After the exchange, use 'record-finding --supersedes' for revisions, "
            "or attach a 'challenged-and-survived' AtamEvidence (kind=quote) if the Finding stands."
        ),
    )


def verb_update_hypothesis(args) -> None:
    adapter = HashharnessAdapter()
    updates = adapter.find_items(
        type="AtamHypothesisUpdate", work_package_id=args.workpackage, limit=1000
    )
    n = len(updates) + 1
    ev_shas = _split_csv(args.evidence_shas) if args.evidence_shas else []
    links: dict = {"hypothesis": args.hypothesis_sha}
    if ev_shas:
        links["evidence"] = ev_shas
    if args.prev_update_sha:
        links["prevUpdate"] = args.prev_update_sha
    spec = ItemSpec(
        type="AtamHypothesisUpdate",
        work_package_id=args.workpackage,
        title=f"Hyp update → {args.status}",
        text=f"atam.hypupdate:{args.workpackage}.hu{n}",
        attributes={
            "status": args.status,
            "note": args.note,
            "updated_at": _now_iso(),
        },
        links=links,
    )
    u_sha = adapter.create_item(spec)
    _ok(update_sha=u_sha, status=args.status)


# --------------------------------------------------------------------------- #
# Argparse
# --------------------------------------------------------------------------- #


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATAM controller CLI (Mode B).")
    sub = parser.add_subparsers(dest="verb", required=True)

    def _common(p):
        p.add_argument("--workpackage", required=True)
        p.add_argument("--instrument-version", default="atam-v1")

    p_oe = sub.add_parser("open-evaluation")
    _common(p_oe)
    p_oe.add_argument("--system", required=True)
    p_oe.add_argument("--evaluator", required=True)
    p_oe.add_argument("--goal-primary", default="find-tradeoffs-and-risks")
    p_oe.add_argument("--goal-scope-minutes", type=int, default=240)
    p_oe.add_argument("--goal-depth", default="screening", choices=["screening", "comprehensive"])
    p_oe.add_argument("--goal-target-qas", default="")
    p_oe.add_argument("--goal-scope", default="subsystem", choices=["subsystem", "endpoint", "module"], help="Evaluation scope; biases bank-probe selection toward matching-scope probes (1.3x score multiplier).")
    p_oe.set_defaults(fn=verb_open_evaluation)

    p_cp = sub.add_parser("close-phase")
    _common(p_cp)
    p_cp.add_argument("--phase", type=int, required=True)
    p_cp.add_argument("--decision", required=True, choices=["approved", "revised", "skipped"])
    p_cp.add_argument("--prev-gate-sha", required=True)
    p_cp.add_argument("--note", default="")
    p_cp.set_defaults(fn=verb_close_phase)

    p_s = sub.add_parser("state")
    _common(p_s)
    p_s.add_argument("--phase", type=int, default=6)
    p_s.set_defaults(fn=verb_state)

    p_np = sub.add_parser("next-probe")
    _common(p_np)
    p_np.add_argument("--phase", type=int, default=6)
    p_np.set_defaults(fn=verb_next_probe)

    p_rq = sub.add_parser("record-question")
    _common(p_rq)
    p_rq.add_argument("--evaluation-sha", required=True)
    p_rq.add_argument("--decision-sha", required=True)
    p_rq.add_argument("--scenario-sha", required=True)
    p_rq.add_argument("--probe-id", required=True)
    p_rq.add_argument("--probe-text", required=True)
    p_rq.add_argument("--target-qa", required=True)
    p_rq.add_argument("--probe-kind", default="open")
    p_rq.add_argument("--phase", type=int, default=6)
    p_rq.add_argument("--source-bank-probe-sha", default="")
    p_rq.add_argument("--answer-summary", default="")
    p_rq.set_defaults(fn=verb_record_question)

    p_re = sub.add_parser("record-evidence")
    _common(p_re)
    p_re.add_argument("--evaluation-sha", required=True)
    p_re.add_argument("--kind", required=True, choices=["adr", "file_ref", "measurement", "quote", "test_result", "incident", "doc"])
    p_re.add_argument("--pointer", required=True)
    p_re.add_argument("--quoted-text", default="")
    p_re.add_argument("--cites-decision-sha", default="")
    p_re.add_argument("--cites-component-sha", default="")
    p_re.set_defaults(fn=verb_record_evidence)

    p_rf = sub.add_parser("record-finding")
    _common(p_rf)
    p_rf.add_argument("--evaluation-sha", required=True)
    p_rf.add_argument("--question-sha", required=True)
    p_rf.add_argument("--scenario-sha", required=True)
    p_rf.add_argument("--approach-sha", default="")
    p_rf.add_argument("--finding-type", required=True, choices=["R", "NR", "SP", "TP"])
    p_rf.add_argument("--title", required=True)
    p_rf.add_argument("--description", required=True)
    p_rf.add_argument("--evidence-shas", required=True)
    p_rf.add_argument("--affects-qa-shas", required=True)
    p_rf.add_argument("--locus-shas", default="")
    p_rf.add_argument("--phase", type=int, default=6)
    p_rf.add_argument("--severity", default="med", choices=["high", "med", "low"])
    p_rf.add_argument("--promotion-reason", default="")
    p_rf.add_argument("--supersedes", default="")
    p_rf.set_defaults(fn=verb_record_finding)

    p_uc = sub.add_parser("update-coverage")
    _common(p_uc)
    p_uc.add_argument("--evaluation-sha", required=True)
    p_uc.add_argument("--scenario-sha", required=True)
    p_uc.add_argument("--decision-sha", required=True)
    p_uc.add_argument("--status", required=True, choices=["untouched", "in-progress", "sufficient", "saturated"])
    p_uc.add_argument("--saturation", type=float, required=True)
    p_uc.add_argument("--gaps", default="")
    p_uc.add_argument("--findings-count", type=int, default=0)
    p_uc.add_argument("--questions-asked", type=int, default=0)
    p_uc.set_defaults(fn=verb_update_coverage)

    p_oh = sub.add_parser("open-hypothesis")
    _common(p_oh)
    p_oh.add_argument("--evaluation-sha", required=True)
    p_oh.add_argument("--scenario-sha", default="")
    p_oh.add_argument("--claim", required=True)
    p_oh.add_argument("--discriminating-question", required=True)
    p_oh.add_argument("--relevant-qas", default="")
    p_oh.add_argument("--discriminates-probe-ids", default="")
    p_oh.set_defaults(fn=verb_open_hypothesis)

    p_ch = sub.add_parser("challenge")
    _common(p_ch)
    p_ch.add_argument("--finding-sha", required=True, help="Finding or Recommendation record_sha256 to challenge")
    p_ch.add_argument("--scheme", default="", choices=["", "negative_consequences", "cause_to_effect", "sign", "evidence_to_hypothesis", "abductive", "precedent", "practical_reasoning"], help="Override automatic scheme detection")
    p_ch.add_argument("--tier-only", nargs="+", default=[], choices=["A", "B", "C"], help="Filter CQs by tier (default: all)")
    p_ch.set_defaults(fn=verb_challenge)

    p_uh = sub.add_parser("update-hypothesis")
    _common(p_uh)
    p_uh.add_argument("--hypothesis-sha", required=True)
    p_uh.add_argument("--status", required=True, choices=["open", "confirmed", "refuted", "dropped"])
    p_uh.add_argument("--evidence-shas", default="")
    p_uh.add_argument("--prev-update-sha", default="")
    p_uh.add_argument("--note", default="")
    p_uh.set_defaults(fn=verb_update_hypothesis)

    return parser


def main() -> None:
    args = _make_parser().parse_args()
    try:
        args.fn(args)
    except SystemExit:
        raise
    except Exception as e:
        _err(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
