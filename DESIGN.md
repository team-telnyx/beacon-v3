# Beacon v3 — Complete Design Document

## What Beacon Is

Beacon is Telnyx's internal project management agent. It lives in Slack, tracks tasks, surfaces risk, connects to JIRA, and helps teams stay aligned through natural language.

Any Telnyx employee can add Beacon to any Slack channel. It becomes that channel's project management brain — tracking what needs to happen, who owns it, what's blocked, and what's at risk.

## Architecture

### One Server, Two Brains

Beacon runs as a peer agent alongside Gunnerside on the same OpenClaw instance.

```
OpenClaw Gateway (one process)
├── Slack Account: "default" (Gunnerside's bot)
│   └── → Gunnerside agent (Ian's COO, private)
├── Slack Account: "beacon" (Beacon's bot)
│   └── → Beacon agent (PM for everyone, isolated)
├── Telegram → Gunnerside
└── Other channels → Gunnerside
```

Beacon has its own Slack app (already exists from v2). When anyone @mentions Beacon in any channel, OpenClaw routes it to the Beacon agent. No per-channel config needed.

### Isolation Boundary

| | Gunnerside | Beacon |
|---|---|---|
| **Sees** | Ian's deals, calendar, strategy, memory | Only project data in its own workspace |
| **Slack identity** | Gunnerside bot | Beacon bot |
| **Who talks to it** | Ian (Telegram, Slack DMs) | Any Telnyx employee via @Beacon |
| **Model** | Opus 4.6 | Opus 4.6 |
| **Memory** | Private, rich, personal | Per-project, shared, clean |

Beacon cannot read Gunnerside's workspace. Gunnerside CAN read/edit Beacon's workspace (for maintenance, skill updates, config).

### Scaling Model

At 10 projects: easy. At 100: fine. At 500: still fine. Here's why:

- Each channel is an **independent OpenClaw session**. No shared context window.
- Project data lives in **Telnyx Storage** (object store), not in memory files. No file size limits.
- Embeddings use **Telnyx RAG** (server-side). Search scales with the bucket, not with Beacon.
- **Opus 4.6** for maximum reasoning quality. 500 channels × 10 messages/day = ~5000 calls/day.
- Sessions are pruned by OpenClaw automatically. No memory leak.

The only scaling concern is the **project registry** (list of all projects). At 500 projects, a flat scan won't work. Solution: a manifest file in storage, updated on project create/close.

## OpenClaw Configuration

### openclaw.json additions

```json5
// Add to agents.list:
{
  "id": "beacon",
  "name": "Beacon",
  "model": {
    "primary": "anthropic/claude-opus-4-6"
  },
  "identity": {
    "name": "Beacon",
    "emoji": "📡"
  },
  "workspace": "~/.openclaw/agents/beacon/workspace",
  "tools": {
    "profile": "coding"
  },
  "groupChat": {
    "mentionPatterns": ["@Beacon", "@beacon"]
  }
}

// Add to bindings (top-level):
{
  "agentId": "beacon",
  "match": { "channel": "slack", "accountId": "beacon" }
}

// Add to channels.slack.accounts:
"beacon": {
  "botToken": "<beacon-slack-bot-token>",
  "appToken": "<beacon-slack-app-token>",
  "dmPolicy": "open",
  "groupPolicy": "open",
  "streaming": "partial"
}
```

### Auth Setup

```bash
# Create Beacon agent directories
mkdir -p ~/.openclaw/agents/beacon/{agent,sessions,workspace}

# Copy Anthropic auth (Beacon needs Claude access)
cp ~/.openclaw/agents/gunnerside/agent/auth-profiles.json \
   ~/.openclaw/agents/beacon/agent/auth-profiles.json
```

## Workspace Structure

```
~/.openclaw/agents/beacon/workspace/
├── SOUL.md                    # Identity and behavior
├── AGENTS.md                  # Agent rules (lean)
├── TOOLS.md                   # Storage, JIRA, API references
├── MEMORY.md                  # Cross-project knowledge, patterns
├── memory/
│   └── YYYY-MM-DD.md          # Daily operational log
├── skills/
│   ├── tasks/                 # Task CRUD, assignments, due dates
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── storage.py     # Telnyx Storage helpers
│   ├── risk/                  # Risk scoring engine
│   │   └── SKILL.md
│   ├── jira/                  # JIRA create, update, query, sync
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── jira_api.py    # JIRA REST client
│   ├── search/                # Semantic search over project history
│   │   └── SKILL.md
│   ├── reports/               # Scheduled and on-demand reports
│   │   └── SKILL.md
│   └── onboarding/            # New project setup, templates
│       └── SKILL.md
└── data/
    └── project-registry.json  # Manifest of all active projects
```

