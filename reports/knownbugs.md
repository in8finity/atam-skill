# Known Bugs

Bugs surfaced during the ATAM evaluation of `happyhero` (workpackage `atam.case.uba-2026-05-27`, Phase 6 run on 2026-05-27). Two categories: (A) bugs in the ATAM controller itself, found by running it against a real codebase; (B) bugs in the `happyhero` analytics subsystem, captured as Finding records in hashharness.

---

## A. ATAM controller bugs

Both found *during* the live demo run, both fixed in the same session. Hashharness records in `atam.case.uba-2026-05-27` were not retroactively rewritten — the audit trail shows the controller's reasoning *at the time*, including the now-fixed misbehaviour.

### A1. `controller.state()` did not sort coverage / rating / hypothesis-update records by `created_at`

- **Symptom:** Selector kept picking probes for scenarios already marked `sufficient`. After updating S3's coverage from `in-progress @ 0.45` to `sufficient @ 0.7`, the next `next-probe` call still treated S3 as uncovered.
- **Cause:** `controller.py:state()` iterated `find_items` results in arbitrary order, using last-write-wins to pick "latest" per scenario. `find_items` does not guarantee `created_at` order, so the older in-progress coverage was sometimes the "last write" seen, overwriting the newer sufficient record in the dict.
- **Affected types:** `AtamCoverage`, `ScenarioRating`, `AtamHypothesisUpdate` — all three relied on the same naive pattern.
- **Fix:** Sort records by `created_at` ascending before the loop, so last-write-wins reliably yields the newest.
- **Locations (post-fix):** `scripts/controller.py:147-150` (ratings), `:159-162` (coverage), `:188-191` (hypothesis updates).
- **Status:** Fixed. Source files committed locally to `arch-tradeoff`.
- **Recommended follow-up:** Regression test that creates two coverage records for the same scenario with different statuses and asserts `state()` returns the newer one regardless of insertion order.

### A2. `select_probe()` did not short-circuit to closure

- **Symptom:** After all 5 scenarios reached `sufficient` and no hypotheses remained open, `next-probe` still returned a bank probe (`sec.blast-radius` for `scenario_id: null`) instead of `source=closure`.
- **Cause:** The bank-standard branch (step 2 of the priority pipeline) gated only on `expected_saturation_gain >= 0.35`, not on "is there any uncovered scenario or open hypothesis left at all". With 16 standard probes in the bank, most exceeded the threshold, so the selector never reached the closure step (step 5) until generation also failed (step 3 → 4).
- **Fix:** Added a closure short-circuit at the top of `select_probe()`: if both `state.uncovered_scenarios()` and `state.open_hypotheses()` are empty, return closure immediately.
- **Location (post-fix):** `scripts/selection.py:148-150`.
- **Status:** Fixed.
- **Recommended follow-up:** Unit test for the closure short-circuit; assert that the empty-state case returns `ProbeDecision.closure()` without touching the bank.

---

## B. happyhero subsystem bugs (production findings)

10 findings recorded against `atam.case.uba-2026-05-27`, ordered by severity. The audit trail (`Finding` + `AtamEvidence` records) cites specific files and line numbers in the `happyhero` monorepo.

### B1. `synchronize: true` is on by default in TypeORM (HIGH)

- **Finding:** `F9` (record `6493ec9250c4...`)
- **Evidence:** `happy-hero-mobile-app-back/src/database/database.providers.ts:22`
- **Bug:** `synchronize: process.env.SYNC_DB !== '0'` — TypeORM's official docs explicitly warn against `synchronize: true` in production. Entity-class changes auto-alter the live DB schema on every app startup, with no review gate. The `/src/migrations/` directory is configured (`migrationsRun: true`) but does not exist on disk.
- **Impact:** Directly enables **hypothesis H1** (confirmed): inferred-event semantics can silently drift when underlying tables are renamed/restructured. The 2026-05-11 `bot.questions` content-corruption incident is the documented in-the-wild manifestation.
- **Recommended fix:** Set `synchronize: false` in production; introduce a proper migrations workflow.

### B2. Reporting auth is a single shared token; analyst rows are mutable (HIGH)

