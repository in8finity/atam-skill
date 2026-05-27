# Quality Attribute Taxonomy

Combines classic ATAM QAs (Bass/Clements/Kazman, *Software Architecture in Practice*) with ISO/IEC 25010.

For each QA: short definition, common refinements, and a sample six-part scenario.

## Performance
**Definition:** Ability to meet timing requirements.
**Refinements:** latency, throughput, jitter, capacity.
**Sample scenario:** Under 10k req/s sustained load (environment), an HTTP request (stimulus) arriving at the API gateway (artifact) is served (response) with p99 ≤ 200ms (response measure).

## Availability
**Definition:** Probability the system is operational when needed.
**Refinements:** fault detection, recovery, prevention, MTBF, MTTR.
**Sample scenario:** A database node crashes (stimulus, source=hardware) during peak hours (environment); the system (artifact) fails over to a replica (response) within 30s with ≤ 5 dropped requests (response measure).

## Security
**Definition:** Ability to protect data and services from unauthorized access while providing service to authorized users.
**Refinements:** confidentiality, integrity, authentication, authorization, non-repudiation, auditability.
**Sample scenario:** A malicious actor (source) submits 1000 credential-stuffing attempts/min (stimulus) against the login endpoint (artifact) from outside the network (environment); the system blocks the source IP and logs the event (response) within 60s with zero successful unauthorized logins (response measure).

## Modifiability
**Definition:** Cost of making changes.
**Refinements:** localizing changes, preventing ripple effects, deferring binding time.
**Sample scenario:** A developer (source) needs to add a new payment provider (stimulus) to the production codebase (environment, artifact=payment module); the change is implemented and deployed (response) in ≤ 5 person-days touching ≤ 3 modules (response measure).

## Usability
**Definition:** How easy it is for users to accomplish a task and the kind of support the system provides.
**Refinements:** learnability, efficiency, memorability, error prevention, satisfaction.

## Testability
**Definition:** Ease with which software can be made to demonstrate its faults.
**Refinements:** test coverage achievability, controllability, observability.
**Sample scenario:** A QA engineer (source) writes an integration test (stimulus) for the order pipeline (artifact) in CI (environment); the test runs deterministically in ≤ 30s without external dependencies (response measure).

## Deployability
**Definition:** Ability to be deployed reliably and reversibly.
**Refinements:** rollout granularity, rollback, blue/green, canary support.

## Scalability
**Definition:** Ability to handle growth in load, data, or users.
**Refinements:** horizontal vs vertical, elastic, partitioning.

## Interoperability
**Definition:** Ability to exchange information and use the information that has been exchanged.

## Observability (modern addition)
**Definition:** Ability to understand internal state from external outputs.
**Refinements:** logging, metrics, tracing, alerting.

## Cost (often treated as a constraint, but worth tracking)
**Refinements:** capex vs opex, per-request cost, idle cost.

---

## Quick prioritization heuristic

When forced to pick top QAs, ask the user:
1. What would cause a customer to leave? → maps to availability, performance, usability
2. What would cause a regulator/auditor to act? → security, auditability
3. What would slow down the team most as the system grows? → modifiability, testability, deployability
4. What does the CFO worry about? → cost, scalability
