# ATAM Skill — Run Feedback (case: HappyHero moments/HRV subsystem, 2026-05-28)

Feedback on issues observed while executing the `atam-evaluation` skill end-to-end (Mode B) against a real 4-codebase subsystem. Split into **skill/tooling issues** (actionable for the skill author) and **execution issues** (mistakes the operator/LLM made that the skill could have prevented). Severity: 🔴 blocking-ish · 🟠 friction · 🟡 polish.

---

## A. Skill / workflow issues

### A1 🔴 The §11 CQ-challenge step is not enforced — it was silently skippable
The SKILL.md says: "**Default:** after `close-phase --phase 8 --decision approved`, run a CQ pass on every R-high and R-med Finding." In practice the workflow let me close Phase 9 and produce a "complete" `REPORT.md` having challenged **0** findings. The challenge only happened because the user explicitly asked for it, and even then I challenged **3 of 7** high/med findings; the other four (MOD1, DI1, G10x, RA2) were only challenged on a *second* user prompt.
**Fix:** make `close-phase --phase 9` refuse (or loud-warn) until every high/med Finding has either a linked challenge (an `AtamEvidence`/CA referencing it) or an explicit `--waive-challenge <sha> --reason`. Print the unchallenged-finding list at the P8→P9 boundary.

### A2 🔴 Mode B's adaptive selection is a no-op without a populated probe bank
`next-probe` returned `{"source":"closure","candidates_count":0}` on **every** tick because `AtamBankProbe` / `AtamInstrumentVersion atam-v1` is empty. The headline Mode-B feature (adaptive, audit-trailed probe selection) silently degraded to "emit an empty `AtamPlan` + `AtamAdaptiveDecision`." I ended up using the ticks **only** to mint `decision_sha`/`plan_sha` values that downstream verbs require — not for any selection value.
**Fix:** either ship a starter probe bank for the common QAs (reliability, modifiability, fault-isolation, data-integrity), or have `open-evaluation` warn "instrument bank empty — Mode B will not select probes; you are in manual-record mode." Detection §"an `AtamInstrumentVersion` exists" passes structurally even when the bank has 0 probes.

### A3 🟠 The controller covers only half the entity lifecycle
There are verbs for evidence/question/finding/coverage/hypothesis, but **no** `create-scenario`, `create-qa`, `create-component`, `create-risk-theme`, `create-recommendation`. Yet `record-finding` *requires* `--scenario-sha` and `--affects-qa-shas`. So every run must drop to raw `mcp__hashharness__create_item` for half the graph, hand-threading record_sha256 values. This is the single biggest source of friction and error surface.
**Fix:** add the missing create-* verbs (even thin wrappers) so the whole ATAM ontology is reachable from one CLI with consistent JSON output.

### A4 🟠 Hidden ordering contract: finding/coverage require a prior tick
`record-finding` requires `--question-sha`; `update-coverage` requires `--decision-sha`; `record-question` requires `--decision-sha`. None of this is in the SKILL.md "CLI verbs" example block, which shows `record-finding` as if it stands alone. I discovered the dependency chain by hitting `error: the following arguments are required: --question-sha`.
**Fix:** document the minimal record chain (`next-probe → record-question → record-finding`; `next-probe → update-coverage`), or let `record-finding` auto-mint a decision+question stub when called in "manual mode."

### A5 🟠 Recording one finding is ~4–6 CLI calls; a 6-finding eval is ~30+
Per finding: `next-probe` + `record-question` + `record-evidence`×N + `record-finding` + `update-coverage`. For 6 leaves that is 30–40 process spawns, each paying venv + MCP connect cost. It pushed me toward big fragile bash scripts (and one `${9:+--supersedes}` quoting bug that silently dropped the flag on 3 records).
**Fix:** a single `record-finding` that accepts inline evidence (`--evidence kind:pointer:quote` repeatable) and auto-ticks the plan/decision/question; emit all child shas in one JSON blob.

### A6 🟠 AIF hand-off is fully manual and error-prone
The `challenge` verb ends with `"next_step": "Hand off to aif-arguments skill"`, but nothing automates it. Building the I/RA/CA graph means manually creating 14+ nodes, capturing each `record_sha256`, and threading them into `premises`/`conclusion`/`attacker`/`target`. One transposed sha = a broken edge (caught only because hashharness rejects unknown targets at write).
**Fix:** have `challenge` optionally emit ready-to-create node stubs (I-nodes for each evidence + conclusion, an RA stub with `premises`/`conclusion` pre-filled by sha, CA stubs per CQ with `target` pre-filled) — mirroring `aif-generate-cqs.py --format paired`.

