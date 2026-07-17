---
name: atam-evaluation
description: Evaluate a software architecture using the Architecture Tradeoff Analysis Method (ATAM). Use when the user asks to "do an ATAM", "evaluate architecture tradeoffs", "build a utility tree", "find architectural risks/sensitivity points/tradeoffs", run an "architecture review", "challenge a finding with critical questions", "audit an evaluation", or wants a structured quality-attribute review of a system. Walks the user through 9 ATAM phases with explicit gates that loud-warn on unchallenged findings, structural-only severities (no measurement evidence), asserting non-risks, and zero-selected-scenario QAs — producing per-phase artifacts and a consolidated report. Includes a Walton critical-questions challenge step, a portfolio audit verb (cryptographic + structural trustworthiness check), and list-evaluations / portfolio-status verbs for cross-evaluation queries. Pulls inputs from architecture docs, source code, measurement evidence (perf logs, incident reports, benchmarks, feedback/), an optional external requirements doc, and interactive stakeholder input.
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
5. **(A1) Measurement evidence** — perf logs, incident reports, benchmarks, a `feedback/` dir, CI timing data, recent perf-tagged commits (`git log --grep -i 'perf\\|slow\\|timeout\\|latency'`). If no measurement evidence exists for a QA that will be rated `high`/`med`, record `STATUS: no measurement evidence for <QA>` in the P0 artifact so the gap is visible at Phase 2, not discovered post-hoc when an incident surfaces. Doc-reading reasons your way to "this should be fast"; only measurement reasons you to "189s `pm status`". For Performance/Scalability/Availability QAs, structural reasoning alone is weaker than the severity implies (see B1 + P9 §A5 gate).
6. **(A6) Documented-vs-observed diff** — when arch docs (or a README) make a property claim ("O(1) head lookup", "constant-time lookup", "horizontally scalable"), explicitly check that claim against incidents, tests, or a quick code-trace before propagating it into Phase 4 approaches. The README is the architect's *claim*; the incident report is what *actually happened*. ATAM should privilege the latter when they conflict.

## Outputs

