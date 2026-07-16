# Integrating the new hashharness primitives into `atam-evaluation` — 2026-05-30

Implementation recommendations after hashharness shipped backend scalability +
whole-work-package verification (`40e4fbc` indexed `record_sha256`,
`7e3649e` `where_attributes`, `57bf1e7` `find_tips_where`, `26a4bff` bounded
WAL, `30fd482` `list_work_packages` / `verify_work_package`).

All `scripts/` and `references/` file:line references are this repo at HEAD.
Severity: 🔴 correctness · 🔵 code change · 🟠 friction · 🟣 new capability ·
🟢 free-on-upgrade.

---

## 1. 🔴 Replace `find_items(type=T, work_package_id=W, limit=N)` with `get_work_package(W, type=T)` everywhere

This is both a **silent-truncation correctness fix** and a per-call speedup.

`controller.py` and `cli.py` reach for `find_items` with hard `limit` caps to
scope to one evaluation: `Scenario` 500, `ScenarioRating` 1000, `AtamCoverage`
1000, `AtamHypothesis` 200, `AtamHypothesisUpdate` 1000, `ProbingQuestion` 500
(`controller.py:143, 144-146, 174, 202, 203-205, 231`). On a long-running Mode-B
evaluation, any of these can quietly cross the cap, the call returns the first
N records and the *reconstructed state silently drops the rest*. The bug is
invisible — until your "latest rating per scenario" suddenly skips a scenario.

`get_work_package(work_package_id, type=...)` returns **every** matching record
in that wp in one call, unbounded — that's its job. Concrete substitutions:

| Today (`controller.py`) | Replace with |
|---|---|
| `find_items(type="Scenario", work_package_id=wp, limit=500)` | `get_work_package(wp, type="Scenario")` |
| `find_items(type="ScenarioRating", work_package_id=wp, limit=1000)` | `get_work_package(wp, type="ScenarioRating")` |
| `find_items(type="AtamCoverage", work_package_id=wp, limit=1000)` | `get_work_package(wp, type="AtamCoverage")` |
| `find_items(type="AtamHypothesis", work_package_id=wp, limit=200)` | `get_work_package(wp, type="AtamHypothesis")` |
| `find_items(type="AtamHypothesisUpdate", work_package_id=wp, limit=1000)` | `get_work_package(wp, type="AtamHypothesisUpdate")` |
| `find_items(type="ProbingQuestion", work_package_id=wp, limit=500)` | `get_work_package(wp, type="ProbingQuestion")` |
| `find_items(type="AtamBankProbe", work_package_id=refdata_wp)` (`controller.py:110`) | `get_work_package(refdata_wp, type="AtamBankProbe")` |
| `find_items(type="AtamPlan", work_package_id=wp, limit=500)` (`cli.py:111`) | `get_work_package(wp, type="AtamPlan")` |
| `find_items(type="AtamInstrumentVersion", work_package_id=refdata_wp)` (`cli.py:88`) | `get_work_package(refdata_wp, type="AtamInstrumentVersion")` |

Same change in `scripts/hashharness_adapter.py:59-65`, where the current code
fetches 4× the requested limit (or `limit=10000`) and filters by wp
*client-side*. The intent — "all of type T in wp W" — is exactly
`get_work_package`'s contract.

The `RealMcpAdapter.find_items` (`scripts/mcp_adapter.py:92-107`) should still
exist for text/title queries but should route `(type, wp)` calls to
`get_work_package` internally so callers don't have to think about the
distinction.

---

## 2. 🔴 The "verify_chain on the evaluation's work_package_id" recipe is misleading — use `verify_work_package`

`references/hashharness-mapping.md:241` reads:

> **Verify the chain is intact:** `verify_chain` on the evaluation's `work_package_id`.