- **Finding:** `F1R` (record `6fdd38e7d580...`, supersedes the earlier fabricated F1)
- **Evidence:** `happy-hero-bot/bot/src/services/auth_service.py:229-253, 388`
- **Bug:** `is_key_based_auth()` allowlists `/bot/reporting/analytics/*` and `/bot/admin/*` against a single shared header `x-authtoken-reporting` compared to `REPORTING_AUTH_TOKEN`. No per-analyst identity, no per-query log. Underlying event rows are mutable — any service holding DB credentials can rewrite history.
- **Impact:** No defensible "who saw which user's biometric/PII data when" trail. Token rotation invalidates everyone at once.
- **Recommended fix:** Per-user tokens or short-lived signed credentials; row-level immutability or separate write-once audit log for analytics-relevant tables.

### B3. Event-write idempotency is partial; documented as TODOs (HIGH)

- **Finding:** `F6` (record `6573238ffd95...`)
- **Evidence:** Three production TODO comments:
  - `happy-hero-bot/bot/src/mobile_app_server.py:637` and `:768` — *"TODO: check if already have message with given moment_id presented as the last one — do nothing if already have — so we are idempotnent now"* (sic)
  - `happy-hero-bot/bot/src/paywall/payment_events_processor.py:184` — *"here we chould check if have record with given subscription id and then retry if not, ... three retries, then execption"* (sic)
  - `bot/src/repositories/dialogues_repository.py:99,121,141,324,336,349,597,610,629,783` — INSERT statements with auto-IDs, no `ON CONFLICT`, no idempotency-key constraint
- **Bug:** Retries (whether SDK-side, app-side, or operator-driven) will duplicate moment-presentation events, payment events, and message records. Behavioural analytics will over-count silently.
- **Recommended fix:** Add an idempotency-key column where natural (moment-presentation, subscription events); use `ON CONFLICT DO NOTHING` for the de-dup paths.

### B4. Momenter→NestJS HEAD fan-out has no backpressure or retry policy (MED)

- **Finding:** `F4R` (record `48f102c47a18...`, supersedes the earlier fabricated F4)
- **Evidence:** `happy-hero-mobile-app-back/src/domain/internal-services/internal-services.controller.ts:29` — `@Head('hrv-robot/notification')`; cross-service path described in `.claude/memory_bank/architecture/monorepo-overview.md`
- **Bug:** Synchronous single-hop fan-out from Python momenter → NestJS HEAD endpoint with `?userId=&dataFrom=&dataTo=` query params. No idempotency key, no documented retry policy, no backpressure mechanism.
- **Impact:** If NestJS endpoint slows or errors, the momenter pipeline either backs up or silently drops moment-creation triggers. Moments lost without analytics noticing.
- **Recommended fix:** Make the endpoint POST with an explicit idempotency key; add a bounded retry queue on the momenter side.

### B5. 30-day onboarding cohort CTE is duplicated across 4 SQL files (MED)

- **Finding:** `F5` (record `a8f67fb70e5d...`)
- **Evidence:** `gcloud/mygcloud/bin/cohorts/cohort_engagement_export.sql`, `cohort_tree_export.sql`, `cohort_hexaco_export.sql`, `cohort_hexaco_pairs_export.sql`; pattern documented in `.claude/memory_bank/patterns/cohort-segmentation-bundle.md`
- **Bug:** The "30-day onboarding cohort" definition (users whose first daily-check item with `is_init_question=true` was created in the last 30 days) is repeated as a CTE in four separate SQL files. Changing the definition requires touching all four in lockstep; nothing enforces agreement.
- **Recommended fix:** Extract cohort-membership SQL to a single materialised view or shared `.sql` snippet that the four reports `\include`.

### B6. Retry primitive is per-module, not shared (SP, MED)

- **Finding:** `F7` (record `4a06965cb0a3...`, sensitivity point)
- **Evidence:** `bot/src/mobile_app_server.py:1419-1429` (fixed-delay 3-retry); `bot/src/paywall/payment_events_processor.py:116` (exponential backoff)
- **Bug:** Retry logic is reinvented in each module with different strategies. No shared retry primitive, no circuit breaker, no global retry budget.
- **Impact:** Tuning one retry policy without auditing all is operating one fader on a multi-fader board. The retry-storm-vs-give-up tradeoff is set independently per call site.
- **Recommended fix:** Extract a shared retry helper with explicit policy (jitter, max-attempts, deadline propagation) and migrate the two call sites onto it.

