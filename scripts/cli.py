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


def _count_bank_probes(adapter, instrument_version: str) -> int:
    refdata_wp = f"atam.refdata.{instrument_version}"
    return len(
        adapter.find_items(type="AtamBankProbe", work_package_id=refdata_wp, limit=500)
    )


def _ensure_decision(adapter, wp: str, eval_sha: str) -> str:
    """Auto-mint a minimal AtamPlan + AtamAdaptiveDecision for manual-mode recording.
    Returns the decision record_sha256. (A4: removes the hidden next-probe ordering
    contract — record-* verbs can stand alone.)"""
    plans = adapter.find_items(type="AtamPlan", work_package_id=wp, limit=500)
    n = len(plans) + 1
    plan_sha = adapter.create_item(ItemSpec(
        type="AtamPlan", work_package_id=wp, title=f"Plan #{n} (manual)",
        text=f"atam.plan:{wp}.p{n}",
        attributes={"candidate_probes": [], "generated_at": _now_iso(), "mode": "manual"},
        links={"evaluation": eval_sha},
    ))
    dec_sha = adapter.create_item(ItemSpec(
        type="AtamAdaptiveDecision", work_package_id=wp, title=f"Decision #{n} (manual)",
        text=f"atam.decision:{wp}.d{n}",
        attributes={"chosen_probe": None, "source": "manual",
                    "reason": "manual-mode record (auto-minted stub)", "decided_at": _now_iso()},
        links={"plan": plan_sha, "evaluation": eval_sha},
    ))
    return dec_sha


def _ensure_question(adapter, wp: str, eval_sha: str, scenario_sha: str,
                     decision_sha: str, target_qa: str = "",
                     probe_id: str = "manual.record") -> str:
    """Auto-mint a ProbingQuestion stub for manual-mode finding recording."""
    questions = adapter.find_items(type="ProbingQuestion", work_package_id=wp, limit=500)
    n = len(questions) + 1
    return adapter.create_item(ItemSpec(
        type="ProbingQuestion", work_package_id=wp, title=f"Q{n}: {probe_id}",
        text=f"atam.question:{wp}.q{n}",
        attributes={"probe_id": probe_id,
                    "text": "(manual-mode finding; no explicit probe deployed)",
                    "target_qa": target_qa, "probe_kind": "manual", "asked_at": _now_iso()},
        links={"evaluation": eval_sha, "scenario": scenario_sha, "decision": decision_sha},
    ))


def _create_evidence_inline(adapter, wp: str, eval_sha: str, spec_str: str) -> str:
    """Parse a 'kind:pointer:quote' inline-evidence spec and create the AtamEvidence.
    (A5: lets record-finding take evidence inline instead of pre-creating it.)
    'kind' and 'pointer' are required; 'quote' (everything after the 2nd colon) optional."""
    parts = spec_str.split(":", 2)
    kind = parts[0].strip() if parts else "file_ref"
    pointer = parts[1].strip() if len(parts) > 1 else spec_str
    quote = parts[2].strip() if len(parts) > 2 else ""
    evs = adapter.find_items(type="AtamEvidence", work_package_id=wp, limit=500)
    n = len(evs) + 1
    return adapter.create_item(ItemSpec(
        type="AtamEvidence", work_package_id=wp, title=pointer[:60],
        text=f"atam.evidence:{wp}.e{n}",
        attributes={"kind": kind, "pointer": pointer, "quoted_text": quote,
                    "recorded_at": _now_iso()},
        links={"evaluation": eval_sha},
    ))


