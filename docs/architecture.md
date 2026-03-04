# Beacon Architecture

## Overview

Beacon v3 is a native [OpenClaw](https://github.com/openclaw/openclaw) agent. Unlike v2 (a monolithic Slack Bolt app), v3 delegates connectivity, lifecycle, and scheduling to OpenClaw and focuses purely on project management logic.

```
Slack Channel
    ↓ (message with @beacon mention)
OpenClaw Gateway
    ↓ (route to beacon agent)
Beacon Agent (Claude Sonnet 4)
    ├── Task Management skill    → Telnyx Storage
    ├── Risk Engine skill        → Deterministic scoring
    ├── JIRA Bridge skill        → Atlassian API
    ├── Project Memory skill     → Telnyx RAG (embeddings + similarity search)
    └── Reports skill            → OpenClaw cron
```

## Components

### Agent (Claude Sonnet 4)

The agent handles all reasoning. No regex intent classification, no command parsing — Claude interprets every message and decides what action to take (if any).

Model choice: Sonnet 4 for speed. Beacon interactions are high-volume, low-complexity. Response target: <3 seconds for simple queries.

### Skills

| Skill | Purpose | Storage |
|-------|---------|---------|
| **task-management** | CRUD operations on tasks (create, assign, complete, block) | Telnyx Storage (`beacon-prod` bucket) |
| **risk-engine** | Deterministic risk scoring with explainable factors | Computed on-demand from task data |
| **jira-bridge** | Create/update/query JIRA issues | Atlassian REST API |
| **project-memory** | Semantic search over channel history | Telnyx RAG (embeddings + similarity search) |
| **reports** | Scheduled digests, risk trends, standup summaries | OpenClaw cron triggers |

### Storage

All task and project data lives in Telnyx Storage:
- **Bucket:** `beacon-prod`
- **Key pattern:** `tasks/{channel_id}/{task_id}.json`
- **Channel state:** `channels/{channel_id}/state.json`

### Risk Scoring Formula

```
risk = (overdue_days × 3, cap 30)
     + (overdue_tasks × 5)
     + (blocked_tasks × 4)
     + (late_completions × 3)
     + (unassigned_tasks × 2)
     + staleness_penalty
```

Staleness penalty: +10 if no channel activity in 3+ days, scaling up with inactivity.

| Score | Status |
|-------|--------|
| 0–20 | 🟢 On track |
| 21–50 | 🟡 Needs attention |
| 51+ | 🔴 At risk |

## v2 → v3 Migration

| v2 Component | Lines | v3 Replacement |
|-------------|-------|----------------|
| Socket Mode handler | ~200 | OpenClaw Slack channel |
| Intent classification (3-tier regex) | ~500 | Claude native reasoning |
| Permission framework | ~300 | OpenClaw agent config |
| Storage abstraction | ~200 | Telnyx Storage skill |
| APScheduler | ~150 | OpenClaw cron |
| Health monitoring | ~100 | OpenClaw process lifecycle |
| Command handlers | ~1500 | Skill tool functions |
| **Total removed** | **~3000+** | |
| **Domain logic preserved** | **~800** | As modular skills |

## Channel Routing

Channels are routed to Beacon via OpenClaw config:

```yaml
channels:
  slack:
    routes:
      - match:
          channel: ["C07BFGJ6M26"]
        agent: beacon
```

Adding a new channel = one config update. No code changes, no redeployment.
