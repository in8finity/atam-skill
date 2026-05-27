# Entity Lifecycle Across ATAM Phases

Companion to `entities.md`. Where `entities.md` catalogs the *what*, this file traces the *when* — how each entity is born, accretes attributes, becomes linked to other entities, and (sometimes) changes type across the 9 ATAM phases.

Use this when:
- Reviewing a phase artifact for completeness — "did this scenario gain the attributes it should have by now?"
- Auditing the consolidated `REPORT.md` — "does every risk trace back to a driver via the expected edges?"
- Debugging a stuck evaluation — "we can't form risk themes (P9) because findings have no `affected_QAs` (P6 attribute missing)"

---

## 1. Phase-by-phase delta

| Phase | Entities born | Attributes added | Links formed |
|-------|---------------|------------------|--------------|
| **P0 Setup** | system-under-evaluation, stakeholder roster, input inventory | — | stakeholder → role |
| **P1 Present ATAM** | — | — | — |
| **P2 Drivers** | business driver, constraint, QA (as driver) | driver: *priority*; QA: *priority*; constraint: *kind* | driver ↔ QA (*motivates*); constraint → system (*limits*) |
| **P3 Architecture** | component, connector, deployment unit, data store, trust boundary, external dependency, ADR | architecture: *summary*; component: *responsibility* | architecture ⊇ components; component ↔ connector; ADR → decision |
| **P4 Approaches** | architectural approach, tactic | approach: *type* (style/pattern/tactic) | approach ↔ component(s); tactic ↔ approach |
| **P5 Utility tree** | QA refinement, scenario (leaf), (I,D) rating | QA: *refinements list*; scenario: *six-part*, *(I,D)*, *selected_for_analysis* | utility ↔ QA ↔ refinement ↔ scenario; scenario → artifact-component |
| **P6 Analyze** | probing question, finding (R/NR/SP/TP), evidence | scenario: *analyzed=true*; approach: *scenarios-addressed* | scenario ↔ approach (*addresses*); approach ↔ question; question → finding; finding → evidence; finding ↔ QA; finding → component |
| **P7 Brainstorm** | use-case / growth / exploratory scenario, vote | scenario: *category*, *vote rank* | scenario → stakeholder (*proposed by*); scenario ↔ QA |
| **P8 Re-analyze** | (more) findings | P7 scenarios: *analyzed=true* | same edges as P6, now over P7 scenarios |
| **P9 Results** | risk theme, recommendation | risk: *theme membership*; driver: *threatened-by* | risk → theme; theme → driver (*threatens*); theme → recommendation (*addresses*); **SP → TP** if cross-QA found |

---

## 2. Per-entity lifecycle

### Business driver
- *Born* P2 with `{description}`
- *Grows:* `priority` (P2), `threatened_by[]` (P9)
- *Linked* to QAs (P2), themes (P9), recommendations (P9)

### Constraint
- *Born* P2 `{kind, description}`
- *Linked* to architectural decisions (P3+) as limits
- *Cited* as evidence in P6/P8 findings

### Quality attribute (QA)
The most attribute-rich entity by the end of the process.
- *Born* P2 as driver
- *Grows:* `refinements[]` (P5), `scenarios[]` (P5+P7), `findings[]` (P6/P8), `themes_touching[]` (P9)

### Component / connector / data store
- *Born* P3
- *Grows:* `implements_approach` (P4), `sensitivity_locus[]` (P6), `risk_evidence_for[]` (P6/P8)

### Architectural approach
- *Born* P4 `{name, type}`
- *Grows:* `addresses_scenarios[]` (P6), `probed_with[]` (P6/P8), `findings[]` (P6/P8)

### Scenario — the most lifecycle-rich entity
- **P5 birth (utility-tree path):** `{QA, refinement, six-part, (I,D)}`, category implicit = `anticipated`
- **P5 prioritization:** `selected_for_analysis ∈ {yes, no}`
- **P6 analysis:** gains `addressing_approaches[]`, `probing_questions[]`, `findings[]`
- **P7 alt birth (brainstorm path):** `{six-part, category ∈ use|growth|exploratory, vote_rank}`
- **P8 analysis:** same attribute accretion as P6
- **P9:** may be cited as the source of a themed risk

### Probing question
- *Born and consumed* in P6/P8
- Permanently attached to `{scenario, approach, findings_yielded[]}`

