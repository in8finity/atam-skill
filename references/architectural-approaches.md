# Architectural Approaches Catalog

Used in Phase 4 to **name** the approaches present, and in Phase 6/8 to reason about which QA they address (and what they cost elsewhere).

## Structural styles
- **Layered** — separation of concerns; aids modifiability, hurts performance.
- **Microservices** — independent deployability; hurts consistency, raises operational cost.
- **Modular monolith** — single deployable, internal module boundaries.
- **Event-driven / pub-sub** — decoupling, async; hurts traceability.
- **CQRS** — separate read/write models; aids read scalability, hurts simplicity.
- **Event sourcing** — log as source of truth; aids auditability, hurts query latency.
- **Hexagonal / ports & adapters** — testability, modifiability.
- **Pipe-and-filter** — composability for stream processing.
- **Client-server / N-tier** — classic deployment topology.
- **Serverless / FaaS** — elastic scaling, cold start tradeoff.

## Availability tactics
- Redundancy (active-active, active-passive)
- Health checks + automatic failover
- Circuit breakers, bulkheads, timeouts
- Retries with backoff + idempotency keys
- Graceful degradation
- Disaster recovery (RPO/RTO targets)

## Performance tactics
- Caching (client, edge, application, database)
- Read replicas, materialized views
- Asynchronous processing / queues
- Connection pooling
- Compression, batching
- CDN / edge compute

## Security tactics
- Authentication (OAuth2, OIDC, mTLS)
- Authorization (RBAC, ABAC, ReBAC)
- Encryption in transit / at rest
- Secrets management (Vault, KMS)
- Input validation, output encoding
- Rate limiting, WAF
- Audit logging, immutable trails

## Modifiability tactics
- Information hiding / encapsulation
- Anti-corruption layer between bounded contexts
- Dependency injection
- Plugin / strategy patterns
- Configuration over code
- Feature flags

## Scalability tactics
- Horizontal scaling / stateless services
- Sharding / partitioning
- Read/write splitting
- Backpressure
- Autoscaling

## Observability tactics
- Structured logging
- Distributed tracing (W3C Trace Context)
- RED / USE metrics
- SLOs + error budgets
- Synthetic monitoring

---

When mapping code to this catalog in Phase 4, look for:
- Directory layout (layered vs feature-sliced)
- Cross-service comms (HTTP vs gRPC vs queue)
- Data store fan-out (one DB vs per-service)
- Presence of CI/CD pipelines, IaC, dashboards
- Auth flow, secrets handling
