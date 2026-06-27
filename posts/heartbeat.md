---
title: "heartbeat: a cyclical contributor bot for your github org"
date: 2026-04-18
slug: heartbeat
tags: [ai, agents, tooling, release]
summary: "a cron-driven claude code agent that opens and reviews a small slate of prs each cycle<br/>`git clone git@github.com:cyberwitchery/cwl-agents`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/cwl-agents
---

heartbeat is a cyclical autonomous agent that contributes to a github org
using [claude code](https://docs.anthropic.com/en/docs/claude-code). it runs
every few hours and, in each cycle, opens a small slate of prs (2 small, 2
medium, 1 large), then reviews them and emails a summary.

it lives in the [cwl-agents](https://github.com/cyberwitchery/cwl-agents)
repo, which is the bucket where i'm collecting the long-running claude code
agents i use for the [cyber witchery lab](https://github.com/cyberwitchery)
org.

## why?

i have about 15 actively developed repos under cyberwitchery, most of them
rust libraries that need the usual routine maintenance: dep bumps, clippy
warnings, typos, missing tests, the occasional half-implemented feature
someone (me) left behind. i wanted something that would chip away at that
backlog steadily in the background, without me having to remember or
schedule it.

the obvious alternative is “just have claude code do it interactively when
i notice something”. but the work i notice isn't the work that actually
needs doing. what's visible is the stuff blocking me, not the quiet
backlog in repos i haven't opened in weeks. heartbeat sweeps the whole org
every cycle and picks its own work, which catches things i wouldn't.

## how it works

the core loop is a single `tick.sh` that cron fires every 30 minutes:

```
cron (every 30min)
  └─ tick.sh
       ├─ usage check (optional, skip if burning too fast)
       ├─ heartbeat_prompt.md          orchestrator
       │    ├─ sync repos
       │    ├─ sweep for work
       │    └─ for each topic:
       │         └─ heartbeat_topic_prompt.md   worker (own session, 30min cap)
       ├─ reviewer_prompt.md           reviews the prs just opened
       └─ release_check_prompt.md      (every few days) opens "publish vX.Y.Z" issues
```

each topic (a single concrete task like “fix this clippy warning” or
“implement the feature in issue #42”) runs in its own claude session with
a 30-minute timeout. that isolation is deliberate: a runaway implementation
on one topic can't eat the cycle's budget or take down the rest of the
slate.

tick.sh only schedules; it doesn't decide what to work on. the orchestrator
prompt reads the repos, picks topics, and spawns workers. prompts are plain
markdown with `${VAR}` placeholders that `envsubst` expands at runtime from
`config.env`.

## pieces

five prompts and a script:

- `tick.sh`: the cron entry point. handles locking, usage gating, state,
  and scheduling the next cycle with jitter.
- `heartbeat_prompt.md`: orchestrator. syncs the workspace, sweeps for
  work across the org, writes a balanced slate of topics, then spawns a
  worker session per topic.
- `heartbeat_topic_prompt.md`: worker. does the actual work for one
  topic, runs ci checks locally (fmt, clippy, ruff) before pushing, opens
  or updates a pr.
- `reviewer_prompt.md`: runs right after heartbeat. reviews every pr
  opened this cycle, checks ci, leaves a verdict (merge / revise / close),
  and sends a summary email via `msmtp` if configured.
- `release_check_prompt.md`: runs every few days. enumerates repos, reads
  changelogs, and opens “publish vX.Y.Z” tracking issues where things look
  release-ready.
- `get-github-app-token`: mints short-lived github app installation
  tokens. both heartbeat and reviewer are separate github apps with
  scoped permissions[^1].

## design choices

a few things that matter more than they look:

- **slate-based, not queue-based.** each cycle tries for 2 small, 2 medium,
  and 1 large pr. sizes are about reasoning depth, not line count. the
  large slot is mandatory. if the orchestrator can't find one, the prompt
  tells it to sweep harder rather than pad the small slots.
- **isolation per topic.** one session per task, 30-minute cap. a bad
  topic can't poison the cycle.
- **usage-gated.** an optional `USAGE_CHECK_CMD` lets you back off when
  you're burning api quota too fast. on a usage-capped plan this is the
  difference between “set it and forget it” and “wake up to a surprise
  bill”.
- **two github apps.** the contributor and the reviewer are separate
  identities with different permissions. the reviewer can comment and
  close prs but can't push code, which makes the review feel more like
  an actual second pair of eyes.
- **everything stays visible.** every pr body ends with a footer noting
  it was opened by the agent and hasn't been reviewed by me yet. reviews
  are signed the same way. the email summary marks anything flagged as
  “revise” or “closed” so i can triage from my inbox.

## what's next

it's running for the cyberwitchery org now, quietly ticking away in the
background on the pi 500 on my desk (a cycle every 2 to 2.5 hours, with
jitter). the interesting question is less “does it work” (it does,
mostly) and more “what kinds of work does it reliably do well, and where
does it need a human in the loop”. i'm
keeping a log of the patterns that keep surfacing (topics that always
time out, categories of review feedback that repeat across prs) and
using that to tune the prompts.

longer term i want to factor out the bits that are org-agnostic so the
same harness can host other agents. the release checker is already a
second tenant, and there are obvious candidates like a dependency triage
agent or a flaky-test sweeper. that's what the repo name hints at.

[^1]: the split matters because it's the only way to keep the reviewer
from being able to merge its own recommendations, even in principle.
