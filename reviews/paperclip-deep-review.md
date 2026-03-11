# Paperclip Deep Review — Beacon v3

## Verdict: SHIP (with caveats)

Beacon v3 is a clean, well-structured rebuild. The monolith-to-skills decomposition is sound. The storage patterns are solid, the event-sourced architecture is correctly conceived, and the JIRA integration handles real-world complexity (dynamic transitions, three-tier user resolution, epic link detection). The SOUL.md will guide an LLM correctly.

Ship it — but fix the criticals first, and address the warnings before trusting it in production with real project data.

---

## Critical Issues (blocks ship)

### CRIT-1: Idempotency recorded before task write — retry permanently blocked on failure
- **File:** `storage.py:167-170` (cmd_create_task)
- **What:** `_check_and_record_idempotency()` records the slack_event_id into the rolling window BEFORE the event write and task write happen. If either subsequent write fails (network blip, S3 error), the event ID is already recorded as "processed." Any retry from Slack will be silently dropped as "duplicate." The task is lost forever.
- **Affects:** All mutation commands: `create_task`, `update_task`, `complete_task`, `dismiss_task`, `block_task`, `unblock_task`, `bulk_assign`, `bulk_due` — every one records idempotency first.
- **Fix:** Split into two operations. Check idempotency at the top (read-only). Record it AFTER all writes succeed. Use `_check_idempotency_only()` (which already exists!) for the check, then call a new `_record_idempotency()` at the end.

```python
# Before (broken):
if _check_and_record_idempotency(s3, channel, event_id):
    return  # duplicate
_write_event(...)
_put_json(...)  # if this fails, event_id is already "processed"

# After (correct):
if _check_idempotency_only(s3, channel, event_id):
    return  # duplicate
_write_event(...)
if not _put_json(...):
    return  # don't record idempotency
_record_idempotency(s3, channel, event_id)  # only after success
```

### CRIT-2: Retry queue exists but is never called
- **File:** `jira_api.py:220-232` (_enqueue_retry)
- **What:** The `_enqueue_retry()` function is implemented and the retry queue key pattern is defined, but NO command ever calls it. When `create()` or `update()` fails, the error is emitted and that's it. The design doc explicitly states: "On failure: queue for retry, tell user JIRA temporarily unavailable." Additionally, there's no command to process/drain the retry queue.
- **Impact:** JIRA failures are permanent. If JIRA is down for 5 minutes during a task creation, that JIRA ticket is just... never created. No one knows.
- **Fix:** (a) Call `_enqueue_retry()` on JIRA API failures in `create()`, `create_epic()`, and `update()`. This requires adding `--channel` parameter to those commands for the queue key. (b) Add a `process_retries` command that drains the queue. (c) Wire it into the daily cron.

### CRIT-3: Event write failure is silently swallowed
- **File:** `storage.py:130-138` (_write_event) and all cmd_* functions
- **What:** `_write_event()` logs the failure but returns the event dict regardless. The calling code doesn't check if the event was actually persisted. In `cmd_create_task`, the task is written even if the event write failed. This violates the core design principle: "Events are the source of truth" and "every mutation writes an event BEFORE changing state."
- **Impact:** If event writes fail but task writes succeed, you have state that can't be reconstructed from events. The audit trail has gaps.
- **Fix:** `_write_event()` should return `None` on failure. Callers should abort if the event wasn't written:

```python
event = _write_event(s3, channel, intent, actor, slack_event_id, payload)
if event is None:
    _emit_error("Failed to write event — operation aborted")
    return
```

---

## Warnings (should fix before production)

### WARN-1: `created_by` hardcoded to "beacon" instead of actual actor
- **File:** `storage.py:176`
- **What:** Every task has `"created_by": "beacon"` regardless of who actually requested it. The task schema in TOOLS.md and DESIGN.md says this should be the Slack UID of the creator (`"created_by": "U1234ABCDE"`).
- **Fix:** Add `--actor` parameter to `create_task` CLI and pass the Slack user ID.

### WARN-2: `update_task` allows arbitrary field names with no validation
- **File:** `storage.py:210-212`
- **What:** `task[args.field] = args.value` with no validation. You could set `task["status"] = "banana"` or `task["nonexistent_field"] = "whatever"`. No type coercion either — `args.value` is always a string, so setting `is_blocked` via update_task would store the string `"true"` not boolean `True`.
- **Fix:** Whitelist allowed fields and validate/coerce values:

```python
UPDATABLE_FIELDS = {"description": str, "assigned_to": str, "due_date": str, "status": str}
if args.field not in UPDATABLE_FIELDS:
    _emit_error(f"Cannot update field '{args.field}'. Allowed: {list(UPDATABLE_FIELDS)}")
    return
```

### WARN-3: Search results not filtered by channel
- **File:** `search.py:102-117` (cmd_query)
- **What:** Similarity search queries the entire `beacon-prod` bucket. Results from ALL channels are returned. If someone in #project-alpha searches for "DNS migration," they'll get results from #project-beta too. The search SKILL.md explicitly notes: "Filter results by checking if the path starts with `content/{channel_id}/`" — but this filtering is not implemented.
- **Fix:** Either add `--channel` parameter to `cmd_query` and filter results client-side by checking metadata paths, or add a filter/prefix constraint to the API call if supported.

### WARN-4: `cmd_ingest` doesn't trigger embedding after upload
- **File:** `search.py:134-180` (cmd_ingest)
- **What:** Messages are uploaded to S3 but `cmd_trigger_embedding` is never called. The search SKILL.md says: "After all uploads, trigger bucket-wide embedding." Without this, ingested messages won't be searchable until someone manually triggers embedding or the daily cron runs (which also isn't implemented yet).
- **Fix:** Call `cmd_trigger_embedding` at the end of `cmd_ingest`, or at least emit a warning that embedding needs to be triggered.

### WARN-5: `create_epic` fetches field list inside child loop for epic_link mechanism
- **File:** `jira_api.py:372-380`
- **What:** When `mechanism == "epic_link"`, the code calls `GET /rest/api/3/field` for EVERY child ticket to find the Epic Link field ID. This is N+1 queries for N children, all returning the same data.
- **Fix:** Fetch the field ID once before the loop, store in a variable.

### WARN-6: `link` command doesn't write an event
- **File:** `jira_api.py:440-460` (link function)
- **What:** The `link` command updates `task["jira_key"]` directly in S3 without writing an event. Per the event-sourced design, every mutation should write an event first. This means task-JIRA linkages aren't in the audit trail.
- **Fix:** Write a `link_jira` event before updating the task state.

### WARN-7: Read-modify-write race on idempotency and task numbers
- **File:** `storage.py:141-156` (_check_and_record_idempotency), `storage.py:163-174` (_increment_task_number)
- **What:** Both functions do read-modify-write on S3 without locking. If two requests for the same channel process concurrently, one write could overwrite the other.
- **Practical impact:** LOW if OpenClaw processes one message per channel at a time (which it likely does). But if two messages arrive near-simultaneously for the same channel, task numbers could collide or idempotency IDs could be lost.
- **Fix:** Accept as known limitation and document, OR use S3 conditional writes (If-Match/ETag) if Telnyx Storage supports them.

### WARN-8: No cron jobs implemented
- **File:** DESIGN.md specifies 4 cron jobs; none exist
- **What:** The design calls for: daily report check (8am MT), stale task alerts (9am MT), registry refresh (midnight), embedding trigger (2am). None of these are implemented.
- **Impact:** Weekly reports, stale alerts, and search index freshness all depend on these.
- **Fix:** Implement as OpenClaw cron entries. This is Phase 2/3 work per the design doc, so acceptable for initial ship — but should be tracked.

---

## Info (nice to have)

### INFO-1: API key re-read on every S3 client creation
- **Files:** All scripts
- **What:** `_read_api_key()` reads `~/.secrets/telnyx` from disk on every `_get_s3_client()` call. For a CLI that runs once and exits, this is fine. If the scripts ever become long-running, cache the key.

### INFO-2: Duplicate S3 helper code across all four scripts
- **Files:** storage.py, risk.py, jira_api.py, search.py
- **What:** `_read_api_key()`, `_get_s3_client()`, `_emit()`, `_emit_error()`, `_get_json()`, `_list_keys()` are copy-pasted across all scripts. Any bug fix needs to be applied four times.
- **Fix:** Extract into a shared `beacon_common.py` module. Not urgent but reduces maintenance burden.