**(A10) Output location.** By default, write phase artifacts to `./atam-evaluation/` **in the directory where the skill is run** (the evaluator's workspace), NOT into the target repo's root — a new top-level `atam-evaluation/` there would land in the target's next commit. If you must write inside the target repo, put artifacts under a git-ignored path (e.g. alongside `.claude/`), or honor an explicit `--out <dir>`. State the chosen location before writing, and never add the directory to the target's VCS without asking. The hashharness chain is the source of truth; the files are a rendered convenience.

All artifacts go in one directory, one file per phase plus a consolidated report:

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
- **(A2) Per-QA coverage floor:** require **at least one selected scenario per top-level QA**, regardless of (I,D) rating. The (H,H)/(H,M) cut is a useful default, but a whole QA falling below it is a decision the user should make explicitly, not a mechanical side effect. `close-phase --phase 5` warns when any QA has zero selected scenarios — these are exactly the QAs that "the one you rate low-importance is the one a latent measured problem will blindside you on" applies to. Either add a leaf or explicitly waive it in the P5 artifact.

### Phase 6 — Analyze architectural approaches
- For each high-priority leaf from Phase 5:
  - State the scenario (stimulus, environment, response, response measure)
  - Identify the architectural approach(es) addressing it
  - Probe with quality-attribute-specific questions (see `references/probing-questions.md`)
  - Record **risks, non-risks, sensitivity points, tradeoff points**
- **(A4) Run a probe for Performance / Scalability / Availability leaves.** ATAM-as-written is doc-reading + code-reading; that's fine for structural QAs but **insufficient for measured ones** — you cannot read your way to "189s" or "collapses at 6 workers." For any analyzed Perf/Scale/Avail leaf, *write a minimal probe* (a 10-line load script, a `time` invocation, a benchmark) and capture the output as `AtamEvidence kind=measurement`. If the user declines, record the finding's evidence as `structural-only` so the P9 gate can flag it (A5).
- **(A3) Challenge load-bearing non-risks.** A wrong-but-plausible NR ("O(1) fast path", "constant time", "cheap operation") is invisible to every gate that filters on R/TP. When a Phase-4 approach or Phase-6 NR asserts a *property* the analysis leans on, set `--asserts-property` on `record-finding`. The P9 gate then requires the assertion to be challenged like an R/TP — and `record-finding` warns immediately at record-time so the requirement isn't deferred to report time. **(R3) The flag is no longer purely manual:** `record-finding` **auto-promotes** an NR whose title/description contains property-asserting language (`O(1)`, `constant-time`, `fast-path`, `cheap`, `scales`, `indexed`, `guaranteed`, …) — it sets `asserts_property` and loud-warns `A3 AUTO-PROMOTE` — and the P9/audit gate adds an **unflagged-NR backstop** that catches any property-asserting NR that reached the report unflagged *and* unchallenged. Coverage of the incident-proven "wrong O(1) NR" class no longer depends on the evaluator remembering the flag.
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
- **Gate:** final review with user.
- **`close-phase --phase 9` runs five loud-warning checks** (none refuse — they print and proceed):
  1. **§11 challenge gate** — every current high/med R/TP/SP finding must have either a `supersedes` revision or an `AtamEvidence` challenge marker.
  2. **(A3) NR-challenge gate** — every NR with `asserts_property=true` (set manually or by R3 auto-promote) must also be challenged.
  3. **(R3) Unflagged-NR backstop** — every current NR whose *text* asserts a property (`O(1)`, `constant-time`, `scales`, …) but that is unflagged *and* unchallenged is surfaced; catches property claims the flag/auto-promote missed.
  4. **(A5) Structural-only gate** — every current high/med R/TP must cite evidence of kind `measurement | incident | test_result`. Pure `file_ref`/`quote`/`doc` evidence is weaker than the severity implies for measured QAs (see B1 + A1).
  5. A non-empty `qas_zero_selected` list from P5 should already be resolved by P9 (gate proceeds either way).
- Use `cli.py audit --workpackage <wp>` for a one-shot trustworthiness report combining cryptographic + structural checks.

## House rules

- **One gate per phase, no skipping silently.** If the user says "skip", record that in the phase artifact as a known gap.
- **Scenarios must be concrete.** Bad: "system should be fast." Good: "Under 1000 concurrent users, p99 search latency ≤ 300ms on commodity hardware." Enforce the six-part scenario template: *source, stimulus, environment, artifact, response, response measure*.
- **Distinguish the three finding types rigorously:**
  - **Risk** — an architectural decision that may lead to undesirable consequences for a quality attribute
  - **Sensitivity point** — a property of one or more components critical to achieving a particular quality-attribute response
  - **Tradeoff point** — a sensitivity point that affects **more than one** quality attribute, often in opposing directions
- **Cite evidence.** Every risk/sensitivity/tradeoff must reference a specific file, ADR, scenario, or stated decision. No findings from thin air.
- **(B1 / A5) Consequence findings need hard evidence — checked twice.** Before rating an `R`/`TP` finding `high` or `med`, check the Phase-0 measurement sources (perf logs, incident reports, test results) — not only structural reasoning. **At record time, B1**: `record-finding` warns when no evidence of kind `measurement | incident | test_result` is cited. **At report time, A5**: `close-phase --phase 9` lists every current high/med R/TP that remains structural-only as `structural_only_findings`. A structural argument alone is weaker than a high severity implies; either find the measurement or lower the severity. The B1 warning was historically absorbed as "say it and move on" — the A5 gate makes the gap visible *again* at the report boundary.
- **(B3) Gates check claim precision, not just artifact completeness.** When approving a phase gate, don't just confirm the artifact exists — confirm each finding cites the *exact* mechanism, verified in code. A plausible-but-wrong mechanism ("iOS-only because silent-push returns early" when the real cause is a HealthKit-only data source) can pass a completeness check and reach the report. Ask: "is this mechanism the one in the code, or the one that sounds right?"
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

## Companion agent

- `agents/architecture-evaluator.md` — a Claude Code subagent (expert software architect, ATAM-proficient) that drives this skill. It carries the finding-type model, the house rules (measurement-beats-structural, no fabricated drivers, no verdict, artifacts out of the target's VCS), the §11 challenge discipline, and knows to invoke `atam-evaluation` rather than reimplement ATAM. Install by symlinking or copying it into an agents directory Claude Code discovers (`~/.claude/agents/` for global use, or `<repo>/.claude/agents/` per-project), then invoke via the Agent tool with `subagent_type: architecture-evaluator`.

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
    --goal-scope subsystem \
    --goal-target-qas performance,availability,security
# → evaluation_sha, p0_gate_sha, bank_probe_count, warnings[]
#   (warns if the bank has 0 probes — Mode B would be a no-op; use manual mode)

# Build the ontology (A3: create-* verbs — no more raw create_item):
$PY scripts/cli.py create-qa --workpackage "$WP" --evaluation-sha <SHA> \
    --name performance --priority-rank 1                       # → qa_sha
$PY scripts/cli.py create-component --workpackage "$WP" --evaluation-sha <SHA> \
    --name api-gateway --kind component --responsibility "..." # → component_sha
$PY scripts/cli.py create-scenario --workpackage "$WP" --evaluation-sha <SHA> \
    --title "p99 search ≤ 300ms" --qa performance --qa-sha <SHA> \
    --importance H --difficulty M --artifact-shas c1,c2        # → scenario_sha (+rating_sha)
$PY scripts/cli.py create-risk-theme --workpackage "$WP" --evaluation-sha <SHA> \
    --title "..." --member-shas f1,f2 --threatens-shas d1      # → theme_sha
$PY scripts/cli.py create-recommendation --workpackage "$WP" --evaluation-sha <SHA> \
    --title "..." --addresses-theme-sha <SHA> --effort S       # → recommendation_sha

# Per Phase-6/8 tick (Mode B, bank-driven):
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

# --- Portfolio & audit verbs (perf-integration 2026-05-30) ---

# Audit one evaluation: crypto + structural checks combined.
$PY scripts/cli.py audit --workpackage "$WP"
# → trustworthy=true iff: crypto.ok AND no unchallenged R/TP/SP AND no
#   structural-only consequence findings AND no asserting NRs unchallenged
#   AND no QAs with zero selected scenarios.

# Portfolio view across all evaluations in the store:
$PY scripts/cli.py list-evaluations --with-status
# → every atam.case.* wp + its latest PhaseGate (phase/decision/at)
$PY scripts/cli.py portfolio-status --phase 8 --decision approved
# → which evaluations are sitting on an approved P8 (ready for P9 themes)
```

All verbs print `{"ok": true, ...}` JSON. Chain shas across calls. Failures return `{"ok": false, "error": "..."}` and exit 1.

### (A4) Manual mode — record findings without the tick chain

`record-question`, `record-finding`, and `update-coverage` all accept omitted `--decision-sha`/`--question-sha`; when absent they **auto-mint** the `AtamPlan` + `AtamAdaptiveDecision` (+ `ProbingQuestion`) stubs. So when the bank is empty or you're doing a direct code-walk (no adaptive selection), record a finding in one call:

```bash
$PY scripts/cli.py record-finding --workpackage "$WP" \
    --evaluation-sha <SHA> --scenario-sha <SHA> \
    --finding-type R --severity med \
    --title "..." --description "..." --affects-qa-shas qa1 \
    --evidence "file_ref:bot/src/x.py:42:the quoted line" \
    --evidence "measurement:perf-log 2026-05:p99 1.4s"
# → finding_sha, auto-minted question_sha + decision_sha, inline evidence_shas, warnings[]
```

`--evidence kind:pointer:quote` (repeatable) creates the `AtamEvidence` inline — no separate `record-evidence` call needed. The minimal manual chain is just `create-scenario` + `create-qa` once, then one `record-finding` per finding.

### Detection

The skill prefers Mode B when:
1. `mcp__hashharness__get_schema` succeeds and payload contains `AtamBankProbe`, AND
2. `scripts/cli.py` is executable, AND
3. an `AtamInstrumentVersion` exists in `atam.refdata.<version>` (default `atam-v1`), AND
4. that bank has **≥ 1 `AtamBankProbe` record** (mere version presence is not enough — `open-evaluation` counts probes and emits a `warnings[]` entry when zero, in which case Mode B adaptive selection returns closure on every tick and you should use manual mode instead).

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

The `cli.py challenge` verb is self-contained: it detects the Finding's argumentation scheme(s), emits the scheme's CQs (catalog in `references/cq-schemes.md`), and **writes a challenge marker** — an `AtamEvidence` record (`kind=quote`) carrying `attributes.challenged_finding_sha`. That marker is what the P9 gate (below) looks for, so simply running `challenge` on a finding satisfies the gate even if the finding ends up standing pat.

For contested reasoning that warrants an explicit argument graph, hand off to the **`aif-arguments` skill**, which records the exchange as I-nodes (claims), RA-nodes (inference steps), CA-nodes (conflicts/attacks), PA-nodes (preferences) in the same hashharness store. (Note: there is no `IndividualCriticalQuestion` type — a CQ becomes an `AifInode` + an `AifCA` against the finding's `AifRA`.) A challenge exchange is then queryable from both sides: as ATAM Findings with `supersedes` links, and as an AIF argument graph.

**AIF authoring contract — emit canonical premise roles, not ad-hoc names.** When you author the finding's `AifRA`, set `attributes.scheme` to the registry key and `attributes.premise_roles` to that scheme's **canonical Walton roles, in order, one premise per role** (arity). `cli.py challenge` returns this per scheme in its `aif_authoring` block (`scheme_key_to_tag`, `required_premise_roles`, `arity`); the authoritative source is `aif-check-scheme.py --roles <scheme> --format json`. Two gotchas, from a 2026-05-29 audit that found 10/13 ATAM-emitted RAs failing `aif-validate.py [F3]`: (1) this skill's `precedent` is tagged as the registry key **`analogy`**; (2) `cause_to_effect` needs **two** premises (`causal_generalization` + `cause_present`), not a single merged `["cause"]` — see `references/cq-schemes.md` for the full table and the arity/resolution rules.

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
    [--tier-only A B C] \
    [--no-marker]
# → returns scheme(s) detected, the tiered CQ list, evidence summaries,
#   and a challenge_marker_sha (the AtamEvidence the P9 gate detects).
```

The `challenge` verb:
- Detects the Finding's argumentation scheme(s) from its shape (causal language, past-incident citations, sibling references, severity) — override with `--scheme`.
- Returns the CQ list with tiered priorities (A/B/C); `--tier-only A` keeps the exchange brisk.
- **Writes a challenge marker** (`AtamEvidence`, `kind=quote`, `attributes.challenged_finding_sha=<SHA>`) so the P9 gate can tell the finding was challenged even if it stands pat. Pass `--no-marker` for a read-only CQ preview.
- After the exchange: revise via `record-finding --supersedes` (downgrade severity / reframe causality), or let the finding stand (the marker already satisfies the gate).

See `references/cq-schemes.md` for the full Walton catalog (7 schemes, ~24 canonical CQs) and tiering heuristics.

### Close-phase gates (loud warnings at P5 and P9)

`close-phase --phase 5` runs **one** check and `--phase 9` runs **four**. None refuse — they print and proceed.

**At P5:**
- **(A2) `qas_zero_selected`** — QAs with zero selected scenarios. The (H,H)/(H,M) cut is a useful default but a whole QA falling below it is a decision the user should make explicitly. Add a leaf or waive in the artifact.

**At P9** (inspects every *current* / non-superseded Finding):
- **§11 `unchallenged_findings`** — `R`/`TP`/`SP` at `high`/`med` with neither a `supersedes` revision nor a `challenge` marker. ATAM resists a verdict; an un-challenged risk lean is itself a bias.
- **(A3) `asserting_nrs_unchallenged`** — `NR` flagged `--asserts-property` (manually or by R3 auto-promote) that's never been challenged. A wrong "fast-path / O(1) / cheap" claim is the most dangerous class of error — it's invisible to gates that only filter on R/TP unless flagged.
- **(R3) `unflagged_property_nrs`** — `NR` whose *text* asserts a property (`O(1)`, `constant-time`, `scales`, …) but that reached P9 **unflagged and unchallenged**. Backstops the case where auto-promote didn't fire (legacy records, or findings written outside `record-finding`). Challenge each, or supersede if the claim isn't load-bearing.
- **(A5) `structural_only_findings`** — `R`/`TP` at `high`/`med` whose evidence is only `file_ref`/`quote`/`doc`/`adr` (no `measurement`/`incident`/`test_result`). Structural reasoning alone is weaker than the severity implies; either add hard evidence or lower the severity.

```json
{"ok": true, "gate_sha": "...",
 "unchallenged_findings": [...], "asserting_nrs_unchallenged": [...],
 "unflagged_property_nrs": [...], "structural_only_findings": [...], "qas_zero_selected": [],
 "warnings": ["§11 CHALLENGE GATE: N high/med ...", "A3 NR-CHALLENGE GATE: ...",
              "A3 UNFLAGGED-NR BACKSTOP: ...", "A5 STRUCTURAL-ONLY GATE: ..."]}
```

A clean run shows all four lists empty. Use `cli.py audit --workpackage <wp>` for the same four checks combined with a cryptographic verify in one command.

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
- **(B2) The abductive "working-as-designed" CQ is a default theme-time step, not optional.** Every R-high finding should face `comparison_with_alternatives` (CQ13) before it becomes a theme member. ATAM resists a verdict; an un-challenged risk lean is itself a bias. The `challenge` verb auto-includes `abductive` for high-severity R findings.
- **(B4) Run a finding-interaction pass before P9 rollup.** Before theming, ask "do any findings share a root cause?" Cross-link related findings (a long-running job that causes both a perf runaway *and* invisible data stranding is one root, two symptoms). The risk-theme step then clusters by shared cause, not just by surface QA.

---

## Running under pm (guided / assisted / auto execution)

This skill is drivable by the `pm-*-skill-execution` family (`pm-guided-skill-execution`, `pm-assisted-skill-execution`, `pm-auto-skill-execution`). Those drivers call `pm extract-steps atam-evaluation`, which reads the `### Phase N — …` headings under **"Workflow — 9 ATAM phases with gates"** as the canonical step list, then plan one task per phase (chained by `dependsOn`) and execute them under the chosen policy. Invoke, e.g.:

```
pm-guided-skill-execution --skill atam-evaluation --prompt "ATAM of <system> at <scope>"
pm-assisted-skill-execution --skill atam-evaluation --prompt "..."
pm-auto-skill-execution --skill atam-evaluation --prompt "..."     # only for well-scoped, low-stakes runs
```

### Canonical steps (what the extractor will plan)

The nine `### Phase N` headings (P0–P9) plus the §11 challenge sub-step. The extractor's anchors are those heading lines verbatim. Expect ~10 planned tasks for a full run; fewer if the run is endpoint-scoped (see scope note below).

### Per-gate policy table

For each phase gate, the **default decision** is what `auto` picks and what `assisted` picks for routine gates. **Critical** gates pause-and-ask the user *even in assisted and auto* — `auto` should **reject** the task rather than guess; `assisted` pauses, asks, then continues. Never auto-reject a step merely because a decision is required — surface it.

| Phase / gate | Default decision (auto / assisted-routine) | Critical? | Precondition |
|---|---|---|---|
| **P0 Setup** | Inventory inputs (`fd`/`rg` for docs, ADRs, code), record scope. | **CRITICAL** — the system-under-evaluation and its boundaries cannot be guessed. Confirm scope with the user. | A target system/path is identified. |
| **P1 Present ATAM** | Proceed (one-paragraph method summary). | no | — |
| **P2 Business drivers** | **No default.** Drivers must come from the user/stakeholders. | **CRITICAL** — house rule: *never fabricate business drivers.* If the user can't supply them, mark `STATUS: stakeholder input needed` and pause. | P0 done. |
| **P3 Architecture** | Summarize from docs + code inspection. | no (but flag if architecture cannot be derived from available inputs) | P2 done. |
| **P4 Approaches** | Name approaches/tactics from `references/architectural-approaches.md`. | no | P3 done. |
| **P5 Utility tree** | Build leaves; rate (Importance, Difficulty); default-select all (H,H)+(H,M) for analysis. **`close-phase --phase 5` also warns (A2) when any QA has zero selected scenarios** — surface that as a pause-and-ask in guided/assisted. | **CRITICAL** — which leaves to analyze is a prioritization judgment; confirm the selected set with the user. | P2 + at least one scenario per top-3 QA. |
| **P6 Analyze** | Drive the bank loop (`next-probe`→record-question→record-finding→update-coverage) to closure; or manual-mode record-finding if the bank is empty. For Perf/Scale/Avail leaves, **(A4)** prompt for a measurement probe (record output as `kind=measurement`) rather than relying on structural reasoning alone. **(B1)** `record-finding` warns at record-time when a high/med R/TP cites no hard evidence; **(A3)** flag property-asserting NRs with `--asserts-property` so the P9 gate catches them. | no | P5 selected leaves exist. |
| **§11 Challenge** | Challenge **every** high/med R/TP/SP finding (`cli.py challenge`). | **CRITICAL** — never auto-waive a challenge; the abductive "working-as-designed" CQ is mandatory for high-R findings. | At least one high/med finding. |
| **P7 Brainstorm** | Generate use/growth/exploratory scenarios; self-vote if solo. **Auto-skip for endpoint/module scope.** | no | P6 done. |
| **P8 Re-analyze** | Bank loop against the top-voted P7 scenarios. **Auto-skip if P7 skipped.** | no | P7 done. |
| **P9 Themes + report** | Cluster findings into themes (post-challenge set), map to drivers, write recommendations, render `REPORT.md`. `close-phase --phase 9` runs **four gates** (§11 challenge, A3 asserting NRs, R3 unflagged-property-NR backstop, A5 structural-only severities); treat any non-empty list as a pause-and-ask in guided/assisted. `cli.py audit` combines all four with a cryptographic verify for a one-shot trustworthiness verdict. | no (but the P9 gates may produce pause-worthy output) | P8 (or P6 if P7/P8 skipped) done; §11 challenges recorded. |

### Never-auto rules (hold in every mode, including `auto`)

1. **Don't fabricate business drivers** (P2). No driver → pause, even in `auto`.
2. **Don't auto-waive a challenge** (§11). Every high/med finding gets a real CQ pass; record the marker.
3. **Don't auto-skip the abductive / "working-as-designed" CQ** for high-R findings (B2).
4. **Don't auto-waive an A5 structural-only severity** for measured QAs (Perf/Scale/Avail). If `record-finding`'s B1 warning fires and no hard evidence can be added, lower the severity rather than ship the finding at high/med with structural-only support.
5. **Don't auto-skip an A2 zero-selected QA at P5** — a whole QA falling below the analysis cut is a user judgment, not a mechanical outcome.
6. **Don't render a verdict.** ATAM surfaces risks; it does not grade the architecture.
7. **Don't write artifacts into the target repo's VCS** without asking (A10) — default to the evaluator's workspace or a git-ignored path.

### Scope note

Pass the scope in the prompt (`… at endpoint scope` / `… at subsystem scope`) and to `open-evaluation --goal-scope`. For **endpoint** or **module** scope, P7 and P8 carry the documented default **skip** (no brainstorm/re-analysis pass) — the driver plans them but they auto-close as `skipped` with a recorded note. For **subsystem** scope they run normally.

### What a driver should record at each step

Each phase task's report (`pm report`) should cite the hashharness shas it created (PhaseGate, plus the phase's records) so the planning-queue audit trail and the hashharness evaluation chain stay cross-referenced. The `close-phase` gate_sha is the natural proof-of-work artifact for `pm finished`.
