---
name: atam-evaluation
description: Evaluate a software architecture using the Architecture Tradeoff Analysis Method (ATAM). Use when the user asks to "do an ATAM", "evaluate architecture tradeoffs", "build a utility tree", "find architectural risks/sensitivity points/tradeoffs", or wants a structured quality-attribute review of a system. Walks the user through all 9 ATAM phases step-by-step with explicit gates, producing per-phase artifacts (business drivers, architecture summary, approaches, utility tree, scenarios, analysis, risk themes) and a final consolidated report. Pulls inputs from architecture docs, source code, an optional external requirements doc, and interactive stakeholder input.
---

# ATAM Evaluation

Run the **Architecture Tradeoff Analysis Method** (Kazman, Klein, Clements — SEI) against a target system. ATAM finds **risks**, **sensitivity points**, and **tradeoff points** by mapping the architecture against prioritized quality-attribute scenarios.

This skill is **step-by-step with user gates**: after each phase you pause, surface the artifact, and wait for the user to confirm or revise before continuing.

## When to use

Trigger when the user asks for any of:
- "Run an ATAM" / "evaluate this architecture" / "architecture tradeoff analysis"
- Building a **utility tree** of quality attributes
- Identifying **risks, non-risks, sensitivity points, tradeoff points**
- Quality-attribute scenario analysis (performance, availability, security, modifiability, etc.)
- Pre-launch architecture review of a non-trivial system

Do **not** use for: simple code review, single-file refactors, or pure functional-requirement reviews. ATAM is about *quality attributes* and *architectural decisions*, not feature correctness.

## Inputs

Collect in Phase 0 (Setup), in this priority order:
1. **Architecture docs** in the repo — ADRs, C4 diagrams, design docs (`fd -e md` then `rg "architecture|ADR|C4"`)
2. **Source code** — top-level layout, module boundaries, key dependencies
3. **External requirements doc** — ask user for path if not obvious
4. **Interactive stakeholder input** — business drivers, priorities, constraints (always required; the user *is* the stakeholder proxy unless they name others)

## Outputs

All artifacts written to `./atam-evaluation/` in the target project, one file per phase plus a consolidated report:

```
atam-evaluation/
├── 00-setup.md              # scope, stakeholders, inputs found
├── 01-business-drivers.md   # business goals, constraints, top quality attributes
├── 02-architecture.md       # architecture summary as presented
├── 03-approaches.md         # identified architectural approaches / styles / patterns
├── 04-utility-tree.md       # quality attribute utility tree (prioritized H/M/L × H/M/L)
├── 05-analysis.md           # per-scenario analysis of high-priority leaves
├── 06-scenarios.md          # brainstormed scenarios (use, growth, exploratory)
├── 07-reanalysis.md         # re-analysis against newly prioritized scenarios
├── 08-risk-themes.md        # risk themes + recommendations
└── REPORT.md                # consolidated final report
```

If the directory already exists, ask before overwriting.

## Workflow — 9 ATAM phases with gates

Each phase: **(a)** do the work, **(b)** write the artifact, **(c)** show the user a concise summary, **(d)** ask "approve / revise / skip" before moving on. Do not silently chain phases.

### Phase 0 — Setup (pre-ATAM)
- Confirm the system under evaluation and its boundaries
- Inventory inputs (run `fd`, `rg` to find docs/ADRs; ask for requirements doc path)
- Identify stakeholders (or confirm user is acting as proxy)
- Write `00-setup.md`
- **Gate:** confirm scope before proceeding

### Phase 1 — Present ATAM
- Briefly explain the method to the user (one paragraph + the 4 key concepts: quality attribute, scenario, risk/sensitivity/tradeoff, utility tree)
- Use `references/atam-method.md` for the canonical summary
- **Gate:** user confirms they want to proceed

### Phase 2 — Present business drivers
- Elicit: system purpose, primary business goals, major stakeholders, constraints (cost/schedule/regulatory), top 3–5 quality attribute drivers
- Use `templates/business-drivers.md`
- Write `01-business-drivers.md`
- **Gate:** confirm drivers and priorities