### INFO-3: risk.py duplicates task loading and filtering
- **File:** `risk.py:196-230` (cmd_calculate)
- **What:** `calculate_risk()` filters to active_tasks/open_tasks, then `cmd_calculate()` re-filters for the task_summary. The same data is processed twice with slightly different code paths.
- **Fix:** Have `calculate_risk()` return the summary counts alongside the score.

### INFO-4: `_now_iso()` imported inline in jira_api.py and search.py
- **Files:** `jira_api.py:78`, `search.py:68`
- **What:** `from datetime import datetime` is imported inside `_now_iso()` instead of at module top. Works but unusual.

### INFO-5: task_number not persisted in task JSON on S3
- **File:** `storage.py:195-196`
- **What:** After creating a task, the number is assigned via `_increment_task_number()` and added to the output dict, but NOT written back to the task JSON in S3. Task numbers only exist in the cache file. If the cache is lost, numbers are gone.
- **Fix:** Either write task_number into the task JSON, or accept that the cache is the canonical source and back it up.

### INFO-6: JIRA `create` and `create_epic` don't accept `--channel` parameter
- **Files:** `jira_api.py` CLI parser
- **What:** Without channel context, the JIRA commands can't: (a) enqueue retries (WARN/CRIT-2), (b) write events, (c) update linked Beacon tasks. The JIRA commands are somewhat disconnected from the Beacon data model.
- **Fix:** Add optional `--channel` and `--task-id` parameters for full integration.

---

## Script-by-Script Notes

### storage.py
**Overall:** Solid. Clean CLI structure, proper error handling on S3 operations, good use of argparse subcommands. The JSON-to-stdout / logs-to-stderr pattern is correct for LLM consumption.

**Strengths:**
- Pagination handled correctly in `_list_keys()` (ContinuationToken loop)
- Rolling window idempotency is a smart pattern for bounded memory
- Task number cache is a reasonable approach for human-friendly IDs
- Event-first write pattern is architecturally correct (even if the failure handling needs work per CRIT-3)

**Concerns:**
- CRIT-1 (idempotency timing) is the biggest issue
- No input validation on fields or values
- `created_by` hardcoded (WARN-1)
- 776 lines is fine for what it does — not bloated

### risk.py
**Overall:** Clean and correct. The formula matches the spec exactly. Edge cases handled (no tasks = green/0).

**Strengths:**
- v2 event compatibility (`task_created`, `blocker_declared`, etc.) alongside v3 intents — smart for migration
- Correct timezone handling (strip to naive UTC, compare to utcnow)
- Staleness penalty considers both events and task timestamps

**Concerns:**
- No critical issues
- Minor code duplication in task filtering (INFO-3)
- 354 lines is appropriate

### jira_api.py
**Overall:** The most complex script and it handles real-world JIRA complexity well. Three-tier user resolution is correct. Dynamic transitions are correct. Epic link detection is correct.

**Strengths:**
- Exponential backoff with retries on 429/5xx
- Fallback from email to display name in user resolution
- Handles multiple JIRA user matches gracefully (returns list for disambiguation)
- ADF conversion for descriptions
- 941 lines is justified given the feature surface

