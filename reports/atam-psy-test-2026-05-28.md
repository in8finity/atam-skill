# ATAM Evaluation Report — psy-test endpoints

**System:** `/bot/psy-test/all` (user-facing) and `/bot/admin/reset_test` (admin) endpoints, happy-hero-bot
**Date:** 2026-05-28
**Evaluator:** AI + architect-proxy, grounded in `/Users/a.morozov/workspace/happyhero` code
**Method:** ATAM (Kazman, Klein, Clements — SEI), endpoint-scope walk
**Workpackage:** `atam.case.psy-test-all-2026-05-28` (hashharness, append-only hash-chained)
**Phases run:** P0, P2, P3, P4, P5, P6, P9 (P7 brainstorm and P8 re-analysis skipped — no second pass needed at endpoint scope)
**Sibling evaluation:** `atam.case.uba-2026-05-27` (User Behaviour Analytics subsystem) — referenced where findings echo cross-evaluation patterns.

---

## Executive summary

Two endpoints, one shared codebase, two very different qualities of engineering.

`/bot/psy-test/all` (user-facing) returns each user's test progress. The implementation has a small cluster of related defects: an unwhitelisted header (`x-language-code`) gets f-string-interpolated into a SQL identifier slot, a catch-all returns the raw exception string as the response body, and adding a fourth language touches schema columns in lockstep with no fallback. The three findings compose: untrusted input lands in a SQL slot → produces a syntax error → the error text leaks back to the client. None is catastrophic alone (under PostgreSQL identifier rules the classical injection class is essentially impossible from a column-name slot); together they enable schema enumeration via the error channel and low-cost DoS.

`/bot/admin/reset_test` (admin) is materially better written — structured error responses with stable shape, defensive type checks, per-user error isolation, batched-result summary. The interesting risk on this side is **structural, not local**: the reset semantic is "advance a timestamp; downstream consumers must filter rows by that timestamp". This contract is documented in the docstring of the reset handler — at the *actor*, not at the *data tables*. Three consumers honor it today. A fourth consumer added by a future developer touching `users_tests_answers` directly has no structural guardrail. This is the same risk class as F14R from the sibling UBA evaluation (cross-layer interface without contract test), instantiated at endpoint scope.

The challenge step (`cli.py challenge` + Walton CQ schemes) caught two overstatements: F1 (SQL injection) was originally high-severity, downgraded to medium after CQ1 (likelihood) revealed that catastrophic injection is essentially impossible from a column-name slot in PostgreSQL — the realistic class is info-leak + DoS, not RCE/exfiltration. F6 (the 3-consumer contract) was originally high-severity, downgraded to medium after CQ13 (alternatives) lands the steelman: the docstring IS a contract, all current consumers respect it, and the failure mode is *future* propagation, not *current* correctness.

Two recommendations, both effort S to S-M:
- **R1** — whitelist `x-language-code` + structured error response on the user path. Breaks the F1R/F2/F5 chain in one patch.
- **R2** — move the date-filter contract from docstring to either SQL views (lightest) or a CI lint (medium). Surfaces the contract at the data, not the actor.

---

## 1. Business drivers (P2)

| # | Driver | Notes |
|---|--------|-------|
| BD1 | Reliable test-progress display | Users see an accurate, fast, correctly-localized list of psy-tests with their personal progress when opening the testing screen. The admin reset endpoint exists in service of this driver: it lets operators force a re-test after data-correctness incidents. |

## 2. Quality-attribute priorities (P2)

| Rank | QA | Refinements |
|------|----|-------------|
| 1 | security | input sanitization, auth correctness, error-message containment |
| 2 | modifiability | adding a language, schema-column drift, endpoint-shape change cost, reset contract propagation |
| 3 | performance | query latency, request-shape efficiency, batch-operation scaling |

## 3. Architecture summary (P3, P4)

