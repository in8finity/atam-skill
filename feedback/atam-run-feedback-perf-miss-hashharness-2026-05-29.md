# ATAM Skill — Run Feedback (case: hashharness core, 2026-05-29)

Retrospective on a **miss**: an end-to-end `atam-evaluation` run (guided, via `pm-guided-skill-execution`) against hashharness core produced a "complete" REPORT.md that **under-weighted Performance/Scalability and asserted a wrong performance characteristic**. A production latency/concurrency incident report (filed independently the same day) then surfaced findings the ATAM should have caught — a 189 s `pm status`, server collapse at 6 concurrent workers, and a hot path that scales with total history.

This note dissects **why the skill's process let that happen** and proposes guardrails. Severity: 🔴 blocking-ish · 🟠 friction · 🟡 polish. Split into skill/workflow issues (actionable for the author) and execution issues (LLM mistakes the skill could have prevented).

The specific miss, concretely: I rated `find_tips_bulk` as an "O(1) tip / two-query fast path" (approach A12, leaf PERF-1 at (M,M)) and it fell below the analysis cut. In reality its head-resolution step decodes **every record in each work-package's chain** to recover one head — O(all history), not O(N heads). The incident measured the consequence. The evaluation's own house-rule B1 *correctly flagged* that my Performance findings were structural-only — but the skill let the run complete anyway.

---

## A. Skill / workflow issues

### A1 🔴 Phase 0 treats measurement evidence as optional, so the run never went looking for it
SKILL.md Phase 0 lists inputs in priority order: arch docs (1), source (2), external requirements (3), interactive input (4). **Measurements — perf logs, incident reports, benchmarks, a `feedback/` dir — are not on the list.** B1 later *demands* measurement evidence to rate an R/TP high/med, but by then Phase 0 is closed and nobody gathered any. The result: the evaluator reasons structurally, B1 warns "no measurement," and the warning is absorbed as a caveat instead of sending anyone back to measure.
In this run there was a `feedback/backend-query-latency-indexing-2026-05-29.md` sitting in the target repo's sibling tree that I never looked for, and a git log with perf-relevant commits I never read.
**Fix:** add to Phase 0 an explicit, gated **"hunt for measurement evidence"** step: look for `feedback/`, `benchmarks/`, `*.bench`, perf/incident docs, CI timing, and recent perf-tagged commits (`git log --grep`). If none exist for a QA that will be rated, record `STATUS: no measurement evidence for <QA>` so the gap is visible at Phase 2, not discovered post-hoc.

### A2 🔴 Importance×Difficulty prioritization structurally buries the QA most likely to surprise you
The utility-tree gate selects (H,H)/(H,M) leaves. For a correctness-first system, the evaluator's prior puts Integrity/Auditability at H and Performance at M/L — so **every Performance leaf fell below the ★ cut and went unanalyzed by construction.** That is exactly backwards for finding *surprises*: the QA you rate low-importance is the one where a latent measured problem will blindside you, because nobody looks.
**Fix:** require **at least one leaf per top-level QA** to be analyzed regardless of rating (a "minimum coverage floor"), OR make the Phase 5 gate print "QAs with zero selected leaves: [Performance]" and force an explicit waive. A whole quality attribute silently excluded from analysis should be a loud event, not a side effect of the H/M/L math.

### A3 🔴 The §11 CQ-challenge only interrogates Risks/Tradeoffs — never Non-Risks
My wrong claim ("`find_tips_bulk` is O(1), performance is fine") never became a Risk; it lived as an **approach (A12) and an implicit non-risk**. The challenge step, B1, and B3 all operate on findings of type R/TP. **A plausible-but-wrong NON-risk is invisible to every quality gate in the skill.** The most dangerous errors in a review are the things you waved through as fine.
**Fix:** extend §11 (or add a Phase 6 sub-gate) to challenge **load-bearing non-risks and "fast-path"/"O(1)"/"cheap" claims** too. Minimum: any approach or NR asserting a *performance* or *scalability* property must cite either a measurement or a traced code path — not a doc label. Re-use B3's question ("is this the mechanism in the code, or the one that sounds right?") on non-risks.

