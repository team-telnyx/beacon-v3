# Beacon Onboarding Guide

How to roll out Beacon to your team, from pilot to full adoption.

## Phase 1 — Pilot (Week 1)

### Pick 2–3 channels

Choose channels that:
- Have active projects with clear deadlines
- Get 10+ messages/day (enough signal for Beacon to work with)
- Have engaged project owners who'll give feedback

Good mix: 1 engineering project, 1 cross-functional, 1 client/partner project.

### Add Beacon

```
/invite @beacon
```

### Create a project

```
@beacon start tracking this channel
```

Beacon will:
1. Analyze the last 30 days of messages
2. Identify the project, participants, and apparent DRI
3. Extract existing tasks and blockers
4. Ask for confirmation before tracking

Or be explicit:

```
@beacon start project "Q2 Launch" — due June 30, DRI is @sarah
```

### Let it observe (48 hours)

For the first 48 hours, Beacon builds context. Don't expect perfect results immediately.

**Do:**
- Use the channel normally
- Ask Beacon questions ("what's the status?")
- Correct it when it's wrong ("that's not a task, ignore it")

**Don't:**
- Change thresholds yet (need baseline data)
- Judge accuracy on day 1 (it improves with context)

### Review and tune

After 48 hours:
- Was the daily digest useful? Too noisy? Too quiet?
- Were blocker detections accurate?
- Did risk scores feel right?

Tell Beacon what to adjust:

```
@beacon only flag blockers if they're more than 2 days old
@beacon skip messages from bots
@beacon the DRI is actually @mike, not @sarah
```

## Phase 2 — Expand (Week 2+)

Based on pilot feedback, add more channels. Each new channel follows the same pattern:
1. `/invite @beacon`
2. `@beacon start tracking`
3. 48-hour observation
4. Tune as needed

### Selective tracking

Not everything in a channel needs tracking. If engineering work lives in JIRA:

```
@beacon track "Marketing Campaign" and "Sales Enablement" but ignore engineering discussions
```

### Channel-specific settings

Each channel can have its own:
- **Digest schedule:** Daily, weekly, or off
- **Alert threshold:** How many days before a stale task triggers an alert
- **DRI:** Who owns the project
- **JIRA project:** Which JIRA project to create tickets in

## Phase 3 — Steady State

Once teams are comfortable:

### Cross-channel queries

```
@beacon what's due this week across all projects?
@beacon which projects are red?
@beacon show me all blockers company-wide
```

### Stakeholder briefings

Project owners with 2+ projects get weekly DM summaries with risk trends and action items.

### JIRA sync

Keep Slack and JIRA in sync:

```
@beacon sync PLAT-423 — it's done
@beacon what JIRA tickets are still open for this project?
@beacon create an epic for the Q3 migration with 5 child tickets
```

## Tips

1. **Correct Beacon publicly.** When you say "that's not a task" in the channel, everyone learns what Beacon should and shouldn't track.

2. **Use natural language.** You don't need special commands. Talk to Beacon like a colleague.

3. **Trust the risk score.** It's deterministic and explainable. If the score feels wrong, ask Beacon to break it down — the factors will tell you why.

4. **One DRI per project.** Beacon works best when someone clearly owns the project. Shared ownership = no ownership.

5. **Don't over-track.** Beacon works best on real projects with real deadlines. Adding it to a social channel just creates noise.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Beacon isn't responding | Check it's been `/invite`d and the channel is routed in OpenClaw config |
| Too many false positive tasks | Tell Beacon: "@beacon ignore messages like that" |
| Risk score seems wrong | Ask "@beacon break down the risk score" — check each factor |
| Daily digest not appearing | Check digest schedule: "@beacon when is the daily digest?" |
| JIRA tickets not creating | Verify JIRA project key: "@beacon what JIRA project is this linked to?" |

## Support

**#help-ai-platform** on Slack for setup issues or feature requests.