```
mobile-app (Flutter)
   ├── GET /bot/psy-test/all?user_app_id=... [x-language-code: ru|en|uk]
   │       │
   │       ├── auth_service.is_user_authorized (Firebase ID-token + email-match)
   │       │
   │       ├── tests_service.get_tests_with_status_by_user
   │       │       │
   │       │       ├── tests_repository.tests_answers_progress_by_stages_by_internal_id
   │       │       │     [raw SQL with CTE, multi-table joins, GROUP BY,
   │       │       │      COUNT(DISTINCT), f-string interpolated column names]
   │       │       │
   │       │       └── tests_repository.get_user_test_dates
   │       │             [separate query, sequential]
   │       │
   │       └── test_with_status_mapper (Python)
   │
   └── (operator)
         POST /bot/admin/reset_test  [x-authtoken-reporting]
            │  body: {user_application_ids: [...], test_internal_name: "..."}
            │
            ├── tests_repository.get_test_id_by_internal_name (parameterized SQL)
            │
            └── for each user_application_id (sequential):
                    users_repo.get_cached_user
                    tests_repository.reset_test_dates
                       [UPDATE users_tests_dates SET first_test_enter_date = NOW()]
```

**Approaches in use:**
- aiohttp handler (Python) + raw-SQL repository pattern (`tests_repository.py`)
- Firebase ID-token + cached-user email-match for end-user paths
- Shared `REPORTING_AUTH_TOKEN` (single env-var token) for admin paths — same gap surfaced in UBA F1R
- Per-language schema columns (`preview_text`, `preview_text_en`, `preview_text_uk`) selected by f-string interpolation
- Reset-by-timestamp-advance: prior-attempt rows stay on disk; downstream consumers filter them out

**Components (4):** handler, tests-repository, auth-service, shared-db-tests-schema. Plus admin-reset-test added in post-P9 revision.

## 4. Scenarios (P5, with P5-rev additions for admin)

| # | QA | Category | Title | (I, D) | Selected |
|---|----|----------|-------|--------|----------|
| S1 | security | anticipated | Malicious `x-language-code` header cannot inject SQL | (H, M) | ✓ |
| S2 | modifiability | anticipated | Adding a new supported language is bounded in touches | (M, M) | ✓ |
| S3 | performance | anticipated | GET `/bot/psy-test/all` p95 ≤ 1s under typical load | (H, M) | ✓ |
| S4 | security | anticipated | Error responses don't leak internal state | (M, L) | ✓ |
| S5 | modifiability | anticipated (rev) | A new consumer of test-derived data respects the date-filter contract | (H, H) | ✓ |
| S6 | performance | anticipated (rev) | Large-batch reset (1000+ users) completes in bounded time | (M, M) | ✓ |

## 5. Findings (consolidated)

### Risks — medium (5)

| ID | Title | Anchor |
|----|-------|--------|
| **F1R** | Unwhitelisted `x-language-code` reaches SQL identifier f-string; amplifies F2 into schema info-leak + DoS class (supersedes F1, severity high→med via CQ review) | `tests_repository.py:131-146`; `http_app.py:939` |
| F2 | Catch-all exception handler returns raw `str(e)` as response body | `http_app.py:951-953` |
| F3 | Two sequential DB queries; first has multi-table aggregation shape | `tests_service.py:53-63`; `tests_repository.py:109-220` |
| F5 | Adding a new language touches schema + inference in lockstep; no whitelist or fallback policy | same f-string evidence |
| **F6R** | Reset-immune-by-date-filter contract is documented at the actor, not the data — discoverability gap (supersedes F6, severity high→med via CQ review) | `admin_controller.py:324-333` |
| F9 | Admin batch reset is a sequential loop, no size limit, O(N) DB roundtrips | `admin_controller.py:392-413`; `tests_repository.py:273-284` |

### Risks — low (2)

| ID | Title | Anchor |
|----|-------|--------|
| F4 | `test_id` filter applied in Python after fetching all tests (waste at current N, structural smell) | `http_app.py:943-948` |
| F8 | Per-user `entry["error"] = str(exc)` in admin response — same anti-pattern as F2, scoped to operator-facing channel | `admin_controller.py:414-422` |

### Non-risks (1)

| ID | Title | Anchor |
|----|-------|--------|
| F7 | Admin endpoint error handling is well-structured (positive comparator to F2): stable `{error: <code>, ...}` shape, all top-level paths covered | `admin_controller.py:346-380` |

### Superseded (in chain for provenance)

- F1 → F1R (high → med, after CQ review)
- F6 → F6R (high → med, after CQ review)

---

## 6. Risk themes (P9)

### T1 — untrusted-input → SQL identifier slot → error channel leak (compound, MED)

**Member findings:** F1R + F2 + F5 (with F8 a sibling in the admin scope).