# Evidence kinds that satisfy the B1 "consequence findings need hard evidence" check
_HARD_EVIDENCE_KINDS = {"measurement", "incident", "test_result"}


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

    # A2: detection that "an AtamInstrumentVersion exists" passes structurally even
    # when the bank has 0 probes. Count probes and warn if Mode B will be a no-op.
    warnings = []
    n_probes = _count_bank_probes(adapter, args.instrument_version)
    if n_probes == 0:
        warnings.append(
            f"Bank '{args.instrument_version}' has 0 AtamBankProbe records — "
            "Mode B adaptive selection will return closure on every tick. "
            "You are effectively in manual-record mode (use record-finding directly; "
            "it auto-mints the plan/decision/question stubs). Seed a probe bank or "
            "pick an instrument-version that has probes."
        )
    _ok(evaluation_sha=eval_sha, p0_gate_sha=p0_sha,
        instrument_version_ref=iv_ref, bank_probe_count=n_probes,
        warnings=warnings)


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
    warnings: list[str] = []
    unchallenged: list[dict] = []

    # A1: at the P8->P9 boundary, surface high/med findings that were never challenged.
    # Loud warning (not refusal): print the list, let the close proceed.
    if args.phase == 9:
        findings = adapter.find_items(type="Finding", work_package_id=args.workpackage, limit=500)
        # Current set = findings not superseded by a newer finding.
        superseded = set()
        for f in findings:
            sup = (f.get("links") or {}).get("supersedes")
            if sup:
                superseded.add(sup)
        # Challenge markers: AtamEvidence whose attributes.challenged_finding_sha names a finding.
        markers = adapter.find_items(type="AtamEvidence", work_package_id=args.workpackage, limit=1000)
        challenged_shas = set()
        for m in markers:
            cf = (m.get("attributes") or {}).get("challenged_finding_sha")
            if cf:
                challenged_shas.add(cf)
        for f in findings:
            sha = f["record_sha256"]
            if sha in superseded:
                continue  # not current
            a = f.get("attributes", {})
            if a.get("finding_type") not in ("R", "TP", "SP"):
                continue
            if a.get("severity") not in ("high", "med"):
                continue
            links = f.get("links") or {}
            is_revision = bool(links.get("supersedes"))  # came from a challenge revision
            is_marked = sha in challenged_shas
            if not (is_revision or is_marked):
                unchallenged.append({"sha": sha, "title": f.get("title", ""),
                                     "severity": a.get("severity"), "type": a.get("finding_type")})
        if unchallenged:
            warnings.append(
                f"§11 CHALLENGE GATE: {len(unchallenged)} high/med finding(s) reach P9 "
                "with no recorded CQ challenge (no supersedes revision and no challenge "
                "marker). ATAM resists a verdict — an unchallenged risk lean is itself a "
                "bias. Run `cli.py challenge --finding-sha <sha>` on each, then either "
                "supersede or attach a challenged-and-survived marker, before relying on "
                "the report. Proceeding anyway (loud-warn mode)."
            )

    gate_sha = controller.close_phase(
        phase=args.phase,
        decision=args.decision,
        note=args.note,
        prev_gate_sha=args.prev_gate_sha,
    )
    _ok(gate_sha=gate_sha, warnings=warnings, unchallenged_findings=unchallenged)


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
    # A4: --decision-sha is optional; auto-mint a manual-mode plan+decision if absent.
    decision_sha = args.decision_sha or _ensure_decision(
        adapter, args.workpackage, args.evaluation_sha
    )
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
            "decision": decision_sha,
            **(
                {"sourceBankProbe": args.source_bank_probe_sha}
                if args.source_bank_probe_sha
                else {}
            ),
        },
    )
    q_sha = adapter.create_item(spec)
    _ok(question_sha=q_sha, question_index=q_index, decision_sha=decision_sha)


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

    # A5: inline evidence. Each --evidence 'kind:pointer:quote' becomes an AtamEvidence
    # created here and linked, so a finding can be recorded in one call.
    inline_kinds: list[str] = []
    for spec_str in (args.evidence or []):
        ev_sha = _create_evidence_inline(adapter, args.workpackage, args.evaluation_sha, spec_str)
        ev_shas.append(ev_sha)
        inline_kinds.append(spec_str.split(":", 1)[0].strip())

    if not ev_shas:
        _err("record-finding needs evidence: pass --evidence-shas and/or --evidence "
             "kind:pointer:quote (≥1). Quote-or-no-finding rule.")

    # A4: --question-sha optional; auto-mint a manual decision+question if absent.
    question_sha = args.question_sha
    decision_sha = None
    if not question_sha:
        decision_sha = _ensure_decision(adapter, args.workpackage, args.evaluation_sha)
        question_sha = _ensure_question(
            adapter, args.workpackage, args.evaluation_sha, args.scenario_sha,
            decision_sha, target_qa=(qa_shas[0] if qa_shas else ""),
        )

    # B1: consequence-bearing findings at high/med severity should cite hard evidence
    # (a measurement, incident, or test result), not only structural/file_ref reasoning.
    warnings: list[str] = []
    if args.finding_type in ("R", "TP") and args.severity in ("high", "med"):
        kinds_present = set(inline_kinds)
        # Inspect any pre-supplied evidence shas for their kind too.
        if args.evidence_shas:
            for ev_sha in _split_csv(args.evidence_shas):
                ev = adapter.get_item_by_hash(ev_sha)
                if ev:
                    kinds_present.add(ev.get("attributes", {}).get("kind", ""))
        if not (kinds_present & _HARD_EVIDENCE_KINDS):
            warnings.append(
                f"B1: {args.finding_type}/{args.severity} finding cites no hard evidence "
                f"(measurement|incident|test_result) — only {sorted(kinds_present) or 'none'}. "
                "Before rating a consequence-bearing finding, check the Phase-0 measurement "
                "sources (perf logs, incident reports, test results). A structural argument "
                "alone is weaker than the severity implies."
            )

    links: dict = {
        "evaluation": args.evaluation_sha,
        "scenario": args.scenario_sha,
        "answeringQuestion": question_sha,
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
    _ok(finding_sha=f_sha, finding_type=args.finding_type,
        evidence_shas=ev_shas, question_sha=question_sha,
        decision_sha=decision_sha, warnings=warnings)


def verb_update_coverage(args) -> None:
    adapter = HashharnessAdapter()
    # A4: --decision-sha optional; auto-mint if absent.
    decision_sha = args.decision_sha or _ensure_decision(
        adapter, args.workpackage, args.evaluation_sha
    )
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
        "decision": decision_sha,
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
    _ok(coverage_sha=cov_sha, decision_sha=decision_sha)


# --------------------------------------------------------------------------- #
# A3: create-* verbs for the rest of the ATAM ontology (QA, component, scenario,
# risk-theme, recommendation). Thin wrappers so the whole graph is reachable from
# one CLI with consistent JSON output, instead of dropping to raw create_item.
# --------------------------------------------------------------------------- #


def verb_create_qa(args) -> None:
    adapter = HashharnessAdapter()
    spec = ItemSpec(
        type="QualityAttribute", work_package_id=args.workpackage,
        title=args.name,
        text=f"atam.qa:{args.workpackage}.{args.name}",
        attributes={"priority_rank": args.priority_rank,
                    "refinements": _split_csv(args.refinements) if args.refinements else []},
        links={"evaluation": args.evaluation_sha,
               **({"motivatedBy": _split_csv(args.motivated_by)} if args.motivated_by else {})},
    )
    _ok(qa_sha=adapter.create_item(spec), title=args.name)


def verb_create_component(args) -> None:
    adapter = HashharnessAdapter()
    comps = adapter.find_items(type="Component", work_package_id=args.workpackage, limit=500)
    n = len(comps) + 1
    spec = ItemSpec(
        type="Component", work_package_id=args.workpackage,
        title=args.name,
        text=f"atam.component:{args.workpackage}.{args.name}",
        attributes={"kind": args.kind, "responsibility": args.responsibility},
        links={"evaluation": args.evaluation_sha,
               **({"partOf": args.part_of} if args.part_of else {})},
    )
    _ok(component_sha=adapter.create_item(spec), title=args.name)


def verb_create_scenario(args) -> None:
    adapter = HashharnessAdapter()
    scens = adapter.find_items(type="Scenario", work_package_id=args.workpackage, limit=500)
    n = len(scens) + 1
    links: dict = {"evaluation": args.evaluation_sha}
    if args.qa_sha:
        links["qualityAttribute"] = args.qa_sha
    if args.artifact_shas:
        links["stimulatesArtifact"] = _split_csv(args.artifact_shas)
    if args.supersedes:
        links["supersedes"] = args.supersedes
    spec = ItemSpec(
        type="Scenario", work_package_id=args.workpackage,
        title=args.title,
        text=f"atam.scenario:{args.workpackage}.s{n}",
        attributes={"qa": args.qa, "category": args.category,
                    "source": args.source, "stimulus": args.stimulus,
                    "environment": args.environment, "artifact_label": args.artifact_label,
                    "response": args.response, "response_measure": args.response_measure,
                    "phase_introduced": args.phase_introduced},
        links=links,
    )
    scenario_sha = adapter.create_item(spec)
    out = {"scenario_sha": scenario_sha}
    # Inline rating (the selector needs selected_for_analysis + I/D to consider a scenario).
    if args.importance or args.difficulty:
        ratings = adapter.find_items(type="ScenarioRating", work_package_id=args.workpackage, limit=1000)
        rn = len(ratings) + 1
        rating_sha = adapter.create_item(ItemSpec(
            type="ScenarioRating", work_package_id=args.workpackage,
            title=f"Rating s{n} ({args.importance},{args.difficulty})",
            text=f"atam.rating:{args.workpackage}.s{n}-r1",
            attributes={"importance": args.importance or "M", "difficulty": args.difficulty or "M",
                        "selected_for_analysis": not args.not_selected,
                        "rationale": args.rating_rationale, "phase": args.phase_introduced},
            links={"scenario": scenario_sha},
        ))
        out["rating_sha"] = rating_sha
    _ok(**out)


def verb_create_risk_theme(args) -> None:
    adapter = HashharnessAdapter()
    themes = adapter.find_items(type="RiskTheme", work_package_id=args.workpackage, limit=500)
    n = len(themes) + 1
    links: dict = {"evaluation": args.evaluation_sha}
    if args.member_shas:
        links["members"] = _split_csv(args.member_shas)
    if args.threatens_shas:
        links["threatens"] = _split_csv(args.threatens_shas)
    spec = ItemSpec(
        type="RiskTheme", work_package_id=args.workpackage,
        title=args.title,
        text=f"atam.theme:{args.workpackage}.t{n}",
        attributes={"description": args.description, "severity": args.severity,
                    "rank": args.rank, "phase": "P9"},
        links=links,
    )
    _ok(theme_sha=adapter.create_item(spec), title=args.title)


def verb_create_recommendation(args) -> None:
    adapter = HashharnessAdapter()
    recs = adapter.find_items(type="Recommendation", work_package_id=args.workpackage, limit=500)
    n = len(recs) + 1
    links: dict = {"evaluation": args.evaluation_sha}
    if args.addresses_theme_sha:
        links["addresses"] = args.addresses_theme_sha
    spec = ItemSpec(
        type="Recommendation", work_package_id=args.workpackage,
        title=args.title,
        text=f"atam.recommendation:{args.workpackage}.r{n}",
        attributes={"description": args.description, "effort": args.effort,
                    "owner_role": args.owner_role, "priority": args.priority, "phase": "P9"},
        links=links,
    )
    _ok(recommendation_sha=adapter.create_item(spec), title=args.title)


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


# AIF authoring contract (from aif-arguments feedback, 2026-05-29).
# When the challenge hand-off authors an AifRA for a finding, the node's
# attributes.scheme must be the registry KEY below, and attributes.premise_roles
# must be the required_roles verbatim and in order — one premise per role (arity).
# Ad-hoc roles like ["cause"]/["observation"] fail aif-validate.py's [F3] check.
#
# AUTHORITATIVE SOURCE is the aif-arguments JSON contract, not this table:
#   aif-check-scheme.py --roles <scheme_key> --format json   → {required_roles, ...}
# This table mirrors it as of 2026-05-29 for the 7 schemes ATAM tags; verify
# against the CLI if the registry has changed.
#
# Note: this skill's "precedent" maps to the registry key "analogy".
SCHEME_REGISTRY_KEY = {
    "negative_consequences": "negative_consequences",
    "cause_to_effect": "cause_to_effect",
    "sign": "sign",
    "evidence_to_hypothesis": "evidence_to_hypothesis",
    "abductive": "abductive",
    "precedent": "analogy",
    "practical_reasoning": "practical_reasoning",
}
SCHEME_PREMISE_ROLES = {
    "negative_consequences": ["action", "bad_consequence"],
    "cause_to_effect": ["causal_generalization", "cause_present"],
    "sign": ["sign_observed", "sign_indicates"],
    "evidence_to_hypothesis": ["hypothesis_predicts", "observation"],
    "abductive": ["data", "best_explanation"],
    "analogy": ["base_case", "similarity"],
    "practical_reasoning": ["goal", "means"],
}


def _aif_authoring_for(scheme: str) -> dict:
    """Return the AifRA authoring contract for a CQ scheme: the registry key to
    tag, the required premise_roles (in order), and the arity (one premise per role)."""
    key = SCHEME_REGISTRY_KEY.get(scheme, scheme)
    roles = SCHEME_PREMISE_ROLES.get(key, [])
    return {
        "scheme_key_to_tag": key,
        "required_premise_roles": roles,
        "arity": len(roles),
        "note": (
            f"Author one AifInode premise per role ({len(roles)} premises), set "
            f"AifRA.attributes.premise_roles={roles} in this order, and "
            f"attributes.scheme='{key}'. Authoritative: "
            f"aif-check-scheme.py --roles {key} --format json."
        ),
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

    # A1: write a challenge marker so the P9 gate can tell this finding WAS challenged
    # (even if it ends up standing pat with no supersedes revision). The marker is an
    # AtamEvidence whose attributes.challenged_finding_sha names the target.
    marker_sha = None
    if not args.no_marker:
        eval_items = adapter.find_items(type="AtamEvaluation", work_package_id=args.workpackage)
        eval_sha = eval_items[0]["record_sha256"] if eval_items else None
        markers = adapter.find_items(type="AtamEvidence", work_package_id=args.workpackage, limit=1000)
        mn = len(markers) + 1
        marker_sha = adapter.create_item(ItemSpec(
            type="AtamEvidence", work_package_id=args.workpackage,
            title=f"cq-challenge: {target.get('title','')[:48]}",
            text=f"atam.evidence:{args.workpackage}.cq-marker-{mn}",
            attributes={"kind": "quote",
                        "pointer": f"cq-challenge-marker:{args.finding_sha}",
                        "challenged_finding_sha": args.finding_sha,
                        "schemes": schemes,
                        "quoted_text": "Challenge initiated; CQs emitted for operator/LLM to answer. "
                                       "Revise via record-finding --supersedes, or let the finding stand "
                                       "(this marker records that it was challenged).",
                        "recorded_at": _now_iso()},
            links={"evaluation": eval_sha} if eval_sha else {},
        ))

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
        challenge_marker_sha=marker_sha,
        aif_authoring={s: _aif_authoring_for(s) for s in schemes},
        next_step=(
            "Answer the Tier-A CQs. For productive critiques, use 'record-finding --supersedes' "
            "to revise (downgrade severity / reframe causality). If the finding stands, this "
            "challenge marker already records that it was challenged (satisfies the P9 gate). "
            "If you build the AIF graph via aif-arguments: tag AifRA.attributes.scheme with the "
            "registry key in aif_authoring[scheme].scheme_key_to_tag, set premise_roles to "
            "required_premise_roles verbatim/in-order, and supply one AifInode premise per role "
            "(arity) — ad-hoc roles fail aif-validate.py [F3]. When a CQ is decided, optionally "
            "mint an AifPA(preferred, dispreferred) so the resolution isn't read as open [D1]."
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
    p_rq.add_argument("--decision-sha", default="", help="Optional; auto-minted if omitted (manual mode).")
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
    p_rf.add_argument("--question-sha", default="", help="Optional; auto-mints a manual decision+question stub if omitted (A4).")
    p_rf.add_argument("--scenario-sha", required=True)
    p_rf.add_argument("--approach-sha", default="")
    p_rf.add_argument("--finding-type", required=True, choices=["R", "NR", "SP", "TP"])
    p_rf.add_argument("--title", required=True)
    p_rf.add_argument("--description", required=True)
    p_rf.add_argument("--evidence-shas", default="", help="Comma-sep pre-created AtamEvidence shas.")
    p_rf.add_argument("--evidence", action="append", default=[], help="Inline evidence 'kind:pointer:quote', repeatable (A5). Created and linked in this call.")
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
    p_uc.add_argument("--decision-sha", default="", help="Optional; auto-minted if omitted (manual mode).")
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
    p_ch.add_argument("--no-marker", action="store_true", help="Don't write the challenge marker (read-only CQ preview).")
    p_ch.set_defaults(fn=verb_challenge)

    # --- A3: create-* verbs for the rest of the ontology ---
    p_cq = sub.add_parser("create-qa")
    _common(p_cq)
    p_cq.add_argument("--evaluation-sha", required=True)
    p_cq.add_argument("--name", required=True, help="Canonical QA name (performance, security, ...)")
    p_cq.add_argument("--priority-rank", type=int, default=99)
    p_cq.add_argument("--refinements", default="")
    p_cq.add_argument("--motivated-by", default="", help="Comma-sep BusinessDriver shas")
    p_cq.set_defaults(fn=verb_create_qa)

    p_cc = sub.add_parser("create-component")
    _common(p_cc)
    p_cc.add_argument("--evaluation-sha", required=True)
    p_cc.add_argument("--name", required=True)
    p_cc.add_argument("--kind", default="component", choices=["component", "connector", "deployment-unit", "data-store", "external-dependency", "trust-boundary", "bounded-context"])
    p_cc.add_argument("--responsibility", default="")
    p_cc.add_argument("--part-of", default="", help="Parent Component sha")
    p_cc.set_defaults(fn=verb_create_component)

    p_cs = sub.add_parser("create-scenario")
    _common(p_cs)
    p_cs.add_argument("--evaluation-sha", required=True)
    p_cs.add_argument("--title", required=True)
    p_cs.add_argument("--qa", required=True, help="QA name string stamped on the scenario")
    p_cs.add_argument("--qa-sha", default="", help="QualityAttribute record sha to link")
    p_cs.add_argument("--category", default="anticipated", choices=["anticipated", "use", "growth", "exploratory"])
    p_cs.add_argument("--source", default="")
    p_cs.add_argument("--stimulus", default="")
    p_cs.add_argument("--environment", default="")
    p_cs.add_argument("--artifact-label", default="")
    p_cs.add_argument("--artifact-shas", default="", help="Comma-sep Component shas (stimulatesArtifact)")
    p_cs.add_argument("--response", default="")
    p_cs.add_argument("--response-measure", default="")
    p_cs.add_argument("--phase-introduced", default="P5")
    p_cs.add_argument("--supersedes", default="")
    # inline rating
    p_cs.add_argument("--importance", default="", choices=["", "H", "M", "L"])
    p_cs.add_argument("--difficulty", default="", choices=["", "H", "M", "L"])
    p_cs.add_argument("--not-selected", action="store_true", help="Mark selected_for_analysis=false")
    p_cs.add_argument("--rating-rationale", default="")
    p_cs.set_defaults(fn=verb_create_scenario)

    p_crt = sub.add_parser("create-risk-theme")
    _common(p_crt)
    p_crt.add_argument("--evaluation-sha", required=True)
    p_crt.add_argument("--title", required=True)
    p_crt.add_argument("--description", default="")
    p_crt.add_argument("--severity", default="med", choices=["high", "med", "low"])
    p_crt.add_argument("--rank", type=int, default=99)
    p_crt.add_argument("--member-shas", default="", help="Comma-sep Finding shas")
    p_crt.add_argument("--threatens-shas", default="", help="Comma-sep BusinessDriver shas")
    p_crt.set_defaults(fn=verb_create_risk_theme)

    p_crr = sub.add_parser("create-recommendation")
    _common(p_crr)
    p_crr.add_argument("--evaluation-sha", required=True)
    p_crr.add_argument("--title", required=True)
    p_crr.add_argument("--description", default="")
    p_crr.add_argument("--effort", default="M", help="S | M | L | S-M etc.")
    p_crr.add_argument("--owner-role", default="")
    p_crr.add_argument("--priority", type=int, default=99)
    p_crr.add_argument("--addresses-theme-sha", default="")
    p_crr.set_defaults(fn=verb_create_recommendation)

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
