# ATAM — Method Reference

**Source:** Kazman, Klein, Clements. *ATAM: Method for Architecture Evaluation*. SEI Technical Report CMU/SEI-2000-TR-004.

## Purpose

ATAM helps stakeholders understand the consequences of architectural decisions with respect to **quality attribute requirements**. It does not score architectures; it surfaces **risks**, **sensitivity points**, and **tradeoff points** that need attention.

## The 9 Steps

| # | Step | Output |
|---|------|--------|
| 1 | Present the ATAM | Shared understanding of the method |
| 2 | Present business drivers | Business goals, constraints, top QAs |
| 3 | Present the architecture | Architectural overview |
| 4 | Identify architectural approaches | List of styles/patterns/tactics in use |
| 5 | Generate quality attribute utility tree | Prioritized (Importance × Difficulty) QA scenarios |
| 6 | Analyze architectural approaches | Risks, non-risks, sensitivity points, tradeoffs for high-priority leaves |
| 7 | Brainstorm and prioritize scenarios | Use / growth / exploratory scenarios, voted |
| 8 | Analyze architectural approaches (again) | Findings against new scenarios |
| 9 | Present results | Risk themes, recommendations, consolidated report |

## Core concepts

### Quality Attribute (QA)
A measurable property of a system that indicates how well the system satisfies stakeholder needs *beyond* functional correctness. Examples: performance, availability, security, modifiability, usability, testability, deployability, scalability, interoperability.

### Scenario (six-part form)
A concrete, testable statement of a QA requirement. Six parts:
1. **Source** of stimulus (user, attacker, internal system, …)
2. **Stimulus** (event arriving at the system)
3. **Environment** (normal, overloaded, dev, prod, degraded, …)
4. **Artifact** (component or whole system being stimulated)
5. **Response** (what the system does)
6. **Response measure** (quantitative success criterion)

Example: "An authenticated user (source) issues a search query (stimulus) under normal load (environment) against the search service (artifact); the system returns ranked results (response) within 300ms p99 (response measure)."

### Utility Tree
Hierarchy with **utility** at the root, **quality attributes** at level 1, **refinements** at level 2, **scenarios** at leaves. Each leaf is annotated with **(Importance, Difficulty)** each rated H/M/L. Analysis focuses on (H,H) and (H,M) leaves.

### Three finding types

- **Risk (R):** An architectural decision (or its absence) that may cause undesirable consequences for one or more QAs.
  - *Example:* "All services share a single Postgres instance — risk for availability and scalability."

- **Sensitivity point (SP):** A property of one or more components that is critical for achieving a particular QA response.
  - *Example:* "Cache TTL is a sensitivity point for read latency."

- **Tradeoff point (TP):** A sensitivity point that affects **multiple** QAs, often in opposing directions.
  - *Example:* "Cache TTL is a tradeoff between read latency (longer TTL → faster) and data freshness (shorter TTL → fresher)."

- **Non-risk:** A decision that, after analysis, is judged sound for its QA goals. Worth recording — it documents *why* something is fine.

### Risk Themes
At the end, individual risks are grouped into **themes** — recurring patterns indicating a systemic issue (e.g., "no end-to-end timeout budget", "single points of failure in data plane"). Themes are mapped back to **business drivers** so leadership sees which goals are threatened.
