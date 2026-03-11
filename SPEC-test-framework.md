# Beacon v3 Test Framework Spec

## Goal
Comprehensive pytest-based integration test suite that validates every Beacon v3 skill script works correctly against live infrastructure (Telnyx Storage, JIRA, Telnyx RAG).

## Architecture
- **Location:** `~/beacon-v3/tests/`
- **Runner:** pytest with JSON output
- **Target scripts:**
  - `~/.openclaw/agents/beacon/workspace/skills/tasks/scripts/storage.py`
  - `~/.openclaw/agents/beacon/workspace/skills/risk/scripts/risk.py`
  - `~/.openclaw/agents/beacon/workspace/skills/jira/scripts/jira_api.py`
  - `~/.openclaw/agents/beacon/workspace/skills/search/scripts/search.py`
- **Test channel:** `C_TEST_BEACON` (dedicated test channel ID, configurable via env)
- **Cleanup:** All test data created must be cleaned up after each test run

## Test Coverage Required

### storage.py Tests
1. `create_task` — creates task, returns valid JSON with id, task_number, status=open
2. `create_task` with all optional fields (assignee, due, actor)
3. `list_tasks` — returns tasks including newly created ones
4. `update_task` — each updatable field (description, assigned_to, due_date, status, is_blocked, blocker_reason)
5. `update_task` — rejects invalid field names
6. `block_task` — sets is_blocked=true and blocker_reason
7. `unblock_task` — clears block
8. `complete_task` — sets status=completed and completed_at
9. `dismiss_task` — sets status=dismissed
10. `bulk_assign` — updates multiple tasks
11. `bulk_due` — updates multiple tasks
12. `idempotency` — duplicate slack-event-id returns status=duplicate
13. `write_event` — writes custom event, verifiable
14. `get_context` / `set_context` — round-trip project context
15. `next_task_number` — auto-increments
16. `get_registry` / `update_registry` — channel registry CRUD
17. Event ordering — events written in correct chronological order

### risk.py Tests
18. `calculate` — returns valid score, level, breakdown for channel with tasks
19. `calculate` — empty channel returns score 0, green
20. Score components — overdue tasks increase score
21. Score components — blocked tasks increase score
22. Score components — unassigned tasks increase score
23. Level thresholds — green (0-3), yellow (4-6), red (7+)

### jira_api.py Tests
24. `query` — JQL returns results with expected fields
25. `query` — empty results handled gracefully
26. `create` — creates issue, returns key and URL
27. `create` — invalid project returns error (not crash)
28. `status` — returns issue details
29. `update` — updates issue field
30. `link` — links Beacon task to JIRA issue, writes event
31. `resolve_user` — cache tier works after map_user
32. `map_user` — maps Slack UID to JIRA account
33. `process_retries` — processes retry queue, handles permanent failures

### search.py Tests
34. `query` — returns results from RAG with scores
35. `query` with --channel — filters results by channel prefix
36. `query` — empty query returns graceful empty result
37. `ingest` — uploads content and triggers embedding (if testable)

### Cross-Script Tests
38. Full lifecycle: create → update → block → unblock → complete → verify via list
39. Create task → link to JIRA → verify jira_key persisted
40. Create tasks → calculate risk → verify score reflects task states

## Implementation Rules
- Each test is a pytest function
- Tests run via subprocess (call scripts as CLI, parse JSON stdout)
- conftest.py handles setup/teardown (create test tasks, clean up after)
- All tests use a configurable test channel (default: C07BFGJ6M26)
- Environment variables: TELNYX_API_KEY, JIRA_EMAIL, JIRA_TOKEN
- Tests must be idempotent — safe to run repeatedly
- Test JIRA issues created in LEGAL project with "[TEST]" prefix
- Cleanup fixture dismisses all test tasks and deletes test JIRA issues
- pytest markers: @storage, @risk, @jira, @search, @lifecycle
- JSON output parsing must handle deprecation warnings on stderr
