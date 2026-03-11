# Sapper API Review — Beacon v3

## Verdict: PASS

No critical issues. All API integrations will work in production. A handful of warnings around code hygiene and minor inefficiencies.

---

## Critical (wrong API usage, will fail in production)

None.

---

## Warnings (works but fragile)

### WARN-1: Hardcoded bucket name in search.py ingestion/indexing
- Script: `search.py:149,174`
- What: `cmd_ingest` and `cmd_index_message` hardcode `bucket = "beacon-prod"` as a string literal instead of using a module constant. `cmd_query` and `cmd_trigger_embedding` correctly use `args.bucket` with a default.
- Risk: If bucket name changes, these two functions get missed.
- Fix: Add `BUCKET = "beacon-prod"` as a module constant (like storage.py and risk.py do) and reference it.

### WARN-2: Epic Link field lookup inside child-creation loop
- Script: `jira_api.py:296-303`
- What: When `mechanism == "epic_link"`, the code calls `GET /rest/api/3/field` for **every child ticket** in `create_epic` to find the Epic Link custom field ID. This is an O(n) API call that should be O(1).
- Risk: Rate limiting on JIRA field endpoint with many children; unnecessary latency.
- Fix: Move the field lookup before the child loop, cache the Epic Link field ID, and reuse it.

### WARN-3: API key re-read from disk on every call
- Script: `search.py:_telnyx_headers()`, `jira_api.py:_get_jira_auth()`, `storage.py:_get_s3_client()`
- What: Every function call reads the API key from `~/.secrets/telnyx` (or jira secrets) from disk. In scripts that make multiple sequential API calls (e.g., `cmd_ingest` doing pagination + writes), this means dozens of redundant file reads.
- Risk: Not a correctness issue. Minor I/O overhead. Could fail mid-execution if the file is temporarily unavailable (e.g., NFS hiccup).
- Fix: Read once at module init or pass through function params. Low priority.

### WARN-4: Slack ingestion lacks per-request error handling for rate limits
- Script: `search.py:130-155`
- What: The `cmd_ingest` function has a fixed `time.sleep(0.5)` between Slack API calls but doesn't check for `429` responses or `Retry-After` headers. It relies on a blanket sleep.
- Risk: Under heavy load or if the Slack workspace has many messages, could hit Tier 3 rate limits (50+ req/min). The 0.5s sleep gives ~120 req/min headroom, which is generous but doesn't adapt.
- Fix: Check `resp.status_code == 429` and honor `Retry-After` header. Low priority — the current sleep is likely sufficient for Beacon's usage patterns.

### WARN-5: No BUCKET constant in search.py
- Script: `search.py` (module level)
- What: Unlike `storage.py` and `risk.py` which define `BUCKET = "beacon-prod"` at the module level, `search.py` has no such constant. The bucket name is either hardcoded in function bodies or comes from CLI args.
- Risk: Inconsistency across scripts. Easy to introduce drift.
- Fix: Add `BUCKET = "beacon-prod"` and use it as the default throughout.

---

## Validated (confirmed correct)

### API-1: Telnyx Storage (S3) client configuration — ✅
- `storage.py`, `risk.py`, `search.py`, `jira_api.py` all configure boto3 correctly:
  - `endpoint_url="https://us-central-1.telnyxstorage.com"` ✅
  - `aws_access_key_id=api_key, aws_secret_access_key=api_key` (Telnyx uses same key for both) ✅
  - `region_name="us-central-1"` ✅
- Auth reads from `~/.secrets/telnyx` at runtime ✅

### API-2: S3 put_object usage — ✅
- `storage.py:_put_json()` correctly sets `ContentType="application/json"` for task data ✅
- `search.py:cmd_ingest()` correctly sets `ContentType="text/markdown"` for ingested content ✅
- Body is properly encoded as UTF-8 bytes ✅
- Error handling catches `BotoCoreError` and `ClientError` ✅

### API-3: S3 get_object usage — ✅
- `storage.py:_get_json()` catches `s3.exceptions.NoSuchKey` for 404 handling ✅
- Returns `None` on not-found (graceful degradation) ✅
- Body decoded as UTF-8 ✅

### API-4: S3 list_objects_v2 with pagination — ✅
- `storage.py:_list_keys()` and `risk.py:_list_keys()` both correctly handle pagination:
  - Check `IsTruncated` flag ✅
  - Use `ContinuationToken` for next page ✅
  - Accumulate all keys across pages ✅

### API-5: Telnyx Embeddings API — trigger_embedding — ✅
- `search.py:cmd_trigger_embedding()` sends `POST https://api.telnyx.com/v2/ai/embeddings` ✅
- Payload is `{"bucket_name": args.bucket}` — no `model`, no `input` ✅
- Matches reference implementation (`sync.py:trigger_embedding()`) exactly ✅
- Accepts 200, 201, 202 status codes ✅

