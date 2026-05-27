# Probing Questions by Quality Attribute

Use in Phase 6 and Phase 8 to interrogate the architecture against a scenario. Each question is designed to surface a **risk**, **sensitivity point**, or **tradeoff**.

## Performance
- What is the end-to-end timeout budget, and how is it allocated across components?
- Where are the synchronous fan-outs? What's the worst-case depth?
- What is cached, with what TTL, and what is the invalidation strategy?
- What happens under thundering-herd or cache-stampede?
- What is the slowest dependency on the critical path?
- Is there backpressure, or do queues grow unboundedly?

## Availability
- What are the single points of failure on the critical path?
- What's the RTO and RPO, and has it been tested?
- How is failover triggered? What's the false-positive rate?
- What happens during a partial dependency outage (graceful degradation vs hard fail)?
- Are retries idempotent? Where could they amplify load?
- How is deployment-induced downtime avoided?

## Security
- Where is the trust boundary? Who/what is authenticated at each boundary?
- How are secrets stored, rotated, and accessed?
- What happens if a single service is compromised — what's the blast radius?
- How is data encrypted in transit and at rest? Key management?
- Is there an audit trail for sensitive actions? Is it tamper-evident?
- How are dependencies (libraries, containers) scanned and patched?

## Modifiability
- What is the typical cost (touches, days) of adding a new feature of type X?
- Where are the "god modules" — what fraction of changes touch them?
- Are bounded contexts enforced, or do schemas leak across services?
- How are breaking changes to APIs/contracts handled (versioning, deprecation)?
- What's the test pyramid? Can a developer get fast feedback locally?

## Testability
- Can each component be tested in isolation? What's mocked, what's real?
- Are flaky tests tracked and quarantined?
- Is there a staging environment that mirrors prod, and how is data parity maintained?

## Deployability
- What's the deployment unit and frequency?
- Can a single component be rolled back without rolling back others?
- Are canaries / blue-green / progressive rollouts used?
- How is schema migration sequenced with code deploy?

## Scalability
- What scales horizontally, what doesn't, and why?
- Where is the next bottleneck assumed to be? Has it been load-tested?
- Are stateful components partitioned? How is rebalancing handled?

## Observability
- For a user-reported issue, what's the MTTR from report to identified root cause?
- Are traces propagated end-to-end? Is there sampling bias?
- What alerts page humans, and what's the false-positive rate?

---

## Red-flag patterns worth probing regardless of QA

- "We've never tested that" → risk
- "Only one person knows how that works" → risk (bus factor)
- "It works because of <subtle property of component X>" → sensitivity point
- "We made it faster by giving up <other QA>" → tradeoff
- "We rely on <external system> being available" → risk