Three findings compose into one risk shape: an authenticated user sends an arbitrary `x-language-code` header → server f-string-interpolates it into a SQL column-name position → PostgreSQL parses the result, usually returning a "column does not exist" or "syntax error at or near" error → the catch-all handler at `http_app.py:951-953` returns the raw error text in the response body. The attacker now has a schema-enumeration channel. Repeating the request many times is also a low-cost DoS because each invalid query still incurs the multi-table aggregation cost of F3 before failing.

None of the three findings is catastrophic alone. Together they form the chain; closing **any one** breaks it. F5 (whitelist `x-language-code`) is the cheapest because it's a four-line change at the handler edge and also solves a modifiability concern.

**Threatens:** BD1 indirectly (the failure mode is information disclosure rather than a broken user experience).

### T2 — contracts live at the actor, not at the data — discoverability gap (MED)

**Member findings:** F6R.

The reset mechanic depends on a contract — "every query against test-derived data must filter by `users_tests_dates.first_test_enter_date`" — that is documented only in the docstring of `admin_controller.reset_test`. Three current consumers honor it: the listing query, the doppelganger persona, the cached summary. A fourth consumer added by a future developer touching `users_tests_answers` directly will not naturally encounter the docstring; the contract is invisible from their entry point.

This is the same risk class as **F14R** from the sibling UBA evaluation (`atam.case.uba-2026-05-27`) at a different abstraction level. In UBA the cross-layer interface was "Python compute → NestJS storage → SQL band thresholds" for scoring semantics. Here it's "reset writer → N readers" for state filtering. Same shape, same remedy class (move the contract from docstring to a structural mechanism).

**Threatens:** BD1 directly (a future-consumer leak shows the user a stale test result after an admin-initiated reset, which is exactly the operational use case this endpoint exists for).

---

## 7. Recommendations (P9)

### R1 — whitelist `x-language-code` + structure the user-endpoint error response (effort S, addresses T1)

Two small changes, total ~2 dev-days:

1. **Whitelist** `x-language-code` at the handler edge: if header value is not in `{ru, en, uk}`, either reject with 400 or coerce to `ru`. Implement as a small helper in `auth_service.py` or an aiohttp middleware so it can be applied to other endpoints that consume the header (the bot has more — e.g. `/bot/psy-test/summary`).
2. **Structure the error response** in `http_app.py:951-953`: replace `return web.Response(status=400, text=f"{str(e)}")` with the same shape the admin handler uses (`orjson.dumps({"error": "<kind>"})` + appropriate status). Map known exception classes to known error codes; default to 500 + `{"error": "internal"}` for the rest. Log the full exception via `logging.exception` (already happens) but keep it server-side.

Together these break the F1R → F2 → schema-info-leak chain. Side benefits: F4 (test_id post-filter) and F3 (two-query shape) are surfaced as cleanup items but not blocking; F5 (language addition cost) becomes safer because the whitelist forces explicit language registration. F8 (the admin sibling of F2) can be closed by the same exception-class mapping helper.

**Deliverables:** language-whitelist middleware or helper; structured error-response in `get_tests_with_statuses_and_progress`; unit test for unknown-language rejection; unit test that 500 responses don't include exception text.

### R2 — move the date-filter contract from docstring to either views or CI lint (effort S-M, addresses T2)

Three options, ordered by cost-to-value:

1. **Lightest: SQL views.** Create `vw_active_users_tests_answers` (and equivalents for `user_scale_values`, any other reset-affected table) that bake in the join + filter against `users_tests_dates`. Document the convention: analytics and downstream consumers SELECT from the view, not the raw table. Old queries continue to work but are flagged as "reset-unsafe" in code review.
2. **Medium: CI lint.** Add a rule (sqlfluff/semgrep/custom script) that fails PRs touching the listed tables in a query without either (i) a join on `users_tests_dates` with the expected predicate or (ii) an explicit `-- reset-immune` comment opting out.
3. **Heaviest: PostgreSQL trigger or RLS policy.** Prevent reading rows whose `created_at < first_test_enter_date` at the DB layer. Heavy and surprising for analyst workflows — not recommended.

Start with (1) — small migration, no consumer code changes if SELECTs are updated in the same patch. Add (2) as a guardrail.

**Deliverables:** `vw_active_users_tests_answers` view + sibling views for any reset-affected table; consumers migrated; CI lint rule with at least one positive and one negative test case.

---

## 8. Known gaps in this evaluation

