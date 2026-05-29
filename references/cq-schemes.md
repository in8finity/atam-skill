# Critical-Questions Catalog — Walton Schemes for ATAM Findings

Maps Walton argumentation schemes to the kinds of reasoning ATAM Findings, RiskThemes, and Recommendations commonly invoke. Each scheme comes with its canonical critical-questions (CQs); each CQ is a probe that, if answered productively, can revise or withdraw the original argument.

Used by the **challenge step** (see SKILL.md §11) and consumable by the `aif-arguments` skill: each scheme name here is also an AIF `argumentation_scheme` value.

> **Recording note.** There is no `IndividualCriticalQuestion` hashharness type. The challenge step records its work two ways: (1) the `cli.py challenge` verb writes a lightweight **`AtamEvidence`** record (`kind=quote`) with `attributes.challenged_finding_sha` naming the target — this is the marker the P9 gate looks for; (2) if you hand off to `aif-arguments` for a full argument graph, each CQ becomes an `AifInode` (the question as a claim) plus an `AifCA` (the conflict/attack against the finding's `AifRA` inference node). Use the lightweight path by default; reach for the AIF graph when the reasoning is contested enough to warrant explicit premise/conclusion/attacker modeling.

> **AIF authoring contract (premise roles + arity).** When you build an `AifRA` for a finding, `aif-validate.py`'s `[F3]` scheme-fullness check requires `AifRA.attributes.premise_roles` to be the scheme's **canonical Walton role names, in order**, with **one premise per role** (arity). Ad-hoc names (`["cause"]`, `["observation","observation"]`) fail — a 2026-05-29 audit found 10/13 ATAM-emitted RAs failing exactly this. The **authoritative source** is the aif-arguments JSON contract — do not hardcode or scrape the human text:
> ```bash
> aif-check-scheme.py --roles <scheme_key> --format json   # → {required_roles, ...}
> ```
> `cli.py challenge` also surfaces this per detected scheme in its `aif_authoring` output block. Note: tag `AifRA.attributes.scheme` with the **registry key** — this skill's `precedent` maps to the registry's `analogy`.
>
> | Scheme (CQ catalog name) | Registry key to tag | Required `premise_roles` (in order) |
> |---|---|---|
> | negative_consequences | `negative_consequences` | `action`, `bad_consequence` |
> | cause_to_effect | `cause_to_effect` | `causal_generalization`, `cause_present` |
> | sign | `sign` | `sign_observed`, `sign_indicates` |
> | evidence_to_hypothesis | `evidence_to_hypothesis` | `hypothesis_predicts`, `observation` |
> | abductive | `abductive` | `data`, `best_explanation` |
> | precedent | `analogy` | `base_case`, `similarity` |
> | practical_reasoning | `practical_reasoning` | `goal`, `means` |
>
> **Arity matters (1a).** `cause_to_effect` needs *two distinct* premises — a `causal_generalization` ("X-type causes Y-type") and a `cause_present` ("X holds here") — not one merged `["cause"]`. If only one premise genuinely exists, either split the reasoning to make the defeasible generalization explicit and attackable, or tag a scheme whose roles match what's present. Same for `evidence_to_hypothesis`: supply a `hypothesis_predicts` premise, not three `observation`s.
>
> **Resolution (item 2, optional).** When a CQ is decided, mint an `AifPA(preferred, dispreferred)` so `aif-validate.py` doesn't read the attack as unresolved (`[D1]`). Recording the outcome only as a CA attribute preserves history but leaves every attack "open" in the validator's view.

## How to use this doc

1. Identify what argumentative shape your Finding (or Recommendation) takes — see "Scheme triggers" below.
2. Look up the scheme's CQ list.
3. **Prioritize**: not every CQ is productive for every Finding. Tier them A/B/C as we did in practice.
4. Answer the Tier-A questions seriously, conceding where they land.
5. Either: (a) stand-pat with a defended record, (b) revise via `supersedes`, or (c) withdraw the Finding.
6. Record the exchange as AIF nodes — see `examples/challenge-f16r.md` for a worked exchange.

---

## Schemes most relevant to ATAM

### 1. Argument from Negative Consequences (`walton.negative_consequences`)

**Form:** "X has negative consequences C; therefore X should not be done / is risky."
**Triggers:** Risk findings (type=R) — almost all of them invoke this implicitly.

**CQs (Walton 1995):**
- CQ1 (likelihood_of_consequence) — How likely is the negative consequence to actually occur?
- CQ2 (evidence_for_consequence_claim) — Is the body of evidence here strong enough?
- CQ3 (opposite_consequences_to_consider) — Are there positive consequences that outweigh the negative?

### 2. Cause-to-Effect (`walton.cause_to_effect`)

**Form:** "Cause C produces effect E; we observe condition X (which looks like C); therefore E will follow."
**Triggers:** Findings that claim a causal mechanism — e.g. "duplication without test → drift", "no circuit breaker → cascading failure".

**CQs:**
- CQ4 (generalization_holds) — Does the general causal rule actually hold?
- CQ5 (no_intervening_cause) — Is the effect attributable to the named cause, or to something else?
- CQ6 (no_blocker) — Is there a blocker that would prevent the causal mechanism from completing (e.g. a workaround already in place)?

### 3. Sign (`walton.sign`)

**Form:** "Observation X is typically a sign of S; we see X; therefore S is the case."
**Triggers:** Findings using past incidents as evidence of systemic risk (e.g. "the 2026-05-11 incident proves systemic schema fragility").

**CQs:**
- CQ7 (sign_event_correlation_strength) — How strongly does X correlate with S? One incident vs many?
- CQ8 (alternative_event_accounting_for_sign) — Could X be explained by something other than S (e.g. a one-off refactor)?

### 4. Evidence to Hypothesis (`walton.evidence_to_hypothesis`)

**Form:** "If hypothesis H were true, we'd observe O; we observe O; therefore H is likely true."
**Triggers:** Findings claiming an architecture has a property (e.g. "the codebase is fragile") based on observed signals (TODOs, churn rates, single points of failure).

**CQs:**
- CQ9 (hypothesis_entails_observation) — Does H actually predict O?
- CQ10 (observation_actually_made) — Are the claimed observations accurate and current?
- CQ11 (alternative_reason_for_observation) — Could O be explained by H' instead of H (e.g. "deliberate layer-appropriate split" vs "duplication")?

### 5. Inference to Best Explanation / Abductive (`walton.abductive`)

**Form:** "These symptoms are best explained by H; therefore H is likely true."
**Triggers:** Synthesis claims — e.g. "the dominant risk theme is silent schema drift".

**CQs:**
- CQ12 (satisfactoriness_of_explanation) — Does H actually explain the symptoms, or is it just a label?
- CQ13 (comparison_with_alternatives) — Is H better than the alternative "the team is working as designed"?
- CQ14 (thoroughness_of_inquiry) — Has the conclusion been reached after sufficient investigation?
- CQ15 (continue_inquiry_vs_close) — Should we gather more evidence before treating this as established?

### 6. Precedent (`walton.precedent`)

**Form:** "Case Y was treated as risk R; case X is similar to Y; therefore X is also risk R."
**Triggers:** Findings appealing to prior incidents, sibling findings ("F18 is like F14"), or external industry incidents.

**CQs:**
- CQ16 (rule_applies_to_present_case) — Does the prior rule actually apply, or is the present case different in load-bearing respects?
- CQ17 (cited_case_legitimate) — Is the cited precedent genuinely similar, or only superficially?
- CQ18 (recognized_exception_already_exists) — Has the team already adopted a practice that legitimately covers cases like this?

### 7. Practical Reasoning (`walton.practical_reasoning`)

**Form:** "Goal G; means M achieves G; therefore do M."
**Triggers:** Recommendations. Every R record invokes this scheme.

**CQs:**
- CQ_other_means — Are there other means M' that achieve G more cheaply?
- CQ_best_means — Is M the best means, considering side effects?
- CQ_side_effects — Will M produce undesirable side effects?
- CQ_possibility — Is M feasible given existing constraints (ownership, third-party dependencies, etc.)?

---

## Scheme triggers — quick reference

| Finding shape | Likely scheme | Key CQs to ask |
|---|---|---|
| Pure risk claim (R/high) | negative_consequences | likelihood, evidence strength, opposite consequences |
| Causal-mechanism claim ("→") | cause_to_effect | generalization, intervening cause, blocker |
| "This already happened" claim | sign | correlation strength, alternative accounting |
| Architecture-property claim | evidence_to_hypothesis | observation accuracy, alternative reason for observation |
| Risk theme / synthesis | abductive | satisfactoriness, alternatives, thoroughness |
| "F18 is like F14" sibling claim | precedent | rule applies, cited case legitimate, recognized exception |
| Recommendation (R1-R4) | practical_reasoning | other means, best means, side effects, possibility |

A typical Finding invokes **2-3 schemes simultaneously**:
- F18: cause_to_effect (duplication→drift) + sign (H-collapse incident) + precedent (F14, F5)
- F16R: evidence_to_hypothesis (architecture lacks attribution) + practical_reasoning (R4 prescription)

Run CQs for each invoked scheme; cross-cutting concessions ("not duplication; cross-layer interface") may dissolve multiple schemes at once.

---

## Tiering

Not every CQ is productive. Default tiers:

- **Tier A (must answer):** CQs whose answer would change the Finding's severity, type, framing, or remedy.
- **Tier B (refines, doesn't overturn):** CQs that calibrate but don't shift core claims.
- **Tier C (procedural):** CQs answered routinely (e.g. "observation_actually_made" — yes, I read the file).

Tier A in practice tends to be:
- `alternative_reason_for_observation` (CQ11) — the steelman question
- `no_intervening_cause` (CQ5) — what's *actually* causing this?
- `other_means` — is there a cheaper remedy?
- `comparison_with_alternatives` (CQ13) — is the risk reading really better than "working as designed"?

When in doubt, answer Tier A first.

---

## Worked exchanges

- `examples/challenge-f18.md` — duplication framing dissolved into cross-layer interface (F18 → F18R, severity med → low)
- `examples/challenge-f14.md` — same critique applied partially; F14 kept high but reframed (F14 → F14R)
- `examples/challenge-f16r.md` — R4 split into R4a + R4b after `other_means` and `no_intervening_cause` landed

(Examples written as we accumulate exchanges; not a complete reference.)