### B7. Shared OLTP DB couples analyst-read latency to user-write availability (TP)

- **Finding:** `F2` (record `a29f27ab32fd...`, tradeoff point)
- **Evidence:** `database.providers.ts:25` — `poolSize: 20`; absence of any read-replica configuration; analyst access via `bot/src/analytics/*` and `database/query.sh` runs direct on shared-db
- **Bug:** Single 20-connection pool serves user-facing writes from bot-api and mobile-app-back AND analyst reads via the analytics exporters. A heavy cohort query (e.g. the 135-cell HEXACO pairs export) competes with chat-write latency.
- **Recommended fix:** Read replica for analytics; or move the analytics exporter to read against a snapshot/log of the OLTP DB rather than the live store.

### B8. No backpressure on event-write paths; scale-protected only (LOW)

- **Finding:** `F8` (record `5694075e877e...`)
- **Evidence:** `rg` for rate-limit primitives shows none on user-facing endpoints; the only ones found are inbound from external systems (`openai.service.ts:246` handling OpenAI's `RateLimitError`, `google_play_rtdn_pull_service.py:24,36` Semaphore on Google's pubsub consumer)
- **Bug:** `bot-api` and `mobile-app-back` accept unbounded incoming load. No throttle/queue/shed policy between request acceptance and shared-db INSERT.
- **Impact:** At current 1k eps well within capacity; a 10× scale event combined with B7 (shared pool) + B3 (no idempotency) + B1 (silent schema changes) is a compounding failure mode.
- **Recommended fix:** Token-bucket or concurrency limit at the API gateway level; document explicitly when scale changes warrant it.

### B9. No API versioning convention (LOW)

- **Finding:** `F10` (record `7322aa398169...`)
- **Evidence:** No `/v1/`, no `@ApiVersion`, no negotiated content-type versioning. Three Swagger-doc-only `deprecated: true` annotations in `moments.controller.ts:209`, `daily-check.controller.ts:165, 219`.
- **Bug:** Breaking changes rely on coordinated mobile-app + backend releases. Workable at current consumer-count (1 mobile client + analytics scripts); becomes a hard problem the moment a second consumer appears.
- **Recommended fix:** Adopt a versioning convention (URL or header) before introducing a second consumer.

### B10. No analytics caching (NR — kept as documented non-risk)

- **Finding:** `F3` (record `276b50e380f2...`, non-risk)
- **Evidence:** Confirmed via grep; no Redis or in-memory analytics cache configured
- **Status:** Non-risk in the ATAM sense: no caching layer means no cache-coherence drift bugs. Documented because the absence is itself a deliberate (or accidentally-deliberate) trade — analysts always see fresh data, at the cost of latency relief.

---

## C. Confirmed hypothesis

### C1. Inferred-event semantics have hidden schema coupling — CONFIRMED

- **Hypothesis:** `H1` (record `9df8ce1792df...`)
- **Status update:** `AtamHypothesisUpdate` (record `3a21d7e1fd76...`) — status `confirmed`
- **Confirming evidence:** `.claude/memory_bank/reports/test-content-audits-summary-2026-05-12.md` documents the 2026-05-11 `bot.questions` content corruption incident. EN/UK content for HEXACO and PVQ tests was corrupted; stored `user_scale_values` rows from before the fix are computed against non-canonical items and are **not valid scores**. Mitigation is an ex-post `--score-min-date` filter baked into the cohort wrapper — a manual code convention, not an automated integrity check.
- **Connection to bugs:** B1 (`synchronize: true`) is the underlying enabler. B5 (cohort-CTE duplication) means any future similar drift requires fixing the workaround in 4 places.

---

## Audit trail

All findings, evidence, coverage updates, hypothesis updates, plans, decisions, and probe outcomes are stored as append-only hash-chained records in hashharness, workpackage `atam.case.uba-2026-05-27`. Query via:

```bash
mcp__hashharness__find_items(type="Finding", work_package_id="atam.case.uba-2026-05-27", limit=20)
mcp__hashharness__find_items(type="AtamProbeOutcome", work_package_id="atam.case.uba-2026-05-27", limit=10)
mcp__hashharness__verify_chain(...)  # to confirm the chain is intact
```

Or via the controller CLI: `$PY scripts/cli.py state --workpackage atam.case.uba-2026-05-27`.
