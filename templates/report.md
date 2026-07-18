# ATAM Evaluation Report

**System:** <name>
**Date:** <YYYY-MM-DD>
**Evaluator:** <name>
**Method:** ATAM (Kazman, Klein, Clements — SEI)

<!-- (R2a) AUDIT-TRAIL STATUS — MANDATORY. Pick exactly one variant below. A reader
     must be able to tell at a glance whether these findings are hash-chained and
     verifiable. Never delete this block: a report with no trail-status line reads as
     trustworthy when it may not be (finding F3 — a file-only report is otherwise
     indistinguishable from an audited one). -->

<!-- Mode B (controller + hashharness): -->
> **Audit trail:** ✅ hash-chained — workpackage `<atam.case.…>` · `cli.py audit` → `trustworthy=<true|false>` (crypto <ok>, <N> records). Findings/evidence are immutable and independently verifiable.

<!-- Mode A (direct MCP records, no controller audit): -->
> **Audit trail:** ◑ hash-chained (workpackage `<…>`), but not run through `cli.py audit` — no combined crypto+structural verdict. Re-run under Mode B to certify.

<!-- File-only mode (NO hashharness): -->
> ## ⚠️ NO AUDIT TRAIL — FILE-ONLY MODE
> These findings were **not** recorded to a hash-chained store. Nothing here is
> cryptographically verifiable, immutable, or independently checkable — the report is
> a rendered artifact only. Treat severities and the "no verdict" stance accordingly.
> To get a verifiable trail, re-run with hashharness available (Mode A/B).

## Executive summary
<3–5 sentences: what was evaluated, top risk themes, headline recommendation>

## 1. Scope and inputs
See `00-setup.md`.

## 2. Business drivers
See `01-business-drivers.md`. Top QAs in priority order:
1.
2.
3.

## 3. Architecture summary
See `02-architecture.md`.

## 4. Architectural approaches identified
See `03-approaches.md`.

## 5. Utility tree
See `04-utility-tree.md`. Leaves analyzed: <count>.

## 6. Findings — consolidated

### 6.1 Risks
| ID | Risk | Theme | Affected QA | Source scenario |
|----|------|-------|-------------|-----------------|

### 6.2 Sensitivity points
| ID | Property | Component | QA |
|----|----------|-----------|----|

### 6.3 Tradeoff points
| ID | Property | QAs | Tradeoff |
|----|----------|-----|----------|

### 6.4 Non-risks
| ID | Decision | Why sound |
|----|----------|-----------|

## 7. Risk themes
<group related risks into themes; map each theme to the business driver(s) it threatens>

### Theme T-1: <name>
- **Risks rolled up:** R-x, R-y, R-z
- **Business driver(s) threatened:** <from §2>
- **Why it matters:** <impact>
- **Recommendation:** <concrete action>

<repeat>

## 8. Recommendations (prioritized)
1. **<recommendation>** — addresses theme T-x. Effort: <S/M/L>. Owner: <role>.
2. ...

## 9. Known gaps in this evaluation
- <stakeholder not consulted>
- <phase skipped>
- <data not available>

## Appendices
- Phase artifacts: `00-setup.md` through `08-risk-themes.md`
- Scenario catalog: `06-scenarios.md`
