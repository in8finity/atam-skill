# 05 — Analysis of Architectural Approaches

One section per prioritized scenario from the utility tree (Phase 5).

---

## Scenario S-<nn>: <one-line summary>

**QA:** <attribute>
**Priority:** (I=<>, D=<>)

### Six-part form
| Part | Value |
|------|-------|
| Source | |
| Stimulus | |
| Environment | |
| Artifact | |
| Response | |
| Response measure | |

### Architectural approach(es) addressing this scenario
- <approach 1 — e.g., "Redis read-through cache in front of Postgres">
- <approach 2 — e.g., "Connection pooling with PgBouncer">

### Probing questions asked
1. <question> → <answer / evidence>
2. <question> → <answer / evidence>

### Findings

#### Risks (R)
| ID | Risk | Evidence | Affected QA |
|----|------|----------|-------------|
| R-<nn> | <description> | <file:line, ADR-NNN, or stated decision> | <QA> |

#### Non-risks (NR)
| ID | Decision | Why it's sound |
|----|----------|----------------|
| NR-<nn> | | |

#### Sensitivity points (SP)
| ID | Property | Component(s) | Affected QA response |
|----|----------|--------------|----------------------|
| SP-<nn> | <e.g., cache TTL> | <e.g., search-svc> | <e.g., read latency> |

#### Tradeoff points (TP)
| ID | Property | QAs affected | Direction of tradeoff |
|----|----------|--------------|------------------------|
| TP-<nn> | <e.g., cache TTL> | latency ↑ vs freshness ↓ | <description> |

---

<repeat per scenario>
