# ATAM Entities — Ontology Reference

The full catalog of things the ATAM workflow names, measures, decides about, or reasons over. Phase artifacts should use these canonical terms verbatim so findings are traceable across documents.

The same word (e.g. "scenario") can play different roles in different places — types below are disambiguated by **kind**: *people*, *object*, *decision*, *quality*, *artifact*, *scenario-part*, *finding*, *relationship*.

---

## 1. People & roles

| Role | What they bring to the evaluation |
|------|------------------------------------|
| **Evaluation lead** | Runs the ATAM, owns the method |
| **Scribe** | Captures findings verbatim (R/SP/TP/NR) |
| **Questioner** | Asks probing questions in Phase 6/8 |
| **Architect / architecture owner** | Presents the architecture, defends decisions |
| **Project decision maker / sponsor** | Owns business drivers; can authorize change |
| **Business stakeholder** | Provides business goals, priorities, constraints |
| **User / customer (proxy)** | Source of use-case scenarios |
| **Developer** | Source of modifiability/testability evidence |
| **Operator / SRE** | Source of availability/deployability/observability evidence |
| **Security / compliance / auditor** | Source of security and regulatory constraints |
| **Stakeholder proxy** | When the real role isn't in the room (often the user running the skill) |

When the same person plays multiple roles, record all of them — different findings cite different roles.

---

## 2. Objects — what exists in & around the system

- **System under evaluation** — the unit of analysis; has explicit boundaries
- **Architecture** — the *description* (views, diagrams, ADRs), distinct from the running system
- **Component / module** — units of decomposition
- **Connector / interface** — how components communicate (sync HTTP, async queue, shared DB, …)
- **Deployment unit** — what ships together (binary, container, lambda)
- **External dependency** — systems we don't control but rely on
- **Data store** — DBs, caches, queues, blob stores (called out separately because they dominate availability/performance reasoning)
- **Trust boundary** — line across which authentication/authorization is enforced
- **Bounded context** — domain-language and ownership boundary
- **ADR / design doc / diagram** — written record of a decision
- **Codebase** — the source-of-truth artifact when docs disagree with reality

---

## 3. Decisions — what gets chosen, recorded, defended

- **Architectural decision** — recorded in an ADR; has context, options, choice, consequences
- **Architectural approach / style** — layered, microservices, event-driven, CQRS, hexagonal, …
- **Tactic** — narrower choice attached to a QA: caching (perf), redundancy (avail), rate-limit (sec), DI (mod), …
- **Technology selection** — concrete product/library binding
- **Boundary placement** — where a service / module / context begins and ends
- **Binding-time decision** — compile-time vs deploy-time vs runtime configuration
- **Tradeoff resolution** — which QA wins when two pull in opposite directions

Every decision is a candidate **evidence anchor** for a finding.

---

## 4. Qualities — what we measure & qualify the system against

### 4.1 Quality attributes (top-level)

`performance` · `availability` · `security` · `modifiability` · `usability` · `testability` · `deployability` · `scalability` · `interoperability` · `observability` · `cost`

### 4.2 Refinements (sub-dimensions of a QA)

- **Performance:** latency, throughput, jitter, capacity
- **Availability:** MTBF, MTTR, RPO, RTO, fault detection, recovery, prevention
- **Security:** confidentiality, integrity, authentication, authorization, non-repudiation, auditability
- **Modifiability:** change locality, ripple containment, binding-time deferral
- **Testability:** controllability, observability (of internals for test), coverage achievability
- **Deployability:** rollout granularity, rollback, blue/green, canary
- **Scalability:** horizontal/vertical, elasticity, partitioning
- **Observability:** logging, metrics, tracing, alerting
- **Cost:** capex/opex, per-request, idle

Full list with sample scenarios in `quality-attributes.md`.

### 4.3 Response measures (the actual numbers)

Examples: *p99 ≤ 300ms*, *RTO ≤ 30s*, *≤ 5 modules touched*, *0 unauthorized logins*.
**The quantitative bit at the end of every scenario.** No measure → not a real scenario.

