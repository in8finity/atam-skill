# Feedback to `atam-evaluation` — from the `aif-arguments` skill

**Source:** validation of the **live hashharness AIF store** on 2026-05-29 (81 AIF items: 54 I-nodes, 13 RA, 14 CA, 0 PA), run with `aif-validate.py`. The findings ATAM emits during its `challenge` step are persisted as `AifRA` nodes; this is feedback about the *metadata* ATAM writes onto those nodes, owned by *this* (ATAM) skill, not by `aif-arguments`.

Severity: 🔴 bug · 🟠 friction · 🟡 polish.

---

## 1. 🟠 ATAM emits `AifRA.attributes.premise_roles` with ad-hoc role names, not the Walton role names the scheme registry requires

**Confirmed against live data.** Of the 13 RAs in the store, **10 fail the `[F3]` scheme-fullness check** because their `premise_roles` array does not contain the role names that `aif-arguments`' scheme registry (`schemes.py`) declares as *required* for the tagged scheme. Hashharness does **not** enforce Layer-2 role vocabulary on write, so every one of these was accepted — only `aif-validate.py` catches it.

The split is diagnostic: the RAs that **pass** were hand-authored in demo/finding work-packages and already used canonical names; the RAs that **fail** are exactly the ones emitted by ATAM case runs.

| Work package | Tagged scheme | `premise_roles` ATAM wrote | `[F3]`? |
|---|---|---|---|
| `atam.case.moments-hrv…` (RA-cross, RA-FI2', RA-RA1') | `cause_to_effect` | `["cause"]` / `["cause","cause"]` | ✗ fail |
| `atam.case.moments-hrv…` (RA-FI1) | `evidence_to_hypothesis` | `["observation","observation","observation"]` | ✗ fail |
| `atam.case.chat-ws…` (RA-RA1, RA-RA2) | `cause_to_effect` | `["cause"]` | ✗ fail |
| `atam.case.chat-ws…` (RA-SEC1) | `evidence_to_hypothesis` | `["observation"×3]` | ✗ fail |
| `aif-finding-release-impact` (RA1) | `cause_to_effect` | `["causal_generalization","cause_present"]` | ✓ **pass** |
| `aif-finding-release-impact` (RA2) | `practical_reasoning` | `["goal","means"]` | ✓ **pass** |
| `aif-finding-taxonomy-drift` (RA1) | `negative_consequences` | `["action","bad_consequence"]` | ✓ **pass** |

So this is not a registry gap — `negative_consequences` and `practical_reasoning` were authored with the correct names and validate cleanly. The ATAM case runs simply use a looser vocabulary (`cause`, `observation`) than the schemes they tag.

### Canonical role names ATAM must emit (in order, aligned with `links.premises`)

Discoverable at authoring time via the **JSON contract** (the stable cross-skill
interface — do *not* scrape the human text or hardcode role names):

```bash
# one scheme:
aif-check-scheme.py --roles <scheme> --format json
#   → { scheme, family, strength, required_roles[], optional_roles[],
#       critical_questions[], reference }
# whole catalog in one call:
python3 schemes.py --json
```

Take `required_roles` (in order) verbatim as the `premise_roles` you write.
Resolve the script path through the installed skills root
(`<skills>/aif-arguments/scripts/`), not an absolute path. The human
`--roles` text and `python3 schemes.py` list may be reflowed at any time; only
the JSON shape is guaranteed stable.

| Scheme ATAM uses | Required `premise_roles` (in order) |
|---|---|
| `cause_to_effect` | `causal_generalization`, `cause_present` |
| `evidence_to_hypothesis` | `hypothesis_predicts`, `observation` |
| `analogy` | `base_case`, `similarity` |
| `negative_consequences` | `action`, `bad_consequence` |
| `practical_reasoning` | `goal`, `means` |

**Suggested fix (ATAM side):** when the `challenge` step writes an `AifRA`, set `premise_roles` from the scheme registry's required list rather than improvising. Concretely, before `create_item`, read `aif-check-scheme.py --roles <scheme> --format json` (no dump needed) and use its `required_roles` array verbatim, in order. This JSON shape is documented in `aif-arguments`' SKILL.md as the stable cross-skill contract.

### 1a. 🟠 Sub-issue: premise *arity*, not just naming

Renaming alone won't fully fix the `cause_to_effect` RAs. That scheme requires **two distinct premises** — a `causal_generalization` ("X-type causes Y-type") and a `cause_present` ("X is present here") — but several ATAM RAs supply a **single** `["cause"]` premise. So ATAM must either:

- **(a)** split the inference into the two premises the scheme expects (preferred — it makes the defeasible generalization explicit and attackable), **or**
- **(b)** if only one premise is genuinely available, tag a scheme whose required roles match what's actually present (e.g. a single-premise causal step may be better modeled differently).

The `evidence_to_hypothesis` RAs supply ≥2 premises (arity OK) but tag them all `observation`; they're missing the `hypothesis_predicts` premise role. Same choice applies: add the predictive premise, or retag.

---

## 2. 🟡 Mint an `AifPA` (or record resolution) when a CQ challenge is decided

**Observed, lower priority.** All 14 `AifCA` attacks in the store show as `[D1]` *unresolved* because there are **0 `AifPA`** nodes. Yet many of these CAs already carry an `attributes.outcome` like `cq_defeated_finding_stands` or `landed_drove_revision` — i.e. the dialectic *was* resolved, ATAM just records the outcome as a CA attribute instead of minting a preference node that the validator recognizes as a resolution.

This is not wrong (the history is preserved), but it means `aif-validate.py`'s dialectical-resolution view always reports every ATAM attack as open. If you want the validator's `[D1]` signal to be meaningful for ATAM graphs, emit an `AifPA(preferred, dispreferred)` when a CQ is decided. Otherwise, treat `[D1]` warnings on ATAM graphs as expected noise. No change required if the `outcome` attribute is considered sufficient.

---

## Summary for triage

| Item | Severity | Action on ATAM side |
|------|----------|---------------------|
| 1. premise_roles use ad-hoc names | 🟠 | Emit canonical Walton roles from `--roles <scheme>`; ~per-finding metadata fix |
| 1a. cause_to_effect supplied 1 premise, scheme needs 2 | 🟠 | Split into `causal_generalization` + `cause_present`, or retag |
| 2. no AifPA → every attack reads as unresolved | 🟡 | Optional: mint AifPA on CQ decision, or accept `[D1]` as noise |

Item 1 is the load-bearing one: it makes every ATAM-emitted RA fail Layer-2 validation even though the structural graph is clean (0 `[S1]` dangling links, 0 cycles). Aligning ATAM's emitted `premise_roles` with the registry is what closes the gap.