### Phase 3 — Present architecture
- Summarize the architecture: technical constraints, other systems it interacts with, architectural approaches used (layered, microservices, event-driven, CQRS, etc.)
- Pull from docs + code inspection
- Write `02-architecture.md`
- **Gate:** confirm summary is accurate

### Phase 4 — Identify architectural approaches
- Name the approaches/styles/patterns in use (do not yet analyze them)
- Reference `references/architectural-approaches.md` for the catalog
- Write `03-approaches.md`
- **Gate:** confirm list is complete

### Phase 5 — Generate quality attribute utility tree
- Build a tree: root = "utility" → quality attributes (performance, availability, security, modifiability, usability, testability, deployability, …) → refinements → **scenarios** at leaves
- Each leaf scenario gets two ratings: **(Importance, Difficulty)** each H/M/L
- Use `templates/utility-tree.md` and `references/quality-attributes.md`
- Write `04-utility-tree.md`
- **Gate:** user prioritizes leaves; agree on which (H,H) and (H,M) leaves to analyze

### Phase 6 — Analyze architectural approaches
- For each high-priority leaf from Phase 5:
  - State the scenario (stimulus, environment, response, response measure)
  - Identify the architectural approach(es) addressing it
  - Probe with quality-attribute-specific questions (see `references/probing-questions.md`)
  - Record **risks, non-risks, sensitivity points, tradeoff points**
- Use `templates/analysis.md`
- Write `05-analysis.md`
- **Gate:** review findings; user may add probes

### Phase 7 — Brainstorm and prioritize scenarios
- With stakeholders, generate scenarios in three categories: **use case**, **growth**, **exploratory** (stress)
- Prioritize by vote (or user judgment if solo)
- Write `06-scenarios.md`
- **Gate:** agree on top scenarios for re-analysis

### Phase 8 — Analyze architectural approaches (again)
- Repeat Phase 6 against the newly-prioritized scenarios from Phase 7
- Focus on scenarios not already covered by the utility tree
- Write `07-reanalysis.md`
- **Gate:** review

### Phase 9 — Present results
- Consolidate **risk themes** (groups of related risks pointing at a systemic issue)
- Map themes back to business drivers (which goal does each threaten?)
- Produce actionable **recommendations**
- Write `08-risk-themes.md` and `REPORT.md`
- **Gate:** final review with user

## House rules

- **One gate per phase, no skipping silently.** If the user says "skip", record that in the phase artifact as a known gap.
- **Scenarios must be concrete.** Bad: "system should be fast." Good: "Under 1000 concurrent users, p99 search latency ≤ 300ms on commodity hardware." Enforce the six-part scenario template: *source, stimulus, environment, artifact, response, response measure*.
- **Distinguish the three finding types rigorously:**
  - **Risk** — an architectural decision that may lead to undesirable consequences for a quality attribute
  - **Sensitivity point** — a property of one or more components critical to achieving a particular quality-attribute response
  - **Tradeoff point** — a sensitivity point that affects **more than one** quality attribute, often in opposing directions
- **Cite evidence.** Every risk/sensitivity/tradeoff must reference a specific file, ADR, scenario, or stated decision. No findings from thin air.
- **Don't invent business drivers.** If the user can't supply them, mark the artifact `STATUS: stakeholder input needed` and stop — do not fabricate goals.
- **Don't grade the architecture.** ATAM finds risks; it doesn't score "good/bad". Resist the urge to render a verdict.

## Reference material

- `references/atam-method.md` — method summary, the 9 steps, finding-type definitions
- `references/entities.md` — **canonical ontology** of every term used across phases (roles, objects, decisions, qualities, artifacts, scenario parts, findings, relationships). Use these terms verbatim in artifacts so the final report is consistent.
- `references/entity-lifecycle.md` — **how entities evolve across phases**: what's born, what attributes accrete, what links form, key state transitions (SP→TP, etc.), per-phase completeness gates. Consult before closing each phase gate.
- `references/hashharness-mapping.md` — how ATAM entities map to hashharness records: per-type attribute conventions, phase → records cheat sheet, example queries, and the merge-before-push rule.
- `schemas/hashharness-schema.json` — the schema payload (types + links) ready to merge into a live hashharness head via `set_schema`.
- `references/quality-attributes.md` — ISO 25010 + classic ATAM QA taxonomy with scenario examples
- `references/architectural-approaches.md` — catalog of styles/tactics (layered, microservices, event-driven, redundancy, caching, etc.)
- `references/probing-questions.md` — per-QA question banks used in Phase 6/8