### A7 🟠 `aif-validate.py` false-positives on the `premises` link (validator bug)
Validator reported `[S1] link 'premisesHash' → unknown record …` for every RA. Inspecting the stored record shows hashharness persists **both** `links.premises` (the correct array of record_sha256) **and** a derived `links.premisesHash` digest of that array. The validator reads `premisesHash` as if it were a node reference. The graph is correct; the validator is wrong.
**Fix:** in `aif-validate.py`, resolve many-links from `links.<name>` (array), ignore the `<name>Hash` digest companion field.

### A8 🟡 Schema/doc mismatch: `IndividualCriticalQuestion` type does not exist
`references/cq-schemes.md` says "each CQ becomes an `IndividualCriticalQuestion` node," and SKILL.md §11 references the same. The hashharness schema has no such type — CQs can only be `AifInode` + an `AifCA`. Either add the type or correct the docs.

### A9 🟡 `premise_roles` must match the scheme catalog exactly, but nothing helps at authoring time
`aif-validate.py [F3]` fires when `premise_roles` ≠ the scheme's required role keys (I used `cause`/`observation`; catalog wanted `causal_generalization`/`cause_present`/`hypothesis_predicts`). You only learn the required names *after* writing the node.
**Fix:** `schemes.py`-backed helper: `aif scheme-roles <scheme>` prints required premise roles + CQs so RA nodes can be authored full the first time.

### A10 🟡 No guidance on where to write phase artifacts vs. VCS
The skill writes `atam-evaluation/00..08 + REPORT.md` to the target repo root. In this project `.claude/memory_bank` is git-excluded but a new top-level `atam-evaluation/` is **not**, so the artifacts would land in a commit by default. The skill should state an output convention (and respect a `--out` dir).

---

## B. Execution issues (operator/LLM mistakes the skill could guard against)

### B1 🔴 A decisive measurement was in-scope but unconsulted (FI2)
`troubleshooting/performance-hotspots.md` was inventoried in Phase 0 and contains `HEAD /hrv-robot/notification` **max 121.4s** runaway — the exact evidence for FI2's consequence claim. I rated FI2 high on a *structural* argument and never opened the file until a later challenge. CQ2 (`evidence_for_consequence_claim`) was effectively unenforced.
**Lesson/skill hook:** before rating a consequence-bearing finding, require an "evidence inventory" check against the Phase-0 measurement sources. A `record-finding` of type R/TP with no `--evidence-shas` of kind `measurement|incident|test_result` should warn.

### B2 🟠 Risk-finding bias; "working as designed" tested only on a second pass
Every utility-tree leaf I analyzed produced a finding. The abductive CQ13 ("is this working-as-designed rather than a risk?") — which reframed T2 (→ observability gap) and T3 (→ latent/conditional) and would have tempered the initial framing — was only applied after the user pushed. ATAM is supposed to resist a verdict; an un-challenged risk lean is itself a bias.
**Lesson/skill hook:** make the abductive/"non-risk" challenge a default theme-time step, not optional.

### B3 🟠 A factual mechanism error reached the report (RA2)
I wrote that passive HRV is iOS-only "because silent-push returns early on Android," when the real cause is the HealthKit-only data source (`background_fetch` is cross-platform). It survived the Phase-3/6 gate approvals because the gates check *artifact completeness*, not *claim precision*. The conclusion held, but the cited mechanism was wrong.
**Lesson/skill hook:** the gate prompts could ask specifically "does each finding cite the exact mechanism, verified in code?" rather than a generic approve/revise.

### B4 🟡 Cross-finding causal links were found late
FI2'' (121s runaway) and RA1' (invisible stranding) share a root (a long promotion recycled mid-run), but I recorded them as independent findings first and only linked them on the evidence pass. ATAM has no explicit "do any findings share a cause?" step before theming.
**Lesson/skill hook:** add a "finding-interaction" prompt before risk-theme rollup.

---

## C. What worked well (keep)
- **Phase gates with user-in-the-loop** caught scope errors early (the user added "HRV must not harm the surrounding system" as G5, and twice expanded the architecture step — ingestion stages, mobile initiators — before I built the tree on top).
- **`supersedes` discipline** made the CQ revisions (RA1→RA1', FI2→FI2'', MOD1→MOD1') cleanly auditable without mutation.
- **The six-part scenario + (Importance,Difficulty) rating** forced concrete, falsifiable scenarios and a defensible analysis order.
- **Hash-chained audit trail** is genuinely valuable for a rigorous user — every finding traces to evidence to file:line.

## D. Top 5 fixes by leverage
1. **A1** — enforce the §11 challenge at the P9 gate (prevents shipping unchallenged findings — the highest-impact correctness issue this run).
2. **A3 + A4 + A5** — complete the controller verb set + collapse the per-finding call chain (removes most friction and the bash-quoting error class).
3. **A2** — populate a starter probe bank or stop advertising adaptive selection when the bank is empty.
4. **B1** — evidence-inventory gate before rating consequence findings (would have caught the 121s datum on the first pass).
5. **A6 + A7** — automate the AIF stub emission and fix the `premisesHash` validator false-positive.
