# ATAM Evaluation Skill

**Turn an architecture review from a set of opinions into a set of findings you can trust — risks, tradeoffs, and sensitivity points that are challenged, evidence-backed, and recorded in a tamper-evident audit trail.**

That sentence is the whole value proposition. Everything below supports it.

---

## Why it exists

- **Situation.** Before you scale, launch, or bet a roadmap on a design, someone reviews the architecture.
- **Complication.** Most reviews produce *prose* — a smart engineer's opinion. Opinions drift, skip the quality attribute nobody championed, rate things "high risk" on a hunch, and leave no trail when someone asks six months later *why* you concluded what you concluded. Worst of all, they reason their way to "this should be fast" instead of measuring their way to "`pm status` takes 189 seconds."
- **Question.** How do you run a review whose conclusions still hold up when they're challenged?
- **Answer.** This skill runs the SEI's **Architecture Tradeoff Analysis Method (ATAM)** as a *gated, evidence-checked, append-only* process. It doesn't just find risks — it makes it hard for a weak finding to survive to the final report.

---

## What you get (four concrete guarantees)

1. **Findings that survived a challenge, not just findings.** Every load-bearing risk/tradeoff is put through a Walton critical-questions pass (§11) before it becomes a recommendation. A finding that can't answer *"is this just the system working as designed?"* gets downgraded or withdrawn — with the original preserved.

2. **Measurement beats hand-waving — enforced.** For Performance / Scalability / Availability, a high-severity finding backed only by "I read the code and it looks slow" gets flagged at the gate. You either attach a measurement (an incident, a benchmark, a 10-line probe) or lower the severity. This is where structural reviews quietly fail; the skill makes the gap loud.

3. **A trustworthy audit trail.** Findings, evidence, and phase gates are written as **hash-chained, append-only records** (via hashharness). Corrections are new records that *supersede* old ones — nothing is silently edited. `cli.py audit` gives a one-shot verdict: *cryptographically intact AND no unchallenged risks AND no structural-only severities*.

4. **Coverage you decided on, not coverage you drifted into.** The utility tree forces at least one scenario per quality attribute, and the gate warns when a whole QA was left unanalyzed — because *the QA you rated low-importance is the one a latent measured problem will blindside you on.*

The through-line: **ATAM finds risks; it does not grade the architecture.** No letter grades, no verdicts — just risks mapped back to the business goals they threaten.

---

## Practical usage: a 90-second walk-through

**You say:**

> "Evaluate the architecture of our user-behaviour analytics subsystem."

**The skill runs the 9 ATAM phases, pausing at each gate.** Here's what a real run produced (abridged from [`reports/atam-uba-2026-05-27.md`](reports/atam-uba-2026-05-27.md)):

**P2 — Business drivers** (it asks *you*; it never invents them):

| # | Driver |
|---|--------|
| BD1 | Understand user-segment behaviour |
| BD2 | Measure the impact of app changes (release → behaviour delta) |

**P3 — Architecture** (summarized from docs + code): a single shared OLTP PostgreSQL serving as *both* the app's source of truth and the analytics store; behavioural events inferred at query time rather than being first-class.

**P5 — Utility tree** ranks the quality attributes: `modifiability > availability > security > performance`.

**P6 + §11 — Analysis, then challenge.** 18 findings surface — 8 rated R-high. Each high finding is challenged before it counts. The non-obvious one:

> **F16R** — The team *does* have a week-over-week comparison framework (`cohort_markov_pivot.py`), but the system can't **attribute** an observed behaviour delta to a specific release. So BD2 is *coarsely* met, not fully met.

That is the kind of finding prose reviews miss: not "you're missing analytics," but "your analytics can't answer the business question you built them for." It only surfaced because the analysis was tied back to a named business driver and grounded in the actual file.

**P9 — Risk themes mapped to drivers:**

> The dominant theme — **silent schema-semantics drift** — has already materialised twice in production (the 2026-05-11 content-corruption incident; a documented SQL-side drift worked around in code). Themes T1 and T4 directly threaten BD1/BD2.

Note "already materialised twice in production" — that's an *incident* citation, not structural speculation. The gate is satisfied because the severity is backed by something that actually happened.

**Recommendations** come out prioritized and, where a critical question split them, paired (a cheaper *do-now* beside a heavier *do-later*) — conventional engineering moves (disable auto-sync, add a read replica, separate DB users), each addressing a named theme.

---

## Three ways to run it

| You want… | Do this |
|---|---|
| **An interactive review**, gate by gate | Just ask in natural language — *"do an ATAM of X"*, *"build a utility tree for X"*, *"find the architectural tradeoffs in X"*. The skill triggers and walks you through it. |
| **An expert to drive it for you** | Invoke the bundled subagent: `@agent-architecture-evaluator`. It's an ATAM-proficient architect that knows this skill's rules and drives it end-to-end. (See [`agents/architecture-evaluator.md`](agents/architecture-evaluator.md).) |
| **Hands-off / batch execution** | Run it under the `pm-*-skill-execution` drivers — `pm-guided` (you're in the loop at every gate), `pm-assisted` (default + escalate on critical gates), `pm-auto` (only for well-scoped, low-stakes runs). Critical gates (scope, business drivers, challenge) never auto-resolve. |

---

## What it produces

```
atam-evaluation/
├── 00-setup.md            04-utility-tree.md      08-risk-themes.md
├── 01-business-drivers.md 05-analysis.md          REPORT.md   ← consolidated
├── 02-architecture.md     06-scenarios.md
├── 03-approaches.md       07-reanalysis.md
```

Files are the human-readable convenience; the **hashharness chain is the source of truth**. Artifacts land in the *evaluator's* workspace (git-ignored), never in the target repo's commit.

---

## Under the hood (for the curious)

- **Three execution modes**, chosen automatically: **Mode B** (the `scripts/cli.py` controller — adaptive, audit-trailed probe selection over a vetted question bank), **Mode A** (direct MCP records), or **file-only** (no audit trail). Mode B needs hashharness + a populated probe bank.
- **The gates that make it trustworthy** (loud warnings, never silent refusals): unchallenged high/med risks, structural-only severities on measured QAs, property-asserting non-risks left unchallenged, and quality attributes with zero analyzed scenarios.
- **The full method, verbs, gates, and house rules** live in [`SKILL.md`](SKILL.md); the ATAM ontology, quality-attribute taxonomy, architectural-approach catalog, probing-question banks, and Walton CQ schemes live in [`references/`](references/).

---

## Requirements

- **Claude Code** with the skill installed (this repo *is* the skill).
- **Optional but recommended:** the **hashharness** MCP backend (see [`SKILL.md`](SKILL.md) → *Adaptive control*) for the append-only audit trail and Mode B. Without it, the skill degrades gracefully to file-only mode.
- **Python venv** for `scripts/cli.py` when using Mode B.