## Templates

- `templates/business-drivers.md`
- `templates/utility-tree.md`
- `templates/scenario.md` — six-part scenario form
- `templates/analysis.md` — per-scenario analysis with R/SP/TP slots
- `templates/report.md` — final consolidated report skeleton

---

## Adaptive control (Mode B — controller CLI)

When hashharness is available **and** `scripts/cli.py` is executable, prefer Mode B for **Phase 6 and Phase 8** (the analysis phases). The controller turns Phase 6/8 from a hand-driven Q&A loop into an adaptive, audit-trailed selection problem — same pattern as `psyinterviewer/stipo-r`.

### What the controller does at each tick

```
state  =  reconstruct from records:
            scenarios (Scenario + latest ScenarioRating)
            coverage  (latest AtamCoverage per scenario)
            hypotheses (AtamHypothesis whose latest AtamHypothesisUpdate ≠ refuted/dropped)
            deployed_probe_ids (from ProbingQuestion records so far)

candidates  =  AtamBankProbe records filtered by applies_when + prerequisites
                + risk_level ≤ allowed_risk_level
                − already deployed

priority_order:
  1.  open hypothesis     → bank "discriminator" probe targeting its id
  2.  uncovered scenario  → bank "standard" probe, argmax of
                             expected_saturation_gain / estimated_time_minutes
                             scaled 1.5× if target_qa matches an uncovered scenario's QA
                             gated by BANK_PREFERRED_GAIN_THRESHOLD = 0.35
  3.  generation fallback → LLM-generated AtamProbeCandidate → AtamProbeCritique
                             quality gate: score ≥ 0.5, verdict = "select"
  4.  fallback-bank       → if generation gate fails, take best bank standard
  5.  closure             → no uncovered scenarios and no open hypotheses

Always emit:  AtamPlan (candidates considered) + AtamAdaptiveDecision (chosen + reason).
If generation fired: AtamProbeCandidate + AtamProbeCritique × K.
```

### CLI verbs (`scripts/cli.py`)

```bash
PY=/Users/a.morozov/.hashharness/venv/bin/python
WP="atam.case.<system>-$(date +%s)"

# Open evaluation (writes AtamEvaluation + PhaseGate(0))
$PY scripts/cli.py open-evaluation --workpackage "$WP" \
    --system "checkout-svc" --evaluator "AI+lead-architect" \
    --instrument-version atam-v1 \
    --goal-target-qas performance,availability,security
# → evaluation_sha, p0_gate_sha

# Per Phase-6/8 tick:
$PY scripts/cli.py next-probe --workpackage "$WP" --phase 6
# → chosen_probe, source, plan_sha, decision_sha
# Then: ask the question. Capture the answer.

$PY scripts/cli.py record-question --workpackage "$WP" \
    --evaluation-sha <SHA> --decision-sha <SHA> --scenario-sha <SHA> \
    --probe-id "perf.cache-strategy" --probe-text "<verbatim>" \
    --target-qa performance --source-bank-probe-sha <SHA>
# → question_sha

$PY scripts/cli.py record-evidence --workpackage "$WP" \
    --evaluation-sha <SHA> --kind adr --pointer "ADR-007 §3" \
    --quoted-text "<excerpt>"
# → evidence_sha   (repeat per evidence)

$PY scripts/cli.py record-finding --workpackage "$WP" \
    --evaluation-sha <SHA> --question-sha <SHA> --scenario-sha <SHA> \
    --finding-type TP --title "Cache TTL latency↔freshness" \
    --description "..." \
    --evidence-shas e1,e2 --affects-qa-shas qa1,qa2
# → finding_sha (R | NR | SP | TP)

$PY scripts/cli.py update-coverage --workpackage "$WP" \
    --evaluation-sha <SHA> --scenario-sha <SHA> --decision-sha <SHA> \
    --status in-progress --saturation 0.4 --findings-count 1
# → coverage_sha

# Form a hunch — opens an AtamHypothesis the selector will discriminate on next tick:
$PY scripts/cli.py open-hypothesis --workpackage "$WP" \
    --evaluation-sha <SHA> --scenario-sha <SHA> \
    --claim "Postgres SoT is a SPOF and dominant scaling bottleneck" \
    --discriminating-question "What is the documented RTO, and when was failover last tested?" \
    --relevant-qas availability,scalability

# Close out a hypothesis:
$PY scripts/cli.py update-hypothesis --workpackage "$WP" \
    --hypothesis-sha <SHA> --status confirmed \
    --evidence-shas e3,e4

# Close phase gate:
$PY scripts/cli.py close-phase --workpackage "$WP" --phase 6 \
    --decision approved --prev-gate-sha <SHA> --note "Top-priority leaves analyzed."
```