### Finding (R / NR / SP / TP)
- *Born* P6/P8 with `{type, description, affected_QAs[], evidence, scenario, approach, component_locus}`
- **Key transition: SP → TP** when later analysis shows it touches a second QA
- Risks gain `theme` membership in P9

### Risk theme
- *Born P9 only.* Pure aggregate `{member_risks[], threatened_drivers[], recommendation}`
- Has no independent existence before P9

### Recommendation
- *Born* P9, linked to exactly one theme

### Evidence
- Never "born" — only *cited*. A reference to a pre-existing artifact (ADR, `file:line`, quoted decision)

---

## 3. Key state transitions

| # | Transition | Phase | Trigger |
|---|------------|-------|---------|
| 1 | QA → prioritized QA | P2 | Rank assigned, becomes a driver QA |
| 2 | Refinement → scenario | P5 | Abstract concern made testable via six-part form |
| 3 | Scenario → prioritized leaf | P5 | (I,D) rating + `selected_for_analysis=true` |
| 4 | Approach → analyzed approach | P6 | First probing question asked against it |
| 5 | **SP → TP** | P6/P8 | Cross-QA effect discovered |
| 6 | Risk → themed risk | P9 | Grouped with related risks into a theme |
| 7 | Theme → actioned theme | P9 | Recommendation attached |

The **SP → TP** transition is the single most important promotion — it is often the deliverable of Phase 8, where new scenarios surface the second QA that elevates a sensitivity into a tradeoff.

---

## 4. Graph density growth

```
After P2 :  small star — drivers ↔ QAs
After P3-4: two disconnected components —
              (system/components/approaches) and (drivers/QAs)
After P5 : ★ fusion ★ — utility tree connects them via scenarios:
              QA → refinement → scenario → artifact-component
After P6 : dense local meshes around each analyzed scenario:
              scenario ↔ approach ↔ question ↔ finding ↔ evidence
After P7-8: more scenarios, more meshes, reaching new corners of
              the component graph
After P9 : themes become super-nodes; the graph closes into a CYCLE
              driver → QA → scenario → finding → theme → driver
          That cyclic closure is what makes the report defensible —
          every recommendation traces back to a business driver via
          evidence.
```

If, at end of P9, you cannot draw the full cycle for every recommendation, the evaluation has a gap. Mark it in the "Known gaps" section of `REPORT.md` rather than papering over it.

---

## 5. Mutability classes

| Class | Entities | Rationale |
|-------|----------|-----------|
| **Append-only** (write once, never edit) | finding, evidence citation, ADR reference, probing question, vote | These record what was said and observed — rewriting destroys the audit trail |
| **Attribute-accreting** (grow, never lose attributes) | QA, scenario, approach, component, business driver | Each phase adds new facets; prior attributes remain valid |
| **State-transitioning** (typed promotions) | SP ↔ TP, scenario `selected_for_analysis`, risk `themed` | Discrete promotions; the prior state is still meaningful and worth recording |
| **Phase-terminal** (born late, cannot exist earlier) | risk theme, recommendation | Aggregates over earlier work — must wait for sufficient findings |

When in doubt, **prefer append over edit**. If a scenario's (I,D) rating changes after P5 because new information surfaces in P7, do *not* overwrite the original — append a new rated version with a reason. This preserves the reasoning chain.

---

## 6. Quick completeness check per phase

A phase is "done" only when every entity it was supposed to introduce or enrich is accounted for:

| End of phase | Required minimum |
|--------------|------------------|
| P2 | ≥ 3 prioritized QAs, ≥ 1 business driver per QA, constraints enumerated |
| P3 | Architecture summary with named components; key data stores & trust boundaries identified |
| P4 | Every component mapped to ≥ 1 architectural approach or tactic |
| P5 | Utility tree with ≥ 1 leaf per top-3 QA; every leaf has full six-part form + (I,D) |
| P6 | Every (H,H) and (H,M) leaf has ≥ 1 probing question and ≥ 1 finding |
| P7 | ≥ 1 scenario in each of {use, growth, exploratory}; votes recorded |
| P8 | Top-voted P7 scenarios analyzed to the same standard as P6 |
| P9 | Every R rolled into a theme; every theme linked to ≥ 1 driver and ≥ 1 recommendation |

Use this as the gate-acceptance checklist when the user is reviewing each phase.
