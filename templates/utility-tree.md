# 04 — Quality Attribute Utility Tree

Leaves are six-part scenarios. Each leaf is rated **(Importance, Difficulty)** each H/M/L.
- **Importance:** how much the business cares
- **Difficulty:** how hard it is for the architecture to achieve

Analysis (Phase 6) focuses on **(H,H)** and **(H,M)** leaves.

```
Utility
├── Performance
│   ├── Latency
│   │   └── [(H,H)] Authenticated search returns p99 ≤ 300ms under 1k rps  ← scenario
│   └── Throughput
│       └── [(H,M)] Ingest service sustains 50k events/s without backpressure
├── Availability
│   ├── Fault tolerance
│   │   └── [(H,H)] Single DB node loss → failover ≤ 30s, ≤ 5 dropped reqs
│   └── Disaster recovery
│       └── [(M,H)] Region loss → RPO ≤ 5min, RTO ≤ 1h
├── Security
│   └── ...
├── Modifiability
│   └── ...
└── Observability
    └── ...
```

## Prioritized leaves for Phase 6 analysis

| # | QA | Scenario (one-line) | (I, D) |
|---|----|---------------------|--------|
| 1 |    |                     |        |
| 2 |    |                     |        |
| 3 |    |                     |        |