- **Solo run.** No real stakeholders or operators consulted. The convention enumerated at `admin_controller.py:324-333` was taken at face value — verifying that *all three* listed consumers actually apply the filter would harden T2's evidence.
- **Bank-driven loop was a poor fit at endpoint scope.** The selector picked `sec.audit-trail` (designed for subsystem-level probing). The findings here came from direct code-walk, not bank-probe-driven adaptive selection. **Implication for the skill:** the bank lacks endpoint-scope probes (e.g. `endpoint.input-validation`, `endpoint.error-shape`, `endpoint.query-shape`, `endpoint.auth-boundary`). Adding them would let the adaptive controller work at this scope.
- **No measurements.** F3 (slow aggregation) and F9 (batch O(N)) are described qualitatively. A 10-minute query-plan run on staging would calibrate the severity.
- **`get_test_id_by_internal_name` and `reset_test_dates` checked, but no full audit of every SQL function touched.** Both are correctly parameterized (no f-string injection on the admin path); the f-string class is confined to the user-facing listing query.
- **The challenge step uses the embedded scheme catalog,** not a live `aif-arguments` invocation. Schemes detected, CQs answered, findings revised — the structural argument-graph nodes (I/RA/CA/PA) are not stored separately. The CQ exchanges are captured as `AtamEvidence` records of `kind=quote` referencing the chain.

---

## 9. Cross-evaluation linkage

This run is the second in the `happyhero` corpus, following the User Behaviour Analytics subsystem evaluation (`atam.case.uba-2026-05-27`). Findings that echo across the two:

| Endpoint-scope finding | UBA-scope sibling | Pattern |
|---|---|---|
| F1R (untrusted header in SQL identifier slot) | F9 (TypeORM `synchronize: true`) | "Schema changes propagate without a gate" — at the request level here, at the migration level there |
| F2 (raw `str(e)` to client) | F1R-UBA (single reporting token, no audit) | "No shared response-shape primitive across handlers"; "no per-actor identity" |
| F5 (no language whitelist, lockstep schema columns) | F14R-UBA (3-place score semantics) | Cross-layer interface without contract test |
| F6R (3-consumer date-filter contract at the actor) | F14R-UBA, F18R-UBA | Contracts that live at the actor instead of at the data — *discoverability gap* sub-pattern |
| F9 (batch reset O(N)) | F11-UBA (no circuit breaker, tiny pool) | The bot's max_size=4 pool turns linear loops into resource-hold patterns |
| F3 (analyst-query latency on shared DB) | F2-UBA (shared OLTP TP) | Same root: no read-replica or query-shape boundary between operational and analytical workloads |

The cross-evaluation pattern is striking: at every abstraction level (subsystem, endpoint, single line of SQL), the same handful of architectural ideas surface. Closing R1 of UBA (disable `synchronize`, R1.1) is the architectural prerequisite for several endpoint-scope mitigations.

---

## 10. Appendix — audit trail

All findings, evidence, themes, recommendations, scenarios, and phase gates are stored as append-only hash-chained records in hashharness, workpackage `atam.case.psy-test-all-2026-05-28`. Phase gates form a chain from P0 (opened) to P9 (closed).

Useful queries:

```bash
mcp__hashharness__find_items(type="Finding", work_package_id="atam.case.psy-test-all-2026-05-28", limit=20)
mcp__hashharness__find_items(type="RiskTheme",  work_package_id="atam.case.psy-test-all-2026-05-28")
mcp__hashharness__find_items(type="Recommendation", work_package_id="atam.case.psy-test-all-2026-05-28")
```

Or via the controller CLI:

```bash
$PY scripts/cli.py state --workpackage atam.case.psy-test-all-2026-05-28 --phase 6
```

Run summary: **7 PhaseGates (P0, P2, P3, P4, P5, P6, P9), 10 Findings (8 R + 1 NR + 2 superseded chains), 2 RiskThemes, 2 Recommendations, 6 Scenarios + 6 ScenarioRatings, 4 ProbingQuestions, 9 AtamEvidence records, 6 AtamCoverage updates, 5 AtamPlan + AtamAdaptiveDecision pairs.**

The skill ran from setup to closed evaluation in approximately 15 minutes of evaluator time (real wall-clock; the model used the CLI verbs `open-evaluation`, `close-phase`, `next-probe`, `record-question`, `record-evidence`, `record-finding`, `update-coverage`, and `challenge`). The CQ challenge step ran twice and revised both invocations' target findings from `high` to `med` — both downgrades were calibrations of framing, not retreats from the underlying diagnosis.