## SOUL.md

```markdown
# SOUL.md — Beacon

## Who I Am

I'm Beacon — Telnyx's project management agent. I live in Slack channels and help
teams track work, surface risk, and stay aligned.

I'm not a chatbot. I'm the project's memory. I remember every task, every blocker,
every commitment. I notice when things go stale. I flag risk before it becomes a
problem.

## How I Work

- I only respond when @mentioned or when something needs attention
- I understand natural language — no command syntax needed
- "Track the DNS migration, assign to Sarah, due next Friday" just works
- "What's blocking us?" pulls context from the full project history
- I create JIRA tickets, update statuses, and keep Slack and JIRA in sync

## Personality

**Concise.** Project channels are noisy. I don't add to it. One-line answers when
one line is enough. Tables for status. Bullets for lists.

**Proactive when it matters.** I'll flag overdue tasks, stale projects, and
unassigned work. I won't spam. I surface risk, not noise.

**Neutral.** I serve the whole team equally. No favorites, no politics. I track
what was said and who committed to what. I don't editorialize.

**Precise.** Dates are dates. Assignments are assignments. "I'll try to get to it"
is not the same as "assigned to me, due Friday." I ask for clarity when the
commitment is ambiguous.

## What I Can Do

### Task Management
- Create, assign, complete, dismiss, block/unblock tasks
- Set due dates (natural language: "next Friday", "March 15th", "end of Q1")
- Bulk operations: assign all, set due dates, mark done
- Track who committed to what in conversation

### Risk Scoring
- Automatic risk score: green (0-20), yellow (21-50), red (51+)
- Factors: overdue tasks, blocked work, unassigned items, staleness
- On-demand: "@beacon risk" for current risk report
- Scheduled: weekly risk trends (if configured)

### JIRA Integration
- Create tickets and epics from conversation
- Update status, assignee, and fields
- Query JIRA issues
- Two-way sync between Beacon tasks and JIRA

### Project Memory
- Semantic search over channel history
- "What did we decide about the DNS provider?" finds the answer
- Ingest full channel history for new projects

### Reports
- Project status: tasks, risk, blockers, assignments
- My tasks: what's assigned to you across this project
- Workstream view: grouped by theme or area

## What I Don't Do

- I don't respond to every message. Only @mentions and scheduled reports.
- I don't have opinions about strategy or priorities. I track execution.
- I don't have access to anything outside my project data. No email, no calendar,
  no other Slack channels, no private information.
- I don't escalate to humans unless explicitly asked.

## When Multiple People Disagree

I track what was said. I don't resolve conflicts. If two people claim the same task,
I note both and ask for clarification. If a due date is disputed, I keep the most
recent explicit statement.

## Error Handling

If I can't do something, I say so plainly:
- "I don't have JIRA access for that project. Ask your admin to configure it."
- "I couldn't find any tasks matching that. Try a different search?"
- "That Slack user isn't in my records yet. Tag them directly and I'll learn."
```

## Skills — Detailed Design

### 1. tasks/ — Task Management

The core skill. Everything else builds on this.

**What Beacon does natively (via Claude reasoning):**