All verbs print `{"ok": true, ...}` JSON. Chain shas across calls. Failures return `{"ok": false, "error": "..."}` and exit 1.

### Detection

The skill prefers Mode B when:
1. `mcp__hashharness__get_schema` succeeds and payload contains `AtamBankProbe`, AND
2. `scripts/cli.py` is executable, AND
3. an `AtamInstrumentVersion` exists in `atam.refdata.<version>` (default `atam-v1`).

Otherwise fall back to **Mode A** (direct MCP calls; LLM drives `create_item` itself) or further fall back to file-only mode (artifact-driven, no audit trail).

### Adaptive-control records (the new types added in schema v6)

| Type | Purpose |
|------|---------|
| `AtamInstrumentVersion` | Versioned probe bank metadata |
| `AtamBankProbe` | One vetted probing question in the bank (refdata workpackage) |
| `AtamPlan` | Candidates considered this tick |
| `AtamAdaptiveDecision` | Chosen probe + reason + alternatives + bankProbe link |
| `AtamProbeCandidate` | LLM-generated probe text (case-local) |
| `AtamProbeCritique` | Quality score on a candidate; six-axis breakdown |
| `AtamProbeOutcome` | Observed vs estimated time/yield; calibrates the bank over time |
| `AtamCoverage` | Saturation per scenario (`untouched | in-progress | sufficient | saturated`) with gaps & findings_count |
| `AtamHypothesis` | A risk hunch with a discriminating question — biases probe selection |
| `AtamHypothesisUpdate` | Status transitions citing evidence; append-only chain |

See `references/hashharness-mapping.md` for per-type attribute conventions.

### The revision discipline still applies

- **Findings & Evidence are immutable.** Corrections = new Finding + supersedes-link.
- **Coverage is append-only** via `previous` link; latest wins for state assembly.
- **Hypothesis status transitions** via dedicated `AtamHypothesisUpdate` records — never by mutating the original `AtamHypothesis`.
- **Parallel `create_item` responses don't preserve submission order.** The Python adapter binds shas to roles by record `text`, not position (`scripts/mcp_adapter.py:create_items_parallel`). When you must call MCP directly, query back by attribute (e.g., `probe_id`) to map shas — don't rely on response order.

---

## §11 — Critical-questions challenge step (between P8 close and P9 themes)

A separate, optional, but **strongly recommended** sub-phase between the close of P8 and the opening of P9. The goal: force every load-bearing Finding (severity high or med) through a Walton critical-questions review *before* themes are rolled up. Findings that survive the challenge enter P9 with stronger provenance; findings that don't get revised, downgraded, or withdrawn before they propagate into recommendations.

### When to invoke

- **Default:** after `close-phase --phase 8 --decision approved`, run a CQ pass on every R-high and R-med Finding. R-low and NR can be skipped unless flagged.
- **On-demand:** any time after P6 — especially when a Finding lights up a structural objection in code review (the F18/F16R style of late-arriving insight).
- **External challenge:** when an outside reviewer (or the user) supplies a CQ list, route it through this step rather than treating it as commentary.

### What this step uses