### A4 🟠 ATAM-as-written never executes anything; for Performance QAs there is no substitute for running it
The whole method is doc-reading + code-reading. For Integrity/Auditability that is largely fine (the properties are structural and machine-checkable). For Performance/Scalability/concurrency-robustness it is **not** — you cannot read your way to "189 s" or "collapses at 6 workers." The skill has no "run a probe / take a measurement" affordance.
**Fix:** for any analyzed Performance/Scalability/Availability leaf, the skill should *prompt* for a measurement or a minimal load probe (even a 10-line script), and mark the finding `evidence: structural-only` if the user declines — surfaced in the report's severity, not buried.

### A5 🟠 B1's evidence warning fires at rating time but has no teeth at report time
B1 says `record-finding` warns when a high/med R/TP cites no measurement. But the run still closed Phase 9 with a clean REPORT while *every* Performance consideration was structural-only. The warning is a print, not a gate.
**Fix:** at `close-phase --phase 9`, list every finding whose severity ≥ med rests on `evidence: structural-only`, and require an explicit `--accept-structural <sha> --reason` to publish. Same shape as the A1 unchallenged-finding gate from the prior (HRV) feedback.

### A6 🟠 No prompt to read the target's own bug/feedback/incident history
Trusting the README's self-description ("O(1) head lookup") over the code+history is how the wrong mechanism entered. The README is the *architect's claim*; the incident report is *what actually happened*. ATAM should privilege the latter when they conflict.
**Fix:** Phase 0/3 should explicitly diff "documented behavior" vs "observed behavior (incidents/feedback/tests)" and flag conflicts as candidate findings.

---

## B. Execution issues (LLM mistakes the skill could have caught)

### B1x 🔴 I trusted a doc label ("O(1)") instead of tracing the code path
The README says "O(1) head lookup"; I propagated it into A12/PERF-1 without tracing `find_tips_bulk`'s second query (`SELECT … WHERE work_package_id IN (chunk)` then decode-and-filter), which is O(all items in those wps). Classic B3 failure — but on a non-risk, where B3 doesn't reach (see A3). The mechanism I recorded sounded right and was wrong.

### B2x 🟠 I let the H/M/L math make the coverage decision for me
At the Phase 5 gate I proposed the eight ★ leaves and noticed Performance had none selected — and proceeded anyway, because the tree said so. I should have flagged "an entire QA is going unanalyzed" as a decision for the user, not a mechanical outcome. (A2 would have forced this.)

### B3x 🟠 I never ran the system or looked for measurements
I had Bash and the repo in front of me. I could have populated a store and timed `find_tips_bulk`, or grepped for a `feedback/` dir. I treated "ATAM = analysis" too literally. (A1/A4 would have prompted it.)

---

## What worked (keep)

- **B1 itself was right.** I explicitly wrote "Performance findings are structural-only" in the analysis and challenge — the skill's honesty rule made me *say* the evaluation was weak exactly where it later proved wrong. The gap is that saying it didn't stop the run (A5).
- **The §11 challenge correctly de-double-counted** (merged R-2 into R-4) and correctly downgraded a speculative concurrency risk to "conditional, no measurement" — which is *precisely* the finding the incident then promoted. The challenge reasoning was sound; it just had no measurement to challenge *with* (A1).
- **T1 (the real top correctness risk — no store-wide verify primitive) was found and held at High** through the challenge. The structural method works well for structural QAs.

## One-line root cause

ATAM-as-written is a **structural** method whose gates (utility-tree H/M/L, R/TP-only challenge, B1-as-warning) systematically under-serve **measured** quality attributes — so a correctness-first system's Performance/concurrency risks fall through every net unless an external incident supplies the evidence. The four 🔴 fixes (hunt for measurements in P0, minimum per-QA coverage floor, challenge non-risks, gate structural-only severities) would have caught this run's miss before the incident did.
