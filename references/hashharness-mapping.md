# Hashharness Mapping — ATAM as an Append-Only Record Graph

The schema in `schemas/hashharness-schema.json` declares only **types** and **inter-record links**. Per-record **attributes** are free-form JSON; their conventions are documented below so the graph stays consistent and queryable across evaluations.

## Conventions

- **One evaluation = one `work_package_id`.** Use a slug: `atam-<YYYY-MM-DD>-<system>`, e.g. `atam-2026-05-26-checkout`.
- **Every typed record links to `AtamEvaluation` via `evaluation`** — gives single-record entry point and lets you bound queries.
- **All time-varying state is append-only.** Mutating-looking concepts (re-rating a scenario, promoting SP→TP) are modeled as a *new* record with a `replaces` / `supersedes` link to its predecessor.
- **`PhaseGate` is chained** (`chain_predecessor: true`). The chain *is* the audit trail of the evaluation's progress.
- **Every finding must link to ≥ 1 `Evidence`.** The schema doesn't enforce this — the skill workflow does at phase gates.

## Type-by-type record conventions

### AtamEvaluation
Root metadata. Exactly one per `work_package_id`.
- `title` — system name
- `text` — scope statement (what's in / out)
- attributes: `system_name`, `evaluator`, `start_date`, `version`

### Stakeholder
- `title` — role label (e.g. *"Architect — Maria"*)
- `text` — notes on their concerns
- attributes:
  - `role` ∈ `evaluation-lead | scribe | questioner | architect | sponsor | business-stakeholder | user-proxy | developer | operator | security`
  - `name`, `is_proxy_for` (optional)

### BusinessDriver
- `title` — short label
- `text` — full statement
- attributes: `priority_rank` (1..N), `phase` = `"P2"`

### Constraint
- `title` — short label
- attributes:
  - `kind` ∈ `schedule | budget | regulatory | technical | organizational`
  - `severity` ∈ `hard | soft`

### QualityAttribute
- `title` ∈ `performance | availability | security | modifiability | usability | testability | deployability | scalability | interoperability | observability | cost`
- attributes:
  - `priority_rank`
  - `refinements`: array of strings (kept inline, no separate type)

### Component
- `title` — component name
- attributes:
  - `kind` ∈ `component | connector | deployment-unit | data-store | external-dependency | trust-boundary | bounded-context`
  - `responsibility`

### ArchitecturalDecision
- `title` — short label ("Single Postgres SoT")
- `text` — context, options, choice, consequences
- attributes: `adr_id` (e.g. `"ADR-007"`), `status` ∈ `accepted | superseded | rejected`

### ArchitecturalApproach
- `title` — canonical name ("CQRS", "Read replicas")
- attributes: `kind` ∈ `style | pattern | tactic`, `targets_QA`

### Scenario
- `title` — one-line summary
- `text` — six-part form rendered as labeled paragraphs
- attributes:
  - `category` ∈ `anticipated | use | growth | exploratory`
  - `source`, `stimulus`, `environment`, `artifact_label`, `response`, `response_measure`
  - `phase_introduced` ∈ `"P5" | "P7"`

### ScenarioRating
New record per rating change. Use `replaces` to point at the prior rating for the same scenario.
- attributes:
  - `importance` ∈ `H | M | L`
  - `difficulty` ∈ `H | M | L`
  - `selected_for_analysis` (bool)
  - `rationale`, `phase` (when this rating was set)

### ScenarioVote
One record per voter per scenario.
- attributes: `weight` (default 1), `category` ∈ `use | growth | exploratory`, `phase` = `"P7"`

### ProbingQuestion
- `title` — the question itself
- attributes: `qa_focus`, `phase` ∈ `"P6" | "P8"`, `answer_summary`

### AtamEvidence
(Named `AtamEvidence` not `Evidence` because the live schema already has an `Evidence` type used by the formal-debugger workflow.)
- `title` — short pointer ("ADR-007 §3" or `api/handler.go:142`)
- `text` — quoted snippet or observation
- attributes:
  - `kind` ∈ `adr | file_ref | measurement | quote | test_result | incident | doc`
  - `pointer` (URI / `path:line` / ticket id)

### Finding
- `title` — one-line statement
- `text` — full description
- attributes:
  - `finding_type` ∈ `R | NR | SP | TP`
  - `phase` ∈ `"P6" | "P8"`
  - `severity` ∈ `high | med | low` (Risks only)
  - `promotion_reason` (only when `supersedes` is set, e.g. *"SP→TP: cross-QA effect on freshness discovered in P8"*)

### RiskTheme
- `title`, `text`
- attributes: `phase` = `"P9"`

### Recommendation
- `title`
- attributes: `effort` ∈ `S | M | L`, `owner_role`, `priority`

### PhaseGate
Chained per evaluation (the `prevGate` link uses `chain_predecessor`).
- attributes:
  - `phase` ∈ `0..9`
  - `decision` ∈ `approved | revised | skipped`
  - `note`

### AtamReport
- `title`, `text` (full markdown report)
- attributes: `version`, `published_at`

---

## Adaptive control types (schema v6+)

These power the **Mode B controller** (`scripts/`). They turn Phase 6/8 from a hand-run Q&A into an audit-trailed selection problem.

### AtamInstrumentVersion
Refdata. One per probe-bank version. Workpackage: `atam.refdata.<version_id>`.
- `title` — short name
- attributes: `version_id` (e.g. `atam-v1`), `published_at`, `qa_coverage` (list), `probe_count`

### AtamBankProbe
Refdata. A vetted probing question. Workpackage: same `atam.refdata.<version_id>`.
- `title` — short slug, e.g. `perf.cache-strategy`
- `text` — `atam.bankprobe:<version>.<slug>` (globally unique)
- attributes:
  - `probe_id` (matches title; used as runtime id; must be unique within a version)
  - `target_qa` ∈ canonical QA names
  - `text` (the question, verbatim — what gets asked)
  - `intent` — what we expect to learn
  - `priority_tier` ∈ `critical | discriminator | standard | exploratory`
  - `estimated_time_minutes`, `expected_saturation_gain` (0..1), `expected_findings` (≥0)
  - `risk_level` ∈ `benign | sensitive | high-stakes`
  - `applies_when` — list of `{condition, value}` clauses (e.g. `{condition: "qa_selected", value: "performance"}`)
  - `discriminates_hypotheses` — when tier=`discriminator`, list of hypothesis text-ids this probe distinguishes
  - `finding_types_targeted` — typical outputs: subset of `R | NR | SP | TP`
- links: `instrumentVersion`, `prerequisites: many AtamBankProbe`, `targetsQA: QualityAttribute` (case-local override, optional)

### AtamPlan
Case-local. Records the candidates considered at one tick.
- `title` — `Plan #N`
- attributes: `candidate_probes` (list of `{probe_id, text_snapshot, target_qa, priority}`), `generated_at`

### AtamAdaptiveDecision
Case-local. The chosen probe + reason + alternatives.
- attributes:
  - `chosen_probe` — `{probe_id, text_snapshot, target_qa, intent, scenario_id}` (null if `source=closure`)
  - `source` ∈ `bank | generated | fallback-bank | closure`
  - `reason` — one-line rationale
  - `decided_at`
- links: `plan`, `evaluation`, `bankProbe` (when source includes bank), `discriminatesHypothesis` (when picking a discriminator)

### AtamProbeCandidate
Case-local. One LLM-generated probe before the quality gate.
- attributes: `text`, `intent`, `target_qa`, `scenario_id`, `proposed_priority_tier`, `proposed_risk_level`, `estimated_time_minutes`, `expected_saturation_gain`, `generation_prompt_hash`
- links: `evaluation`, `plan`, `becomesQuestion` (filled when a candidate is selected and asked)

### AtamProbeCritique
Case-local. Score + verdict on a candidate.
- attributes: `score` (0..1), `breakdown` (`{info_value, cost_eff, specificity, safety, novelty, qa_alignment}`), `verdict` ∈ `select | revise | reject`, `rationale_text`
- links: `candidate`, `evaluation`

### AtamProbeOutcome
Case-local. Calibration data — how a bank probe actually performed in this case.
- attributes: `time_minutes_observed`, `saturation_gain_observed`, `findings_observed`, `verbatim_reply_summary`, `notes`
- links: `evaluation`, `question: ProbingQuestion`, `bankProbe` (if from bank), `findings: many Finding`

### AtamCoverage
Case-local. Saturation per scenario over time. Append-only (`previous` link).
- attributes:
  - `status` ∈ `untouched | in-progress | sufficient | saturated`
  - `saturation` ∈ `[0, 1]`
  - `gaps` (list of strings — known unanswered sub-aspects)
  - `findings_count`, `questions_asked`
  - `updated_at`
- links: `evaluation`, `scenario`, `previous` (prior AtamCoverage for the same scenario), `decision` (the AtamAdaptiveDecision that advanced this coverage)

### AtamHypothesis
Case-local. A risk hunch that biases probe selection.
- `title` — short claim
- `text` — `atam.hypothesis:<wp>.h<n>` — stable id used as the hypothesis identifier
- attributes:
  - `claim_text` — full statement
  - `status` ∈ `open | confirmed | refuted | dropped` (initial; live status is from latest `AtamHypothesisUpdate`)
  - `discriminating_question` — what evidence would settle it
  - `discriminates_probe_ids` (list of `probe_id`s the bank discriminator(s) should match)
  - `relevant_qas` (list)
  - `opened_at`
- links: `evaluation`, `scenario` (optional), `parentHypothesis` (refinement chain), `supports: many AtamEvidence`, `refutes: many AtamEvidence`

### AtamHypothesisUpdate
Case-local. Status transitions. Append-only chain via `prevUpdate`.
- attributes: `status` (new value), `note`, `updated_at`
- links: `hypothesis`, `prevUpdate` (chain), `evidence: many AtamEvidence | Finding`

---

## Phase → records cheat sheet

| Phase | Creates | Mutates (via new record + supersedes/replaces) |
|-------|---------|-----------------------------------------------|
| P0 | `AtamEvaluation`, `Stakeholder*`, `PhaseGate(0)` | — |
| P2 | `BusinessDriver*`, `Constraint*`, `QualityAttribute*`, `PhaseGate(2)` | — |
| P3 | `Component*`, `ArchitecturalDecision*`, `PhaseGate(3)` | — |
| P4 | `ArchitecturalApproach*`, `PhaseGate(4)` | — |
| P5 | `Scenario*`, `ScenarioRating*`, `PhaseGate(5)` | — |
| P6 | `AtamPlan*`, `AtamAdaptiveDecision*`, `ProbingQuestion*`, `AtamEvidence*`, `Finding*`, `AtamCoverage*`, `AtamProbeOutcome*`, `AtamHypothesis*` (when hunches form), `AtamHypothesisUpdate*`, `AtamProbeCandidate*`+`AtamProbeCritique*` (when generation fires), `PhaseGate(6)` | — |
| P7 | `Scenario*` (use / growth / exploratory), `ScenarioVote*`, `PhaseGate(7)` | `ScenarioRating` (re-rating P5 leaves if priorities shifted) |
| P8 | same record types as P6, against newly-prioritized scenarios, `PhaseGate(8)` | `Finding` (SP→TP via `supersedes`); `AtamHypothesisUpdate` (closing out hypotheses) |
| P9 | `RiskTheme*`, `Recommendation*`, `AtamReport`, `PhaseGate(9)` | — |

---

## Example queries

- **All findings for an evaluation:**
  `find_items({type: "Finding", field: "work_package_id", query: "atam-2026-05-26-checkout"})`

- **All tradeoff points:**
  `find_items({type: "Finding", attributes: {finding_type: "TP"}})`

- **Phase progress (audit trail):**
  walk `prevGate` from the latest `PhaseGate` via `query_chain`.

- **All risks rolled into theme T:**
  follow `members` from `RiskTheme T`.

- **Evidence chain behind a recommendation:**
  recommendation → theme → member findings → evidence (→ component / decision).

- **Verify the chain is intact:**
  `verify_chain` on the evaluation's `work_package_id`.

---

## Design rationale

- **Single `Finding` type with `finding_type` attribute** (not four types): the SP→TP promotion is a clean `supersedes` chain, and "all findings on scenario X" is one query, not four unions.
- **`ScenarioRating` separate from `Scenario`**: scenarios are immutable observations; ratings shift as the evaluation discovers new priorities. `replaces` preserves rating history.
- **`PhaseGate` chained per evaluation**: makes phase progress *the* primary audit trail. Genesis-to-head walk replays the evaluation.
- **`Evidence` as a first-class type, not an attribute on `Finding`**: a single piece of evidence (e.g. one ADR) commonly supports multiple findings. Making it a node lets you query the reverse direction ("everything that depends on ADR-007").
- **`work_package_id` = evaluation id**: lets one hashharness instance hold many ATAM evaluations without type clashes; queries naturally scope to one evaluation.

---

## Pushing the schema to a live hashharness instance

The schema in `schemas/hashharness-schema.json` is **partial** — it declares only ATAM types. A live hashharness instance often has other types (Task*, Stipo*, Report, etc.). To install, **merge** the ATAM types into the live head and append a new schema version:

```text
1. current = mcp__hashharness__get_schema()
2. merged = {types: {...current.types, ...atam_types}}
3. mcp__hashharness__set_schema({schema: merged, expected_prev: <current head record_sha256>})
```

If `expected_prev` is stale, re-fetch and retry. **Do not** push the ATAM-only payload directly — it would drop sibling types from the head and break unrelated workflows reading them.