---

## 5. Process artifacts — what the method produces & reasons over

| Artifact | Produced in | Notes |
|----------|-------------|-------|
| **Business driver / goal** | Phase 2 | Why the system exists, in business terms |
| **Constraint** | Phase 2 | Schedule, budget, regulatory, technical, organizational |
| **Architectural approach inventory** | Phase 4 | Named, not yet analyzed |
| **Quality attribute scenario** | Phase 5, 7 | The testable unit of QA requirement |
| **Utility tree** | Phase 5 | Root *utility* → QAs → refinements → scenarios |
| **Utility tree leaf** | Phase 5 | A single scenario in the tree |
| **Importance rating (H/M/L)** | Phase 5 | How much the business cares |
| **Difficulty rating (H/M/L)** | Phase 5 | How hard for the architecture |
| **Probing question** | Phase 6, 8 | A question that, when answered, exposes a finding |
| **Finding** | Phase 6, 8 | Risk / Non-risk / Sensitivity point / Tradeoff point |
| **Risk theme** | Phase 9 | Group of related risks pointing at a systemic issue |
| **Recommendation** | Phase 9 | Actionable response to a theme |
| **Evidence** | All analytic phases | file:line, ADR ID, or quoted decision backing any claim |

---

## 6. Scenario internals — the six-part form

The six-part form is itself a small ontology. Every scenario MUST fill all six.

| Part | Role | Example |
|------|------|---------|
| **Source** of stimulus | Who/what triggers the situation | Authenticated user |
| **Stimulus** | The event arriving at the system | Issues search query |
| **Environment** | Operating mode | Normal load, prod |
| **Artifact** | Which component(s) are stimulated | Search service |
| **Response** | What the system does in reply | Returns ranked results |
| **Response measure** | Quantitative success criterion | p99 ≤ 300ms |

Environment vocabulary (use consistently): `normal` · `peak` · `degraded` · `failure` · `recovery` · `dev` · `staging` · `prod`.

---

## 7. Finding types — the core analytical distinctions

| Type | One-liner | Cardinality vs QAs | Example |
|------|-----------|---------------------|---------|
| **Risk (R)** | Decision (or its absence) likely to harm a QA | ≥ 1 QA affected (negative) | "Shared single Postgres for all services" |
| **Non-risk (NR)** | Decision judged sound after analysis | ≥ 1 QA affected (positive) | "JWT validated at gateway, not per service" |
| **Sensitivity point (SP)** | A component property critical to a QA response | Exactly 1 QA | "Cache TTL controls read latency" |
| **Tradeoff point (TP)** | A sensitivity point affecting **multiple** QAs, often opposing | ≥ 2 QAs | "Cache TTL: latency ↑ vs freshness ↓" |

Decision rule when classifying a finding:
1. Does it pin a specific component property? If **no**, it's R or NR.
2. If **yes**: does it affect **more than one** QA? → **TP**. Otherwise → **SP**.

---

## 8. Relationships — the edges of the graph

```
business driver
    ↓ motivates
quality attribute (prioritized)
    ↓ refines into
scenario  ── rated by ──>  (Importance, Difficulty)
    ↑ addresses
architectural approach
    ↑ probes
probing question
    ↓ yields
finding (R | NR | SP | TP)
    ↓ cites
evidence
    ↓ rolls up into  (only Risks)
risk theme
    ↓ threatens
business driver
    ↑ addresses
recommendation
```

Additional edges:

- A **sensitivity point** *becomes a* **tradeoff point** when it touches ≥ 2 QAs.
- A **constraint** *limits* the option space of an **architectural decision**.
- An **ADR** *records* an **architectural decision** and *serves as* **evidence**.
- A **risk theme** *aggregates* risks across multiple **scenarios** — themes are cross-scenario.

---

## 9. Glossary cross-check

If a phase artifact uses a word not in this file, either:
- Add it here (it's a real new entity), or
- Replace it with the canonical term from here (it was a synonym).

This keeps the consolidated report (`REPORT.md`) consistent and grep-able.
