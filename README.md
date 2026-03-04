# Beacon

AI-powered project management for Slack. Beacon lives in your project channels, tracks tasks, surfaces risks, connects to JIRA, and helps teams stay aligned — all through natural language.

No command syntax to learn. Just talk to `@beacon` like you would a project manager.

## What Beacon Does

| Feature | How it works |
|---------|-------------|
| **Task Tracking** | Say "I'll have the design done by Friday" and Beacon tracks it as a task with a due date |
| **Blocker Detection** | Say "blocked on API credentials" and Beacon flags it, assigns it, follows up |
| **Risk Scoring** | Deterministic health score based on overdue tasks, blockers, and activity — not vibes |
| **Natural Language Q&A** | "What's blocking us?" / "Who owns the frontend?" / "Are we on track?" |
| **JIRA Integration** | Create tickets, update statuses, query issues — all from Slack |
| **Daily Digests** | Morning summary of what changed, what's due, what needs attention |
| **Scheduled Reports** | Weekly risk trends, stale task alerts, standup summaries |

## Quick Start

### 1. Add Beacon to a channel

```
/invite @beacon
```

### 2. Start a project

```
@beacon start tracking this channel — the project is "Q2 Platform Launch", due June 30, Sarah is the DRI
```

Or let Beacon figure it out:

```
@beacon start tracking this channel
```

Beacon will analyze recent messages, identify the project, suggest a DRI, and ask for confirmation.

### 3. Use natural language

No special syntax needed:

```
@beacon what's the status?
@beacon assign the auth task to Mike
@beacon what's due this week?
@beacon create a JIRA ticket for the API migration
@beacon who's blocked?
@beacon summarize for standup
```

## How It Works

Beacon runs as an [OpenClaw](https://github.com/openclaw/openclaw) agent. When added to a Slack channel, messages mentioning `@beacon` are routed to the Beacon agent, which uses Claude to understand intent and take action.

### Architecture

```
Slack Channel → OpenClaw Gateway → Beacon Agent (Claude)
                                       ├── Task Management (Telnyx Storage)
                                       ├── Risk Engine (deterministic scoring)
                                       ├── JIRA Bridge (create/update/query)
                                       ├── Project Memory (Telnyx RAG)
                                       └── Reports (scheduled via cron)
```

### Risk Scoring

Beacon uses a deterministic formula — no black box:

```
risk = (overdue_days × 3, cap 30) + (overdue_tasks × 5) + (blocked × 4)
     + (late_completions × 3) + (unassigned × 2) + staleness_penalty
```

| Score | Color | Meaning |
|-------|-------|---------|
| 0–20 | 🟢 Green | On track |
| 21–50 | 🟡 Yellow | Needs attention |
| 51+ | 🔴 Red | At risk |

## Examples

### Task tracking from conversation

> **Sarah:** I'll have the design mockups done by Thursday  
> **Beacon:** 📋 Tracked: "Design mockups" → @Sarah, due Thursday March 6

### Risk report

```
@beacon risk report
```

> 📊 **Q2 Platform Launch** — Risk Score: 34 🟡
>
> | Factor | Score | Detail |
> |--------|-------|--------|
> | Overdue tasks | 10 | 2 tasks past due |
> | Blockers | 8 | 2 active blockers |
> | Unassigned | 6 | 3 tasks unassigned |
> | Staleness | 10 | No activity in 4 days |
>
> **Top risks:**
> - API credentials still blocked (5 days)
> - No updates from @mike since Monday

### JIRA integration

```
@beacon create a JIRA ticket: migrate auth service to v2, assign to Mike, priority high
```

> 🎫 Created **PLAT-423**: "Migrate auth service to v2"  
> Assignee: Mike | Priority: High | Type: Task

## Configuration

Beacon is configured as an OpenClaw agent. Channel routing determines which Slack channels Beacon monitors.

```yaml
# Example channel route in OpenClaw config
channels:
  slack:
    routes:
      - match:
          channel: ["C07BFGJ6M26", "C0AJ55GR0TD"]
        agent: beacon
```

To add Beacon to a new channel:
1. `/invite @beacon` in the Slack channel
2. Update the channel route in OpenClaw config
3. Beacon starts monitoring immediately

## FAQ

**Does Beacon read every message in the channel?**  
Only in channels where it's been added and routed. It processes messages to detect tasks, blockers, and status updates. It doesn't store raw messages — it extracts structured data (tasks, risk factors) and uses Telnyx RAG for semantic search over history.

**Will Beacon spam the channel?**  
No. Beacon is anti-noise by design:
- Responds in threads, not the main channel
- Max 1 proactive alert per day
- Daily digests only when there's something worth reporting
- Mute options available

**What model does Beacon use?**  
Claude Sonnet 4 via OpenClaw for speed. Most interactions (task CRUD, status queries) are simple and benefit from fast response times.

**Can Beacon work across multiple channels?**  
Yes. You can ask cross-channel questions like "what's due this week across all projects?" and Beacon will aggregate.

**How is this different from Beacon v2?**  
v2 was a monolithic Slack Bolt app with regex-based intent classification. v3 is a native OpenClaw agent — Claude handles all reasoning, OpenClaw handles connectivity and lifecycle. Same features, better natural language understanding, easier to extend.

## Support

Questions or issues? Drop them in **#help-ai-platform** on Slack.

## License

Internal Telnyx tool.