**Concerns:**
- CRIT-2 (retry queue never called) is the showstopper
- WARN-5 (N+1 field fetch in epic_link mode) is a performance issue
- WARN-6 (link doesn't write events) breaks the audit trail
- Missing `--channel` parameter limits integration (INFO-6)
- No command to process the retry queue
- No command to load/use epic templates (mentioned in SKILL.md but not implemented)

### search.py
**Overall:** Functional but the least complete script. Ingestion works, search works, but they're not properly connected.

**Strengths:**
- YAML frontmatter format for content is good for metadata
- Rate limiting on Slack API calls (0.5s sleep)
- Skips bot messages and short messages during ingest

**Concerns:**
- WARN-3 (no channel-scoped search) is a data leakage issue
- WARN-4 (ingest doesn't trigger embedding) means ingest is incomplete without manual follow-up
- 342 lines is appropriate

---

## SOUL.md / AGENTS.md / TOOLS.md Review

### SOUL.md — Excellent
This will guide Claude correctly. Key strengths:
- Clear personality (concise, neutral, precise)
- Explicit boundaries ("I don't respond to every message")
- The pipeline section (parse → idempotency → policy → event → state → respond) is exactly what Claude needs
- "Channel = Project" isolation is stated clearly
- Error handling examples are concrete and natural

One minor note: SOUL.md says "Two-way sync between Beacon tasks and JIRA" in the DESIGN.md version but the actual SOUL.md says "Two-way link" — the implemented code only does one-way (Beacon → JIRA). Beacon doesn't poll JIRA for status changes. This is probably fine for v3 but the language should be precise.

### AGENTS.md — Good
- Intent mapping is comprehensive and matches the scripts
- Idempotency rules are clear
- Permissions model is simple and appropriate
- Memory model (storage-first, not memory files) is correct

One concern: The intent list doesn't distinguish between intents the agent handles conversationally (like `start_project`, `configure_reports`) vs. intents that map to script commands. Claude will figure it out from the SKILL.md files, but explicit mapping would help.

### TOOLS.md — Thorough
- Key patterns are documented and match the scripts
- Task and event schemas match the code
- Risk formula matches the implementation
- Intent surface tables are complete

One issue: TOOLS.md documents `channels/{channel_id}/history/{msg_ts}.json` in the key patterns but the actual code stores ingested content at `content/{channel_id}/{safe_ts}.md`. The `channels/.../history/` path is in the DESIGN.md layout but not used by any script.

---

## Missing from Design Spec

| Feature | Design Doc Section | Status | Severity |
|---|---|---|---|
| Retry queue processing command | "Processed by daily cron or next JIRA operation" | Not implemented | **High** — JIRA failures are permanent |
| Daily report check cron | Cron Jobs table: "8am MT weekdays" | Not implemented | Medium — no scheduled reports |
| Stale task alert cron | Cron Jobs table: "9am MT daily" | Not implemented | Medium — stale tasks go unnoticed |
| Registry refresh cron | Cron Jobs table: "midnight daily" | Not implemented | Low — registry stays stale |
| Embedding trigger cron | Cron Jobs table: "2am daily" | Not implemented | Medium — search index goes stale |
| Anti-noise / rate limiting | `anti_noise_state.json` mentioned | Not implemented | Low for now |
| Channel creator cache | `channel_creator_cache.json` in layout | Not implemented | Low — permissions not enforced |
| Project templates | `templates/project/{name}.json` | Not implemented — no template files | Low — onboarding works without |
| Epic templates loading | `templates/jira/{name}.json` | Function exists but no CLI command | Low |
| JIRA set-default command | "set-default KSA" in design | Not implemented | Low |
| Channel-scoped search | "Filter results by path prefix" | Not implemented | **High** — data leakage |
| Auto-trigger embedding on ingest | "After all uploads, trigger embedding" | Not implemented | Medium |
| Portfolio view command | Reports skill describes it | No script — agent must compose | Acceptable (agent-driven) |
| Deactivated JIRA user detection | Edge Cases in JIRA skill | Not implemented | Low |

### Summary of Gaps

**Phase 1 (scaffold) gaps:** Channel-scoped search, embedding trigger on ingest, retry queue integration. These should be fixed before ship.

**Phase 2 (harden) gaps:** All cron jobs, anti-noise, channel creator cache. Expected — these are called out as Phase 2 in the design doc.

**Phase 3+ gaps:** Templates, portfolio, natural task detection. Expected — these are enhancement features.

---

## Final Assessment

The architecture is right. The decomposition is clean. The scripts do what they claim to do, with three important exceptions (idempotency timing, retry queue not wired, event write failures swallowed). Fix those three criticals and the two high-severity warnings (channel-scoped search, embedding trigger on ingest), and this ships.

The v2 → v3 migration path is smooth (same bucket, same key patterns, additive new features). The SOUL.md and AGENTS.md will guide Claude to use the skills correctly. The risk formula is faithful to the spec.

What I'd fix in priority order:
1. **CRIT-1:** Idempotency timing (1 hour)
2. **CRIT-3:** Event write failure handling (30 min)
3. **CRIT-2:** Wire retry queue into JIRA commands (2 hours)
4. **WARN-3:** Channel-scoped search (1 hour)
5. **WARN-4:** Auto-trigger embedding on ingest (15 min)
6. **WARN-1:** `created_by` actor parameter (15 min)
7. **WARN-2:** Field validation on update_task (30 min)

Total: ~6 hours of hardening to go from "works" to "trustworthy."