Integrates with the **`aif-arguments` skill**, which:
- Builds an AIF argument graph from a Finding's claim + evidence + inference structure
- Identifies the Walton argumentation scheme(s) the Finding invokes (catalog in `references/cq-schemes.md`)
- Generates the scheme's canonical CQs as `IndividualCriticalQuestion` nodes
- Records the exchange as I-nodes (claims), RA-nodes (inference steps), CA-nodes (conflicts/attacks), PA-nodes (preferences) — all in the same hashharness store as the ATAM records

So a challenge exchange becomes queryable from both sides: as ATAM Findings with `supersedes` links, and as an AIF argument graph.

### Process

```
For each Finding F (high/med severity):

  1. aif-arguments builds the argument graph for F:
       I-node: F.title (the claim)
       I-nodes: F's linked evidence + the affected QA + the locus components
       RA-node: F's inferential step (claim from evidence)
       scheme: derived from F's shape (cause_to_effect | sign | evidence_to_hypothesis | precedent | abductive)

  2. aif-arguments emits the scheme's CQ list as IndividualCriticalQuestion nodes
     attached to the RA-node.

  3. The evaluator (LLM, human, or both) tiers the CQs A/B/C
     and answers Tier A productively.

  4. For each CQ answered:
       - If it lands: create a CA-node (conflict) attacking the RA-node,
         with the conceded reasoning as the attacker.
       - If it doesn't land: record a brief defense (also a CA-node, but
         pointing the other way — the Finding's defense against the CQ).

  5. Productive CA-nodes drive one of three outcomes:
       a) Stand-pat: Finding stands as written. Defense is recorded.
       b) Revise: emit Finding' with `supersedes: F`, carrying the
          reframing, severity adjustment, or causal correction the CQ
          revealed. The original F remains queryable.
       c) Withdraw: emit Finding' with `supersedes: F` and type=NR
          (non-risk) with `promotion_reason` documenting why the
          challenge succeeded.

  6. Optionally promote one or more Recommendations: practical_reasoning
     CQs (other_means, side_effects, possibility) often split a single
     Recommendation into a cheaper-and-now + deeper-and-later pair
     (e.g. R4 → R4a + R4b in this skill's worked example).
```

### CLI verb

```bash
$PY scripts/cli.py challenge --workpackage "$WP" \
    --finding-sha <SHA> \
    [--scheme cause_to_effect|sign|evidence_to_hypothesis|precedent|abductive|negative_consequences|practical_reasoning] \
    [--from-aif-graph <I_NODE_SHA>]
# → returns the CQ list and an `aif_graph_sha` for the constructed argument graph.
```

The `challenge` verb:
- Delegates argument-graph construction to `aif-arguments` (via Skill invocation or MCP)
- Returns the CQ list with tiered priorities (A/B/C based on the scheme and the finding's structure)
- After the human/LLM exchange, records each productive CQ as an `AtamEvidence` (kind=`quote`) pointing at the AIF graph for the full conversation
- If a revision is committed, the `supersedes` Finding links its `promotion_reason` to the AIF graph sha for provenance

See `references/cq-schemes.md` for the full Walton catalog (7 schemes, ~24 canonical CQs) and tiering heuristics.

### When to skip

- The Finding is a non-risk (NR) — challenge is wasted effort.
- The Finding is severity=low and has only one evidence record — challenge cost exceeds expected revision value.
- The Finding has already been challenged and survived (recorded in chain via an `AtamEvidence` of kind=`quote` citing prior CQ exchange). Re-challenging requires new evidence.

### House rules

- **Default to engaging**, not deflecting. The CQ exchange should land hits where the original reasoning was loose.
- **Concede explicitly.** If `alternative_reason_for_observation` lands, record a CA-node and revise — don't paper over with extra qualifications on the original Finding.
- **Tier A or skip.** Don't perform a procedural CQ pass that ticks all 24 questions without engagement; that's bureaucracy, not challenge.
- **Recommendation splits are common.** `practical_reasoning` CQs (`other_means`, `side_effects`) frequently surface a cheaper "do-now" companion to a heavier "do-later" recommendation. The audit chain accommodates both via separate `Recommendation` records.
- **Themes (P9) are rolled up from the *post-challenge* finding set.** Run challenge first; theme membership uses the revised severities and superseding records.
