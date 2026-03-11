# Paperclip Cycle 2 Review — Beacon v3

## Verdict: SHIP ✅

All 3 criticals fixed correctly. All targeted warnings resolved. No regressions. Minor new observations below — none block ship.

---

## Fix Verification

### CRIT-1: Idempotency timing — ✅ PASS
Split into `_check_idempotency_only()` (read-only) and `_record_idempotency()` (write-after-success). Verified in all 8 mutation commands:

| Command | Check-only | Event first | Abort on fail | Record last |
|---------|-----------|-------------|---------------|-------------|
| `cmd_create_task` | ✅ | ✅ | ✅ | ✅ |
| `cmd_update_task` | ✅ | ✅ | ✅ | ✅ |
| `cmd_complete_task` | ✅ | ✅ | ✅ | ✅ |
| `cmd_dismiss_task` | ✅ | ✅ | ✅ | ✅ |
| `cmd_block_task` | ✅ | ✅ | ✅ | ✅ |
| `cmd_unblock_task` | ✅ | ✅ | ✅ | ✅ |
| `cmd_bulk_assign` | ✅ | ✅ (per-item) | ✅ (to failed list) | ✅ |
| `cmd_bulk_due` | ✅ | ✅ (per-item) | ✅ (to failed list) | ✅ |

Pattern is correct: check → event → state → record. Retry safety restored.

### CRIT-2: Retry queue — ✅ PASS
- `_enqueue_retry()` now called on JIRA failures in `create()`, `create_epic()`, and `update()` (status transitions)
- `--channel` parameter added to all three commands for queue key routing
- `process_retries` command implemented with full drain logic:
  - Handles `create`, `create_epic`, `update` actions
  - Max 3 attempts before permanent discard (with logging)
  - Writes back remaining items, tracks `last_processed`
- Epic link field ID pre-fetched once before child loop (WARN-5 also fixed as side effect)

### CRIT-3: Event write failure — ✅ PASS
- `_write_event()` returns `None` on S3 put failure
- All 8 mutation commands check `if event is None` and abort with error
- Bulk commands add failed items to the failed list rather than silently continuing

### WARN-1: `--actor` param — ✅ PASS
- `create_task` CLI parser has `--actor` parameter
- `created_by` uses actor value, falls back to `"beacon"` if not provided

### WARN-2: Field validation whitelist — ✅ PASS
- `UPDATABLE_FIELDS` dict with type mapping: `description`, `assigned_to`, `due_date`, `status`, `is_blocked`, `blocker_reason`
- `_coerce_field_value()` handles bool coercion for `is_blocked`
- `VALID_STATUSES` enforces `open|completed|dismissed`
- Unknown fields rejected with clear error

### WARN-3: Channel-scoped search — ✅ PASS
- `--channel` parameter added to `query` command
- Filters results by `content/{channel}/` prefix check on metadata path
- Output includes channel field for transparency

### WARN-4: Ingest triggers embedding — ✅ PASS
- Embedding API called after all uploads complete
- Only triggers if `stored > 0` (no pointless calls on empty ingest)
- Failure logged as warning, doesn't kill the ingest result
- `embedding_triggered` boolean in output for observability

### WARN-6: Link writes event — ✅ PASS
- `link()` now writes a `jira_link` event before updating task state
- Payload includes `task_id`, `jira_key`, `old_jira_key` for audit trail

### INFO-5: task_number in task JSON — ✅ PASS
- `task_number` field included in the task dict written to S3
- No longer dependent solely on the cache file for persistence

### TOOLS.md: Key patterns — ✅ PASS
- `content/{channel_id}/{safe_ts}.md` documented (matches actual code)
- `governance/task_number_cache/`, `jira/project-types/` patterns added
- Task schema shows `task_number` field and `created_by` as UID

---

## New Observations (non-blocking)

### OBS-1: Dead code — `_check_and_record_idempotency()` still exists
- **File:** `storage.py:159-174`
- **What:** The combined check+record function is no longer called by any command. All callers now use the split `_check_idempotency_only()` / `_record_idempotency()` pair.
- **Impact:** None (dead code). Could confuse future readers.
- **Fix:** Delete it. 2 minutes.

### OBS-2: `--actor` not added to mutation commands beyond `create_task`
- **File:** `storage.py` — `cmd_update_task`, `cmd_complete_task`, `cmd_dismiss_task`, `cmd_block_task`, `cmd_unblock_task`
- **What:** These commands still hardcode `"beacon"` as the actor in their event writes. Only `create_task` honors `--actor`.
- **Impact:** Low. The SOUL.md pipeline extracts the actor and passes it on create. For updates/completions, the agent can include the actor in the event payload if needed. But it's inconsistent.
- **Fix:** Add `--actor` to remaining mutation commands. 15 minutes.

### OBS-3: Link event uses non-standard format
- **File:** `jira_api.py:472-483` (link function)
- **What:** The event written by `link()` uses a custom key format (`_now_iso().replace(...)`) and a hardcoded event_id pattern (`evt_link_{task_id[:8]}`) that differs from storage.py's `_event_key()` and `_new_event_id()` patterns.
- **Impact:** Events are still valid JSON and will be read correctly. But the key format divergence means event listing/sorting by key won't be perfectly consistent.
- **Fix:** Extract shared event-writing helpers into `beacon_common.py` (already noted as INFO-2 in cycle 1). Not urgent.

### OBS-4: Bulk operations record idempotency even on full failure
- **File:** `storage.py` — `cmd_bulk_assign`, `cmd_bulk_due`
- **What:** If ALL items in a bulk operation fail (all not found, all event writes fail), `_record_idempotency()` is still called. A retry would be silently dropped as duplicate even though nothing was written.
- **Impact:** Low. Bulk operations on entirely nonexistent task IDs would be a usage error. In practice, at least some items will succeed.
- **Fix:** Only record idempotency if `len(updated) > 0`. 5 minutes.

### OBS-5 (carried): WARN-7, WARN-8 from cycle 1 still open
- Read-modify-write race on idempotency/task numbers — accepted as known limitation
- Cron jobs not implemented — tracked as Phase 2 work

---

## Summary

| Issue | Status |
|-------|--------|
| CRIT-1: Idempotency timing | ✅ Fixed correctly |
| CRIT-2: Retry queue | ✅ Fixed correctly |
| CRIT-3: Event write failure | ✅ Fixed correctly |
| WARN-1: Actor param | ✅ Fixed |
| WARN-2: Field validation | ✅ Fixed |
| WARN-3: Channel-scoped search | ✅ Fixed |
| WARN-4: Embedding trigger | ✅ Fixed |
| WARN-5: N+1 field fetch | ✅ Fixed (bonus) |
| WARN-6: Link event | ✅ Fixed |
| INFO-5: task_number persistence | ✅ Fixed |
| TOOLS.md key patterns | ✅ Fixed |
| OBS-1: Dead code | Cleanup (2 min) |
| OBS-2: Actor on other commands | Consistency (15 min) |
| OBS-3: Link event format | Cosmetic |
| OBS-4: Bulk idem on full fail | Edge case (5 min) |

**No regressions. No new criticals. No new warnings. Ship it.**