### API-6: Telnyx Embeddings API — similarity_search — ✅
- `search.py:cmd_query()` sends `POST https://api.telnyx.com/v2/ai/embeddings/similarity-search` ✅
- Payload: `{"bucket_name": ..., "query": ..., "num_docs": ...}` ✅
- Matches reference implementation (`search.py:similarity_search_with_retry()`) exactly ✅
- Auth via `Bearer` token in Authorization header ✅

### API-7: JIRA REST API v3 — ✅
- Base URL: `https://telnyx.atlassian.net` ✅
- All endpoints use `/rest/api/3/` (v3) ✅
- Auth: `HTTPBasicAuth(email, token)` — correct for Atlassian Cloud ✅
- Credentials from separate files (`~/.secrets/jira-email`, `~/.secrets/jira-token`) ✅

### API-8: JIRA issue creation payload (ADF format) — ✅
- `jira_api.py:_make_adf()` correctly creates Atlassian Document Format ✅
- `"type": "doc", "version": 1` with paragraph content nodes ✅
- This is required for JIRA Cloud v3 (v2 accepted plain text, v3 requires ADF) ✅

### API-9: JIRA transitions API — ✅
- `GET /rest/api/3/issue/{key}/transitions` to discover available transitions ✅
- `POST /rest/api/3/issue/{key}/transitions` with `{"transition": {"id": ...}}` to execute ✅
- Dynamic discovery (not hardcoded transition IDs) — handles different project workflows ✅
- Fuzzy name matching + category fallback — robust ✅

### API-10: JIRA user search API — ✅
- `GET /rest/api/3/user/search?query={email}` ✅
- Fallback: search by display name if email search returns nothing ✅
- Handles multiple results (returns list for disambiguation) ✅
- Results cached in S3 for performance ✅

### API-11: JIRA Epic link detection — ✅
- Correctly detects whether project uses modern `parent` field or legacy `Epic Link` custom field ✅
- Defaults to `parent` (correct for modern Jira Cloud) ✅
- Caches detection result in S3 to avoid repeated field lookups ✅
- Falls back to `GET /rest/api/3/field` to find Epic Link custom field ID ✅

### API-12: JIRA error handling — ✅
- Retries on 429 (rate limit), 500, 502, 503, 504 with exponential backoff ✅
- No retry on 401, 403, 404 (correct — these are permanent errors) ✅
- Timeout handling with retry ✅
- Error messages include status code and response body (truncated to 300 chars) ✅

### API-13: Slack conversations.history — ✅
- `search.py:cmd_ingest()` calls `GET https://slack.com/api/conversations.history` ✅
- Pagination via `cursor` parameter from `response_metadata.next_cursor` ✅
- Checks `has_more` flag correctly ✅
- Rate limiting via `time.sleep(0.5)` between requests ✅
- Auth via `Bearer` token in Authorization header ✅

### API-14: Cross-script API key consistency — ✅
- `storage.py`, `risk.py`, `search.py`: `~/.secrets/telnyx` ✅
- `jira_api.py`: `~/.secrets/jira-email` + `~/.secrets/jira-token` (appropriate — different service) ✅
- Slack: token passed via `--slack-token` arg or `SLACK_BOT_TOKEN` env var (appropriate — different service) ✅

### API-15: Bucket name consistency — ✅
- `storage.py`: `BUCKET = "beacon-prod"` ✅
- `risk.py`: `BUCKET = "beacon-prod"` ✅
- `search.py`: CLI default `"beacon-prod"` + hardcoded in ingestion (see WARN-1) ✅
- `jira_api.py`: `BUCKET = "beacon-prod"` ✅

### API-16: Key patterns consistent across scripts — ✅
- Tasks: `projects/{channel}/tasks/{id}.json` — used consistently in storage.py and jira_api.py ✅
- Events: `projects/{channel}/events/{timestamp}_{id}.json` — storage.py and risk.py ✅
- Content: `content/{channel}/{ts}.md` — search.py ingestion ✅
- Governance: `governance/` prefix for cross-cutting concerns ✅
- JIRA cache: `jira/` prefix for JIRA-specific caches ✅

---

## Summary

| Area | Status | Notes |
|------|--------|-------|
| Telnyx Storage (S3) | ✅ PASS | Correct config, proper pagination, good error handling |
| Telnyx Embeddings API | ✅ PASS | Matches reference implementation exactly |
| JIRA REST API v3 | ✅ PASS | Correct auth, ADF format, dynamic transitions |
| Slack API | ✅ PASS | Correct pagination, adequate rate limiting |
| Cross-script consistency | ✅ PASS | 1 minor inconsistency (WARN-1, WARN-5) |
| Error handling | ✅ PASS | Retries, backoff, graceful degradation throughout |

**Bottom line:** Ship it. The warnings are code hygiene improvements, not blockers.