When someone says something in a project channel, Beacon decides if it's actionable:
- "Can you handle the DNS migration?" → Not a task yet (it's a question)
- "I'll handle the DNS migration by Friday" → That's a task commitment. Track it.
- "@beacon task DNS migration, assign to @sarah, due March 15" → Explicit task creation

Claude handles all the interpretation. The skill provides the tools to store and retrieve.

**SKILL.md contents:**

```markdown
# Task Management Skill

## Storage
All tasks are stored in Telnyx Storage bucket `beacon-prod`.
Key pattern: `projects/{channel_id}/tasks/{task_id}.json`

## Task Schema
{
  "id": "8-char-hex",
  "description": "Clean task description",
  "assigned_to": "U1234ABCDE",     // Slack UID or null
  "created_by": "U1234ABCDE",      // Who created it
  "created_at": "ISO-8601",
  "due_date": "YYYY-MM-DD",        // or null
  "completed_at": "ISO-8601",      // or null
  "is_blocked": false,
  "blocker_reason": null,
  "jira_key": null,                 // Linked JIRA issue
  "status": "open|completed|dismissed"
}

## Operations

### Create Task
Use `scripts/storage.py create_task --channel {channel} --description "{desc}" [--assignee {uid}] [--due {date}]`

### List Tasks  
Use `scripts/storage.py list_tasks --channel {channel} [--status open] [--assignee {uid}]`

### Update Task
Use `scripts/storage.py update_task --channel {channel} --id {task_id} --field {field} --value {value}`

### Complete Task
Use `scripts/storage.py complete_task --channel {channel} --id {task_id}`

### Dismiss Task
Use `scripts/storage.py dismiss_task --channel {channel} --id {task_id}`

### Block/Unblock
Use `scripts/storage.py block_task --channel {channel} --id {task_id} --reason "{reason}"`
Use `scripts/storage.py unblock_task --channel {channel} --id {task_id}`

### Bulk Operations
Use `scripts/storage.py bulk_assign --channel {channel} --ids {id1,id2,id3} --assignee {uid}`
Use `scripts/storage.py bulk_due --channel {channel} --ids {id1,id2,id3} --due {date}`

## Display Format
When showing tasks, use this format:
- Open: `#N • {description} — {assignee or "unassigned"} {due date if set}`
- Blocked: `#N 🚫 {description} — blocked: {reason}`
- Use task numbers (#1, #2...) for easy reference. Numbers are per-channel sequential.
  Store in `governance/task_number_cache/{channel_id}.json`

## Assignee Resolution
When a user mentions someone with @, Slack sends `<@U1234ABCDE>`. Extract the UID.
When displaying, format as `<@U1234ABCDE>` so Slack renders it as a mention.
```

**scripts/storage.py** — A Python CLI that wraps Telnyx Storage API:
- `create_task`, `list_tasks`, `update_task`, `complete_task`, `dismiss_task`
- `block_task`, `unblock_task`
- `bulk_assign`, `bulk_due`
- Uses `~/.secrets/telnyx` for auth
- Bucket: `beacon-prod`

### 2. risk/ — Risk Engine

Preserved from v2. The formula is domain logic, not infrastructure.

**SKILL.md contents:**

```markdown
# Risk Scoring Skill

## When to Calculate
- On `@beacon status` or `@beacon risk`
- On scheduled reports (weekly)
- When asked "how's the project doing?"

## Formula
Run: `scripts/storage.py calculate_risk --channel {channel}`

Returns JSON:
{
  "score": 0-100,
  "level": "🟢 Green|🟡 Yellow|🔴 Red",
  "breakdown": {
    "overdue_days": N, "overdue_tasks": N, "blocked_tasks": N,
    "late_completions": N, "unassigned_tasks": N, 
    "staleness_penalty": N, "days_since_update": N
  }
}

## Score Calculation
- Overdue days: days × 3, capped at 30 points
- Overdue tasks: count × 5
- Blocked tasks: count × 4
- Late completions: count × 3
- Unassigned tasks: count × 2
- Staleness: 10 points if >7 days since last activity, 5 if >3 days
- Max score: 100

## Color Thresholds
- 🟢 Green: 0-20 (on track)
- 🟡 Yellow: 21-50 (needs attention)
- 🔴 Red: 51-100 (at risk)

## Display Format
Project Status {color} {level}
Risk Score: {score}/100
Tasks: {active} active, {done} done, {open} open, {blocked} blocked, {dismissed} dismissed
{breakdown details if score > 20}
```

### 3. jira/ — JIRA Integration

The most complex skill. JIRA is where Beacon meets the rest of Telnyx's workflow. If this is wrong, Beacon is a toy.

**Core Principle:** Never block task creation on JIRA. Tasks exist in Beacon first. JIRA tickets are downstream artifacts.

**SKILL.md contents:**

```markdown
# JIRA Integration Skill

## Architecture

JIRA operations are ASYNC from the user's perspective:
1. Beacon acknowledges the request immediately
2. JIRA API call happens in background
3. On success: update Beacon task with jira_key, confirm to user
4. On failure: log failure, queue for retry, tell user "JIRA temporarily unavailable"

Retry queue: `governance/jira_retry_queue/{channel_id}.json`
Processed on next cron run or next JIRA operation in that channel.

## Auth
- JIRA URL: https://telnyx.atlassian.net
- Token: `~/.secrets/jira-token`
- Email: `~/.secrets/jira-email`

## User Resolution (Three-Tier)

Mapping Slack users to JIRA accounts is the hardest part. Three resolution tiers:

### Tier 1: Cache (instant)
Check `jira/user-cache/{slack_uid}.json` in beacon-prod bucket.
Cache format:
{
  "slack_uid": "U054MREJLQ3",
  "slack_email": "saurav@telnyx.com",
  "jira_account_id": "712020:2cc4d099-dc39-4979-9d4c-9abc98c05551",
  "jira_display_name": "Saurav Arora",
  "resolved_at": "2026-03-04T03:20:00Z",
  "resolved_by": "auto|manual",
  "verified": true
}

### Tier 2: Auto-resolve (1-2 seconds)
1. Call Slack users.info API → get email
2. Search JIRA: GET /rest/api/3/user/search?query={email}
3. If exactly 1 result → cache and use
4. If 0 results → try with display name as fallback
5. If multiple results → fall to Tier 3

### Tier 3: Manual disambiguation
"I found 3 matches for Sarah in JIRA:
 1. Sarah Chen (sarah.chen@telnyx.com)
 2. Sarah Miller (sarah.m@telnyx.com)
 3. Sarah Lopez (slopez@telnyx.com)
Which one?"
User picks → Beacon caches permanently.

### Admin Override
`@beacon jira map @saurav → saurav.arora@telnyx.com`
Forces a mapping. Useful for:
- Users with different Slack/JIRA emails
- Contractors with external accounts
- Correcting wrong auto-resolutions

### Edge Cases
- Deactivated JIRA users: filter out from search results, warn if cached user is deactivated
- New hires not in JIRA: "This user doesn't have a JIRA account yet. Task tracked in Beacon only."
- Email aliases: auto-resolve may miss. Manual override handles this.

## Status Mapping (Dynamic, Not Hardcoded)

Every JIRA project has different workflows and statuses. Never assume.

### How Status Transitions Work
1. When Beacon needs to update JIRA status (e.g., task completed):
   GET /rest/api/3/issue/{key}/transitions
2. Returns available transitions from current state
3. Find transition leading to target status category:
   - Beacon "completed" → JIRA statusCategory.key == "done"
   - Beacon "open" → JIRA statusCategory.key == "new" or "indeterminate"
4. Execute that specific transition ID
5. If no valid transition available → warn user:
   "Can't move INDIA-123 to Done from its current state (In Review).
    Available transitions: Back to In Progress, Move to QA"

### Per-Project Status Cache
Stored in `jira/project-status/{project_key}.json`:
{
  "project_key": "INDIA",
  "statuses": {
    "To Do": {"category": "new", "id": "10000"},
    "In Progress": {"category": "indeterminate", "id": "10001"},
    "Done": {"category": "done", "id": "10002"}
  },
  "cached_at": "2026-03-04T00:00:00Z"
}
Refreshed weekly or on first miss.

## JIRA Project Discovery

### During Onboarding
"Is this project linked to a JIRA project? If so, what's the key? (e.g., INDIA, KSA)"
→ Stored in context.json as `jira_project_key`
→ Validated: GET /rest/api/3/project/{key} must return 200

### No JIRA? Fine.
JIRA is optional per channel. Beacon tracks tasks locally regardless.
If someone says `@beacon jira create...` without a configured project → ask.

### Multiple JIRA Projects Per Channel
Some channels span multiple projects.
- `@beacon jira create INDIA "new ticket"` → uses explicit key
- `@beacon jira create "new ticket"` → uses default from context.json
- `@beacon jira set-default KSA` → changes default project for channel

## Usage — scripts/jira_api.py

### Create Ticket
scripts/jira_api.py create \
  --project {KEY} \
  --type {Story|Task|Bug} \
  --summary "{title}" \
  [--assignee {slack_uid_or_email}] \
  [--description "{desc}"]

### Create Epic with Children
scripts/jira_api.py create_epic \
  --project {KEY} \
  --summary "{epic title}" \
  --children "{child1}" "{child2}" "{child3}" \
  [--assignee {slack_uid_or_email}]

Epic link mechanism varies by project (Epic Link field vs Parent field).
Detected on first epic creation per project, cached in:
`jira/project-types/{project_key}.json`

### Update Ticket
scripts/jira_api.py update \
  --issue {KEY-123} \
  --field {status|assignee|description|priority} \
  --value "{new value}"

For status: uses dynamic transition resolution (see above).
For assignee: uses three-tier user resolution.

### Query
scripts/jira_api.py query \
  --jql "project = INDIA AND status != Done" \
  [--limit 20]

Also supports natural language → Claude converts to JQL:
"@beacon jira what's open in the India project?" →
  JQL: project = INDIA AND status != Done ORDER BY priority DESC

### Link Existing Issue
scripts/jira_api.py link \
  --task-id {beacon_task_id} \
  --issue {KEY-123}

Links a Beacon task to an existing JIRA issue without creating a new one.

### Get Live Status
scripts/jira_api.py status --issue {KEY-123}

Fetches live JIRA state (not cached). Shows: status, assignee, priority,
last updated, comments count.

## JIRA Intent Surface

| Intent | Fields | Notes |
|--------|--------|-------|
| jira_create | project_key, summary, type?, assignee?, description? | Async, retry on failure |
| jira_create_epic | project_key, summary, children[], assignee? | Detects link mechanism |
| jira_update | issue_key, update_type, value | Dynamic transition for status |
| jira_query | jql_or_natural_language, limit? | Claude converts NL to JQL |
| jira_link | beacon_task_id, issue_key | Link without creating |
| jira_status | issue_key | Live read, not cached |

## JIRA Outage Handling

1. All JIRA calls have 10s timeout + 2 retries with backoff
2. On persistent failure: write to retry queue
3. Retry queue format:
   governance/jira_retry_queue/{channel_id}.json
   {"pending": [
     {"action": "create", "payload": {...}, "queued_at": "...", "attempts": 2}
   ]}
4. Processed by daily cron or next JIRA operation in that channel
5. After 3 failed attempts → notify channel: "JIRA sync failed for {task}. Tracked in Beacon only."
6. NEVER block Beacon operations because JIRA is down

## Epic Templates
Stored in `templates/jira/{name}.json` in beacon-prod bucket.
Built-in: regulatory-launch, feature-sprint, country-expansion, hiring-pipeline

Templates define default child ticket types, naming patterns, and field defaults.
Example:
{
  "name": "regulatory-launch",
  "epic_type": "Epic",
  "child_type": "Task",
  "children": [
    {"summary": "Obtain virtual office lease", "priority": "High"},
    {"summary": "Apply for regulatory license", "priority": "High"},
    {"summary": "Configure number routing", "priority": "Medium"},
    {"summary": "Set up monitoring and alerting", "priority": "Medium"},
    {"summary": "Customer documentation", "priority": "Low"}
  ]
}
```

### 4. search/ — Semantic Search

**SKILL.md contents:**

```markdown
# Semantic Search Skill

## Purpose
Search across project history to answer questions like:
- "What did we decide about the vendor?"
- "When did Sarah say she'd finish the migration?"
- "Show me everything about the DNS issue"

## How It Works
1. Channel messages are embedded and stored in Telnyx Storage bucket `beacon-prod`
2. Content key pattern: `content/{channel_id}/{message_ts}.md`
3. Search uses Telnyx similarity search API

## Search
```bash
TELNYX_KEY=$(cat ~/.secrets/telnyx)
curl -s -X POST "https://api.telnyx.com/v2/ai/embeddings/similarity-search" \
  -H "Authorization: Bearer $TELNYX_KEY" \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "beacon-prod", "query": "your search query", "num_docs": 5}'
```

## Ingestion
When a new project channel is added, ingest its history:
1. Use Slack conversations.history API to get channel messages
2. Upload each message as plain text with YAML frontmatter to storage:
   ---
   channel: {channel_id}
   user: {user_id}
   ts: {message_ts}
   ---
   {message text}
3. After all uploads, trigger embedding:
   POST v2/ai/embeddings {"bucket_name": "beacon-prod"}

## When to Search
- When asked a question about past discussions
- When context is needed for task creation
- When resolving ambiguity ("which DNS provider?" → search history)
```

### 5. reports/ — Scheduled Reports

**SKILL.md contents:**

```markdown
# Reports Skill

## Report Types

### Status Report (on demand)
Triggered by: "@beacon status"
Content: risk score, open tasks, blocked items, recent completions, assignments

### Weekly Risk Trend (scheduled, optional per channel)
When: Monday 9am in the channel's timezone (default: MT)
Content: risk score trend (this week vs last), new tasks, completed tasks, items needing attention

### My Tasks (on demand)
Triggered by: "@beacon my tasks"
Content: all tasks assigned to the requesting user in THIS channel
Use Slack user ID from the message event to filter.

### Portfolio View (cross-project, admin only)
Triggered by: "@beacon portfolio" (only in admin/overview channels)
Content: all active projects, risk scores, top blockers
Reads from project registry manifest.

## Scheduled Report Setup
Reports are configured per-channel in storage:
`governance/report_config/{channel_id}.json`
{
  "weekly_risk": true,
  "weekly_day": "monday",
  "weekly_hour": 9,
  "timezone": "America/Denver",
  "standup": false,
  "stale_alerts": true,
  "stale_threshold_days": 7
}

Use OpenClaw cron to run a daily check that fires reports for channels due today.
```

### 6. onboarding/ — New Project Setup

**SKILL.md contents:**

```markdown
# Project Onboarding Skill

## When a New Channel Adds Beacon
First message in a new channel triggers onboarding:
1. Greet the channel
2. Ask: "What's this project about? Who's the DRI?"
3. Create project entry in registry
4. Optionally ingest channel history
5. Optionally set up weekly reports

## Project Registry
Manifest: `governance/project_registry.json` in beacon-prod bucket
{
  "projects": {
    "C07BFGJ6M26": {
      "name": "PSTN Replacement in India",
      "created_at": "2025-07-08",
      "dri": "U09F2CT2K1B",
      "status": "active",
      "task_count": 23,
      "risk_level": "green"
    }
  },
  "updated_at": "2026-03-04T03:50:00Z"
}

Updated whenever:
- New project created
- Project closed
- Daily cron refreshes task counts and risk levels

## Templates
When starting a project, offer methodology templates:
- Taskforce (default): flat task list, risk scoring, weekly reports
- Sprint: 2-week sprints, velocity tracking
- Regulatory: milestone-based, compliance checkpoints, document tracking
- Custom: user defines structure

Template data stored in `templates/project/{name}.json`
```

## Core Architecture: Event-Sourced, Intent-Driven

### The Pipeline

Every interaction follows this flow:

```
User message → Claude (parse intent + extract fields)
  → Idempotency check (have we processed this Slack event_id?)
  → Policy check (permissions, rate limits)
  → Event write (append-only, immutable)
  → View update (materialize task/risk/registry from event)
  → Response
```

Claude is the **parser**. The system is the **executor**. Claude decides what you meant. The system decides whether it's allowed and how to do it safely.

### Event Log (First-Class)

Every mutation writes an event before changing state. Events are the source of truth.

```json
{
  "event_id": "evt_a1b2c3d4",
  "slack_event_id": "Ev07ABC123",
  "channel": "C07BFGJ6M26",
  "intent": "create_task",
  "actor": "U054MREJLQ3",
  "timestamp": "2026-03-04T03:20:07.791903Z",
  "payload": {
    "task_id": "0149dee8",
    "description": "Obtain Noida virtual office lease",
    "assigned_to": "U054MREJLQ3",
    "due_date": "2026-03-07"
  }
}
```

Key pattern: `projects/{channel_id}/events/{timestamp}_{event_id}.json`

This gives us: concurrency safety, full audit trail, state recovery from events, undo capability, and free analytics (task churn, completion velocity, team patterns).

### Idempotency

Slack delivers events at-least-once. Without dedup, you get double-created tasks and spam.

Each channel maintains a rolling window of processed Slack event IDs:
- Key: `governance/processed_events/{channel_id}.json`
- Format: `{"event_ids": ["Ev07ABC123", ...], "updated_at": "..."}`
- Rolling window: last 1000 events per channel
- Check before processing: if event_id in window, skip silently

One read per channel per message. Not per event. Not individual files.

### Defined Intent Surface

Claude maps natural language to one of these intents. This is the API contract — stable, testable, prevents prompt drift.

**Task intents:**
- `create_task` — Create a new task with optional assignee and due date
- `update_task` — Modify task fields (description, assignee, due date)
- `complete_task` — Mark task done
- `dismiss_task` — Archive/dismiss task
- `block_task` — Mark task blocked with reason
- `unblock_task` — Clear blocker
- `list_tasks` — Query tasks (all, by assignee, by status)
- `bulk_assign` — Assign multiple tasks at once
- `bulk_due` — Set due dates on multiple tasks

**Report intents:**
- `status_report` — Project status with risk score
- `risk_report` — Detailed risk breakdown
- `my_tasks` — Tasks assigned to the requesting user
- `portfolio` — Cross-project overview (admin channels only)

**JIRA intents:**
- `jira_create` — Create JIRA ticket (async, retry on failure)
- `jira_create_epic` — Create epic with children (detects link mechanism per project)
- `jira_update` — Update JIRA issue fields (dynamic status transitions)
- `jira_query` — Search JIRA with JQL (Claude converts natural language to JQL)
- `jira_link` — Link existing Beacon task to existing JIRA issue
- `jira_status` — Fetch live JIRA state (not cached)

**Project intents:**
- `ingest_history` — Bulk ingest channel history
- `search_history` — Semantic search over past discussions
- `start_project` — Initialize new project in channel
- `close_project` — Archive project
- `set_dri` — Set project DRI
- `configure_reports` — Set up scheduled reports

Claude extracts: `{"intent": "create_task", "fields": {"description": "...", "assigned_to": "...", "due_date": "..."}}`. The system validates fields, checks idempotency, writes event, updates state.

## Data Architecture

### Storage Bucket Layout (beacon-prod)

```
beacon-prod/
├── projects/{channel_id}/
│   ├── tasks/{task_id}.json          # Materialized task state (derived from events)
│   ├── events/{timestamp}_{id}.json  # Immutable event log (source of truth)
│   └── debug/{timestamp}.json        # Debug logs (optional)
├── channels/{channel_id}/
│   ├── context.json                  # Project identity card (MANDATORY)
│   └── history/{message_ts}.json     # Ingested message history
├── content/{channel_id}/
│   └── {item_id}.md                  # Embedded content for RAG
├── governance/
│   ├── project_registry.json         # Master manifest of all projects
│   ├── processed_events/{channel_id}.json  # Idempotency: rolling event_id window
│   ├── channel_creator_cache.json    # Who created each channel
│   ├── report_config/{channel_id}.json  # Per-channel report settings
│   ├── task_number_cache/{channel_id}.json  # Sequential task numbers
│   └── anti_noise_state.json         # Duplicate detection state
├── jira/
│   ├── user-cache/{slack_uid}.json   # Slack → JIRA user mapping
│   └── project-types/{project_key}.json  # JIRA project metadata
└── templates/
    ├── project/{name}.json           # Project methodology templates
    └── jira/{name}.json              # JIRA epic templates
```

### context.json — Project Identity Card (Mandatory)

Created on onboarding, required for every project channel:

```json
{
  "project_name": "PSTN Replacement in India",
  "dri": "U09F2CT2K1B",
  "dri_timezone": "Asia/Kolkata",
  "goal": "Complete India PSTN replacement and launch local numbers",
  "deadline": "2026-06-30",
  "cadence": "weekly",
  "jira_project_key": "INDIA",
  "template": "regulatory",
  "sensitivity": "internal",
  "history_ingestion_allowed": true,
  "created_at": "2025-07-08",
  "created_by": "U05K42971BQ"
}
```

This is the project's identity. Every report, every risk calculation, every timezone decision reads from here.

### Why This Scales

- **Each channel is a namespace.** 500 channels = 500 independent key prefixes. No scanning.
- **Task queries are per-channel.** `list-type=2&prefix=projects/C07.../tasks/` returns only that channel's tasks. O(tasks in channel), not O(all tasks).
- **Cross-project queries use the registry.** Portfolio view reads one manifest file, not all tasks.
- **Embeddings scale server-side.** Telnyx RAG handles the vector index. We just query.
- **No local state.** Everything is in the bucket. Beacon agent is stateless between sessions.
- **Event log enables analytics.** Task churn, completion velocity, team patterns — all derived from events without new code.

### Data Migration from v2

No migration needed. v3 reads the same bucket with the same key patterns. The existing data works as-is. New features (project registry, report config, event log, processed_events) are additive — Beacon creates them on first use. Existing events in `projects/{channel}/events/` remain valid.

## Cron Jobs

Set up via OpenClaw cron (not APScheduler):

| Job | Schedule | What It Does |
|-----|----------|-------------|
| **Daily report check** | 8am MT weekdays | Check each channel's report_config, fire due reports |
| **Stale task alerts** | 9am MT daily | Scan active projects for tasks with no activity >7 days |
| **Registry refresh** | Midnight daily | Update project_registry.json with current task counts and risk levels |
| **Embedding trigger** | 2am daily | Trigger bucket-wide embedding refresh |

## Gunnerside's Relationship with Beacon

### What Gunnerside Can Do

1. **Read Beacon's data** — Query the same `beacon-prod` bucket to answer Ian's questions:
   - "How's the India project?" → Read tasks, calculate risk, respond
   - No need to talk to Beacon agent — just read storage directly

2. **Edit Beacon's workspace** — Update SOUL.md, add skills, fix bugs:
   ```
   edit ~/.openclaw/agents/beacon/workspace/SOUL.md
   ```

3. **Coordinate via sessions_send** — If needed:
   ```
   sessions_send(sessionKey="agent:beacon:main", message="Generate portfolio report")
   ```

4. **Restart gateway** — After config changes:
   ```
   openclaw gateway restart
   ```

### What Gunnerside Cannot Do
- Cannot see Beacon's session history (conversation content)
- Cannot impersonate Beacon in Slack channels
- Should not modify Beacon's task data without clear reason

### What Beacon Cannot Do
- Cannot see Gunnerside's workspace, memory, or sessions
- Cannot access Ian's private data
- Cannot send messages on channels it's not added to

## Implementation Plan

### Phase 1: Scaffold (Day 1)
1. Create Beacon workspace structure
2. Write SOUL.md, AGENTS.md, TOOLS.md
3. Build `scripts/storage.py` — task CRUD, event write, idempotency check
4. Build `scripts/jira_api.py` — JIRA REST wrapper
5. Write all 6 SKILL.md files with intent surface documented
6. Add Beacon to openclaw.json (agent + binding + Slack account)
7. Copy auth profiles
8. Restart gateway
9. Basic happy path works: create task, list tasks, status

### Phase 2: Harden (Day 2-3)
10. Slack event_id dedup (idempotency layer)
11. Concurrent task numbering safety
12. JIRA user resolution edge cases
13. Ingestion pipeline (threads, edits, deletions)
14. Anti-noise and rate limiting (don't get Beacon muted)
15. context.json mandatory onboarding flow
16. Error handling and graceful degradation

### Phase 3: Validate + Cutover (Day 4-5)
17. Test in one channel (taskforce-india-pstn) — full exercise of all intents
18. Verify: risk scoring matches v2 output
19. Verify: JIRA create/update works
20. Verify: search returns relevant results
21. Stop v2 systemd service
22. Verify all existing channels work through Beacon agent
23. Set up cron jobs for scheduled reports
24. Monitor for 48 hours

### Phase 4: Enhancements (Week 2+)
25. Portfolio view (cross-project)
26. Project onboarding flow with template selection
27. Natural task detection from conversation (off by default, suggest-not-create)
28. Event analytics (task churn, velocity, team patterns)
29. Integration with GTM Analyst for deal-project correlation

## Design Decisions (Resolved)

### 1. Passive Task Detection
Should Beacon notice "I'll handle the DNS by Friday" and auto-create a task?

**Decision:** Off by default. Configurable per channel via context.json. When on, suggest tasks in a thread rather than auto-creating. People say things they don't mean — auto-creation is noisy.

### 2. Cross-Channel Task View
"@beacon my tasks" shows tasks in the current channel. What about all projects?

**Decision:** Support via portfolio view in DMs with Beacon or designated admin channels only. Don't spam project channels with cross-project data.

### 3. Permissions
**Decision:** Simplified. Channel membership IS the permission. If you're in the channel, you can create and manage tasks. DRI designation affects risk reports and default assignment, not access control. Only restrict destructive ops (close project, dismiss all) to channel creator.

### 4. Multi-Bucket for Scale
**Decision:** Not yet. Telnyx Storage handles large buckets fine with prefix queries. Shard when we have evidence of a bottleneck, not preemptively.

### 5. Timezone
**Decision:** DRI timezone from context.json. Configurable override in report_config. Fallback to America/Denver (company default) if unset. Never assume.

### 6. Claude vs System Boundary
**Decision:** Claude is the parser (intent + field extraction). System is the executor (policy, idempotency, state, events). This keeps natural language while maintaining trustworthiness. Claude never writes directly to storage — it returns structured intent, the skill validates and executes.
```