`verify_chain` takes a **`text_sha256` root** and walks the reachable set. An
ATAM evaluation has many records, no single root reaches them all (`PhaseGate`
is a chain but doesn't link to every Finding/Evidence/Scenario), and the whole
point of an evaluation audit is to catch a tampered or orphan record that
*isn't* on the PhaseGate spine. That's the R-2 / R-4 gap the ATAM run against
hashharness identified — and it applies to the auditing of ATAM evaluations
themselves.

`verify_work_package(eval_wp)` is the correct primitive: it verifies **every**
record in the work-package (not just root-reachable ones) and `_verify_item`
already re-checks each record's bound schema against the canonical schema
chain — so AUD-1 (loosen → write → tighten trace) actually surfaces.

**Change** — update `hashharness-mapping.md` "Verify" / "Example queries" to:

```
# Audit the whole evaluation (every node, regardless of reachability)
mcp__hashharness__verify_work_package(
    work_package_id="atam-2026-05-26-checkout",
    summary=true,
)
# → {work_package_id, ok, checked_items, errors_count}
```

And add a `scripts/cli.py audit` verb (or a standalone `atam-audit.py`) that
calls `verify_work_package(eval_wp)`, surfaces failing records, and combines
the result with the structural §11 challenge check (every high/med Finding
must have a linked `AtamEvidence` challenge marker). One command = "is this
evaluation cryptographically and structurally trustworthy."

---

## 3. 🟣 `list_work_packages(prefix="atam-")` finally gives the portfolio enumeration the mapping doc envisions

The hashharness-mapping doc explicitly notes "one hashharness instance can
hold many ATAM evaluations" but there is no command today to **list them**. The
skill has no portfolio view. `list_work_packages` closes that:

```python
mcp_client.tool("list_work_packages", {"prefix": "atam-"})
# → {"work_package_ids": ["atam-2026-05-26-checkout", "atam-2026-05-29-hashharness", …]}
```

**Recommendation**: add `scripts/cli.py list-evaluations` (one-liner) and an
`audit-all` verb that composes `list_work_packages(prefix="atam-")` →
`verify_work_package(work_package_ids=[…])` (batch form, one round trip) → a
portfolio-wide integrity attestation.

The same wp-prefix convention enables a refdata sweep:
`list_work_packages(prefix="atam.refdata.")` → which probe-bank versions are
installed.

---

## 4. 🟣 `find_tips_where` over `PhaseGate` enables a real portfolio status board

`PhaseGate` IS `chain_predecessor: true` (mapping line 109-114), so its current
tip is indexed in the new projection. Attributes are
`phase: 0..9, decision: approved|revised|skipped`. So:

```python
# Which evaluations are sitting on an approved P8 gate (ready for P9 themes)?
mcp_client.tool("find_tips_where", {
    "type": "PhaseGate",
    "where_attributes": {"phase": "8", "decision": "approved"},
})
# → {"tips": {"atam-2026-…": {…}, "atam-2026-…": {…}}}
```

This is the natural primitive for an `atam-portfolio` dashboard: which
evaluations are blocked, which approved through which phase, who needs P5
prioritization next. Today the same answer requires fetching every PhaseGate
record across every evaluation and grouping client-side; with the projection
it's one indexed call. Suggested verb: `scripts/cli.py portfolio-status`.

---

## 5. 🔵 Mode B per-tick: load the whole evaluation wp once, partition in memory

`controller.py:reconstruct_*` calls `find_items` 6+ times per tick (one per
type — see §1). Even after switching each to `get_work_package`, that's still
6+ MCP round trips per controller iteration; each pays connect/dispatch cost.

`get_work_package(wp)` **without** a type returns every record in the
evaluation. For an in-memory partitioning step:

```python
all_items = mcp_client.tool("get_work_package", {"work_package_id": wp})["items"]
by_type: dict[str, list] = {}
for it in all_items:
    by_type.setdefault(it["type"], []).append(it)
# Then in-memory: by_type["Scenario"], by_type["ScenarioRating"], …
```

This cuts the per-tick MCP cost from O(types) to 1 round trip, at the cost of
fetching all records every tick. For Mode-B's data volumes (hundreds to low
thousands of records per evaluation) that's strictly cheaper than the per-type
loop. It also makes the "skill calls are ~30+ per finding" friction noted in
the HRV feedback (A5) less painful — one shared load per tick instead of
re-fetching per command.

If the data grows large enough that this becomes costly, cache the result
between ticks and only re-fetch after writes from the same tick (the
created records are already known from `create_item` returns).

---

## 6. 🟠 `find_tips_where` does NOT help with per-scenario / per-hypothesis state — and that's correct

