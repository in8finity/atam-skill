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

3. **A trustworthy audit trail.** Findings, evidence, and phase gates are written as **hash-chained, append-only records** (via hashharness). Corrections are new records that *supersede* old ones — nothing is silently edited. `cli.py audit` gives a one-shot verdict: *cryptographically intact **AND** its own read path wasn't truncated **AND** no unchallenged risks, structural-only severities, unflagged property-asserting non-risks, or unwaived coverage gaps.*

4. **Coverage you decided on, not coverage you drifted into.** The utility tree forces at least one scenario per quality attribute, and the gate warns when a whole QA was left unanalyzed — because *the QA you rated low-importance is the one a latent measured problem will blindside you on.*

The through-line: **ATAM finds risks; it does not grade the architecture.** No letter grades, no verdicts — just risks mapped back to the business goals they threaten.

---

## Practical usage: the skill evaluated by itself

The most honest demonstration is to point the skill at *its own* architecture. Here's an abridged walk-through of an ATAM of `atam-evaluation` — the spec (`SKILL.md`), the Mode-B controller (`scripts/`), and the hashharness append-only backend — treated as one subsystem.

**You say:**

> "Evaluate the architecture of this project — the atam-evaluation skill itself."

**The skill runs the 9 ATAM phases, pausing at each gate.**

**P2 — Business drivers** (it asks *you*; it never invents them). As the skill's maintainer you supply:

| # | Driver |
|---|--------|
| BD1 | Produce **tamper-evident** evaluation records — the audit trail *is* the product |
| BD2 | Actually **catch weak findings** — unchallenged risks, structural-only severities, property-asserting non-risks, unanalyzed QAs |
| BD3 | Be drivable both **interactively** and by the **`pm-*` automation** drivers |
| BD4 | Be **portable** across arbitrary target repos |

**P3/P4 — Architecture & approaches** (from spec + code): an **immutable, hash-chained audit ledger** (hashharness MCP) written by an **adaptive selection loop** (bank probe → LLM generation → critique gate, in `selection.py`/`generator.py`/`critic.py`), with **graceful degradation** across three modes — Mode B (controller CLI) → Mode A (direct MCP) → file-only.

**P5 — Utility tree** ranks the QAs: `auditability > correctness-of-gates > usability > portability`.

**P6 + §11 — Analysis, then challenge.** The non-obvious finding — and it's self-referential:

> **R-high → revised** — Mode B silently falls back to **file-only** when any prerequisite is missing (no hashharness, empty probe bank, non-executable `cli.py`); `open-evaluation` only *warns* on a zero-probe bank, it doesn't refuse (`scripts/cli.py:196`). File-only drops the append-only ledger — i.e. **BD1's entire value** — with no loud signal. The §11 abductive CQ *"isn't this just working-as-designed graceful degradation?"* **landed**, so the finding was **revised**: the risk isn't that it degrades, it's that it degrades *without telling you the audit trail is now gone.*

That reframing — kept as `supersedes`, with the original preserved — is exactly what the challenge step is for.

**The skill catches its own weak evidence.** That R-high cites only `file_ref` + `doc` evidence, so `close-phase --phase 9` flags it under the **A5 structural-only gate** — the skill holds its *own* finding to the same bar: attach a measurement (seed a broken config, observe the silent fallback) or lower the severity. Meanwhile the load-bearing non-risk *"the chain proves records weren't tampered with"* is marked `--asserts-property`, so the **A3 gate** forces it to be challenged rather than trusted — it's sound only if `verify_work_package` really re-checks content hashes, chain links, and schema binding.

**P9 — Risk themes mapped to drivers:**

> **T1 — Silent trust erosion** (the file-only fallback + the fact that `audit`'s `trustworthy=true` verdict is a *sensitivity point*: it rests entirely on the four gate checks in `cli.py` plus the crypto verify — one defect there yields a false all-clear). Threatens **BD1** and **BD2**.
> **T2 — Core value is asserted, not measured** — the gates' catch-rate is a structural claim; nothing yet *proves* `audit` flags a seeded weak finding. Threatens **BD2**.

**Recommendations**, prioritized with Impact/Effort:

| Recommendation | Impact | Effort |
|---|---|---|
| Print a loud `NO AUDIT TRAIL` banner when running file-only (at open *and* in `REPORT.md`) | H | S |
| Add a regression corpus of seeded weak findings; assert `audit` catches each — turns BD2 from *structural* to *measured* | H | M |
| Make `open-evaluation` **refuse** (not just warn) on a zero-probe bank unless `--allow-file-only` is passed | M | S |

The point isn't that these are dramatic findings — it's that a review of a system *by its own author* still surfaced a silent-degradation risk, a false-verdict sensitivity point, and an honestly-flagged gap in its own evidence, **because the gates wouldn't let the loose reasoning through.**

### The loop closed

This isn't hypothetical — the skill *was* run against itself, and it worked so well it **broke on itself**. Mid-run, the §11 challenge step couldn't resolve **4 of 7 findings**: `get_item_by_hash` scanned only the first 10,000 of the store's 32,000+ records, so 69% were invisible — the tool's own trust-building step silently degraded by the very scalability limit it documents. That became the real headline finding (measured, not projected), and every recommendation was then implemented and verified, hardening the skill it evaluated:

- **indexed record lookup** — replaces the 10k-capped scan (the headline fix)
- **`NO-AUDIT-TRAIL` banner** in file-only mode, at open and in `REPORT.md` — a report can no longer look audited when it isn't
- **auto-promotion + a backstop** for unflagged "O(1)/constant-time/scales" non-risks — the incident-proven blind spot
- **a read-path self-check** — `audit` refuses to certify `trustworthy=true` if its own reads were truncated
- **explicit `waive-qa`** — a prose-only coverage waiver can no longer satisfy the gate

A self-review that measurably hardens the reviewer — the whole exchange recorded, end to end, in its own append-only audit chain.

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
- **The gates that make it trustworthy** (loud warnings, never silent refusals): unchallenged high/med risks; structural-only severities on measured QAs; property-asserting non-risks left unchallenged (flagged manually *or* auto-detected from "O(1)/constant-time/scales" language, with a report-time backstop); quality attributes with zero analyzed scenarios or only a prose-only waiver; a read-path self-check so the verdict can't be certified over a truncated view; and a `NO-AUDIT-TRAIL` banner when running file-only.
- **The full method, verbs, gates, and house rules** live in [`SKILL.md`](SKILL.md); the ATAM ontology, quality-attribute taxonomy, architectural-approach catalog, probing-question banks, and Walton CQ schemes live in [`references/`](references/).

---

## Requirements

- **Claude Code** with the skill installed (this repo *is* the skill).
- **Optional but recommended:** the **hashharness** MCP backend (see [`SKILL.md`](SKILL.md) → *Adaptive control*) for the append-only audit trail and Mode B. Without it, the skill degrades gracefully to file-only mode.
- **Python venv** for `scripts/cli.py` when using Mode B.