`ScenarioRating.replaces`, `AtamCoverage.previous`, and
`AtamHypothesisUpdate.prevUpdate` are *per-scenario* / *per-hypothesis*
timelines, not per-`(wp, type)` chains. They are correctly NOT
`chain_predecessor: true` — the same design choice STIPO-R made and documented
("the flag is a per-(workpackage, type) constraint that conflates semantically
distinct revision/event timelines").

So `find_tips_where("ScenarioRating", …)` would not index "latest rating per
scenario" — it indexes "the single head of the ScenarioRating chain in this
wp," which has no meaningful per-scenario semantics. The current pattern in
`controller.py:148-154, 175-181, 206-216` — fetch all, sort by `created_at`,
group by scenario / hypothesis — is the right shape. Keep it. **One-line note
worth adding to `hashharness-mapping.md`**: "These per-scenario chains are
intentionally not `chain_predecessor`; group client-side, do not reach for
`find_tips_where`."

---

## 7. 🟠 Schema merge discipline — still caller-owned, R-5 from the ATAM addendum is unfixed upstream

The ATAM addendum (`atam-evaluation/10-evidence-addendum.md` from the
hashharness ATAM run) flagged R-5: `set_schema` has no server-side guard that
a new payload is a type-superset of the previous head. The ATAM skill bootstrap
in `hashharness-mapping.md:255-265` already warns about merge-not-replace —
keep that helper strict, and consider adding a pre-push assertion:

```python
current = mcp__hashharness__get_schema()
merged  = {"types": {**current.get("types", {}), **atam_types}}
assert set(current.get("types", {})).issubset(merged["types"]), \
    "merge dropped types; refusing to push"
mcp__hashharness__set_schema(schema=merged, expected_prev=current_head_sha)
```

The CAS itself is sound (the schema-chain CAS-race fix `40e4fbc`-era is in
place); the danger is only a careless **retry** that drops types because the
caller didn't re-merge on the new head. Add the superset assertion *inside the
retry loop* so a stale rebuild can't silently regress the schema.

---

## 8. 🟢 Free wins on upgrade — pin the new hashharness ref

- The `record_sha256` index speeds up link target resolution used everywhere
  `verify_chain` / `query_chain` walk (and now `verify_work_package`). You get
  this for free on upgrade.
- WAL is now bounded automatically by a periodic TRUNCATE checkpoint
  (`HASHHARNESS_WAL_CHECKPOINT_WRITES`, default 1000). Default is fine for ATAM
  load; lower only if you run a portfolio server with continuous writes.
- First open of an existing ATAM store runs the one-time migration
  (record_sha256 backfill + tip_attributes projection rebuild). Idempotent,
  safe — but **run it once offline** before a Mode-B session, not under it.
- Bump whatever ref `atam-evaluation` pins to ≥ `30fd482` to pick up
  `verify_work_package` / `list_work_packages` (needed by §2 / §3 / §4).

---

## 9. ⚠️ Still open upstream: backpressure (R-13)

Connection-reset-under-fan-out is not yet fixed in hashharness. Mode B's
controller loop is single-threaded so it's less acute than for `pm`, but if a
guided ATAM run spawns parallel sub-agents (e.g., during §11 CQ challenges
handed off to `aif-arguments`), expect `ConnectionResetError` at concurrent
worker counts. Treat it as retryable, not fatal.

---

## Suggested order

1. **§8** — pin the new ref + run migration offline. Free.
2. **§1** — replace every `find_items(type, wp, limit)` with `get_work_package(wp, type)`. Correctness fix (silent truncation), strictly faster, no schema change.
3. **§5** — Mode B controller per-tick load-once via `get_work_package(wp)` (no type). Removes the per-tick MCP fan-out.
4. **§2** — replace the broken "verify_chain on the wp" recipe with `verify_work_package`; add the `audit` verb. Closes the audit story honestly.
5. **§3 / §4** — portfolio enumeration + PhaseGate `find_tips_where` board. Genuinely new capability the mapping doc has been gesturing at.
6. **§6 / §7** — one-line clarifications in `hashharness-mapping.md` so future maintainers don't reach for the wrong primitive or skip the merge guard.
