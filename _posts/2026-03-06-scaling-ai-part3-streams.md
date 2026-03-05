---
layout: post
title: "Unimatrix Zero — Scaling Squad with Workstreams"
date: 2026-03-06
tags: [ai-agents, squad, github-copilot, scaling, star-trek, borg]
series: "Scaling AI-Native Software Engineering"
series_part: 3
---

> *"Unimatrix Zero: where individual drones regain their identity within the collective."*
> — Star Trek: Voyager

In [Part 1](/2026/03/04/scaling-ai-part1-first-team.html), I set up my first Squad team and watched AI agents work in parallel. In [Part 2](/2026/03/05/scaling-ai-part2-collective.html), I learned how to share knowledge across repos using upstream inheritance. But there was one question I couldn't stop thinking about:

*Can you run three AI teams on the same repo simultaneously?*

Not three agents on one team — three *separate teams*, each owning a different slice of the codebase, each with their own backlog, each working concurrently. Like three Borg unimatrix clusters operating on the same vessel.

I decided to find out. This is the story of the experiment, what broke, what worked, and the feature that emerged from the wreckage.

![Unimatrix Zero](/assets/scaling-ai-part3-streams/unimatrix-zero.png)
*"Each workstream has its own identity, but they're all part of the same collective."*

## The Experiment

The repo is [tamirdresher/squad-tetris](https://github.com/tamirdresher/squad-tetris) — a multiplayer Tetris game built as a monorepo. It's not a toy project; it has real architecture:

- **React frontend** — game board, lobby, player UI
- **Node.js backend** — WebSocket server, matchmaking, game state sync
- **Game engine** — collision detection, piece rotation, scoring (shared package)
- **Azure infrastructure** — Container Apps, Cosmos DB, SignalR

I created 30 GitHub issues across three teams using labels:

| Team | Label | Issues | Focus |
|------|-------|--------|-------|
| UI Team | `team:ui` | 10 | React components, game board, animations |
| Backend Team | `team:backend` | 10 | WebSocket server, game state, matchmaking |
| Cloud Team | `team:cloud` | 10 | Azure infra, CI/CD, monitoring |

Then I spun up **three GitHub Codespaces**, each with its own devcontainer configuration and a `SQUAD_TEAM` environment variable identifying which team it belonged to.

Three machines. Three Squad instances. One repo. Let's go.

## Setting It Up

Each Codespace had a devcontainer.json that looked like this:

```json
{
  "name": "Squad - UI Team",
  "image": "mcr.microsoft.com/devcontainers/javascript-node:20",
  "containerEnv": {
    "SQUAD_TEAM": "ui-team"
  },
  "postCreateCommand": "npm install && squad init"
}
```

When `squad init` ran, it cast the same Star Trek TNG team in each Codespace — Riker as Lead, Troi on Frontend, Geordi on Backend, Worf on Testing, Picard on DevOps. The casting is deterministic per repo name, so all three Codespaces got the same crew. But the `SQUAD_TEAM` env var told each Squad instance which issues to care about.

The first message to each Codespace was simple:

```
Ralph, go. Pick up all team:ui issues and start working through them.
```

```
Ralph, go. Pick up all team:backend issues and start working through them.
```

```
Ralph, go. Pick up all team:cloud issues and start working through them.
```

And then I sat back and watched three terminals simultaneously.

## What Worked

The results were genuinely impressive. In roughly two hours:

**9 issues closed** with real, working code:

- A Tetris game engine with full collision detection and piece rotation (7 standard Tetrominos — I, O, T, S, Z, J, L)
- A WebSocket server handling multiplayer game state synchronization
- A React game board component rendering a 10×20 grid with ghost pieces and next-piece preview
- CI/CD pipelines for building and deploying to Azure Container Apps

Branch-per-issue was followed consistently. Each agent created a feature branch named after the issue number, worked in isolation, and opened a PR when done. Actual commit messages from the experiment:

```
feat(game-engine): implement tetromino rotation with wall kick (#12)
feat(websocket): add room-based multiplayer with spectator mode (#18)
feat(ui): create responsive game board with CSS grid (#7)
ci: add GitHub Actions workflow for Container Apps deployment (#25)
```

The branch isolation meant that even though three teams were working simultaneously, their day-to-day commits didn't interfere with each other. Each PR was a clean diff against main.

The quality wasn't production-ready — this was an experiment, not a product launch — but the code was *real*. The game engine actually detected collisions. The WebSocket server actually handled connections. The React components actually rendered Tetrominos. These weren't hallucinated code snippets; they were functional implementations.

## What Broke

And now for the honest part. Because things absolutely broke.

**Label leakage.** The Cloud team's Ralph picked up a UI issue that had been mislabeled. An Azure infrastructure agent spent 20 minutes trying to build a React component. It did not go well. The issue was eventually reassigned, but it wasted a cycle and produced a garbage PR that had to be closed.

**Merge conflicts in shared packages.** The game engine was a shared package used by both the UI and Backend teams. When both teams modified `packages/game-engine/src/types.ts` in the same two-hour window, the resulting PRs had merge conflicts. Neither agent knew about the other's changes because they were working in isolated branches.

**Branch proliferation.** The three teams created 15 branches total, but only 6 PRs actually merged cleanly. Some branches had conflicts. Some had code that didn't compile because it depended on another branch's changes that hadn't merged yet. Some were abandoned when Ralph re-triaged the issue to a different approach.

**Codespace timeouts.** GitHub Codespaces have an idle timeout. When one Codespace went to sleep during a long-running agent task, it killed the in-progress work. The agent came back to a half-written file and got confused about state. I had to manually clean up and restart twice.

**Cross-team dependencies.** Issue #14 (Backend: "implement game state serialization") depended on types defined in Issue #8 (UI: "create tetromino type definitions"). The Backend agent started before the UI agent had merged its types, so it invented its own — which were subtly different. Two sources of truth for the same data model. Classic distributed systems problem, now with AI agents.

## The Insight

Here's what I realized watching this experiment unfold: **every single problem I hit is a problem human teams face too.**

Label leakage? That's a mislabeled Jira ticket. Merge conflicts in shared code? That's why monorepo teams have code ownership files. Branch proliferation? That's every team without a branch cleanup policy. Cross-team dependencies? That's why organizations invented architecture review boards.

The AI teams weren't failing in novel ways. They were failing in *exactly the same ways human teams fail* when you put three teams on one repo without coordination guardrails.

For human teams, we solve this with swim lanes — clear boundaries around who owns what code, which issues belong to which team, and how cross-team dependencies are communicated.

For AI teams, we need the same thing. And that's what Workstreams are.

## Workstreams — The Solution

After the experiment, I contributed to [a PR](https://github.com/bradygaster/squad/pull/189) that introduced **Workstreams** — Squad's answer to multi-team coordination in a single repo.

A Workstream is defined in `workstreams.json`:

```json
{
  "workstreams": [
    {
      "name": "ui-team",
      "labelFilter": "team:ui",
      "folderScope": ["packages/ui", "packages/game-board"],
      "workflow": "default"
    },
    {
      "name": "backend-team", 
      "labelFilter": "team:backend",
      "folderScope": ["packages/server", "packages/game-engine"],
      "workflow": "default"
    },
    {
      "name": "cloud-team",
      "labelFilter": "team:cloud",
      "folderScope": ["infra/", ".github/workflows/"],
      "workflow": "default"
    }
  ]
}
```

Each workstream defines three things:

1. **labelFilter** — Which GitHub issues this team picks up. Ralph only processes issues matching the workstream's label filter. No more label leakage.

2. **folderScope** — Which directories this team primarily works in. This is *advisory*, not a hard lock — the backend team can still read from `packages/ui` to understand interfaces, and shared packages like `game-engine` are accessible to multiple workstreams. But when creating new files, agents prefer their scoped directories.

3. **workflow** — Which ceremony and decision-making workflow to use. Different teams might have different review requirements or deployment processes.

Auto-detection via `SQUAD_TEAM` environment variable means you don't need to manually select a workstream. Set `SQUAD_TEAM=ui-team` in your Codespace's devcontainer, and Squad automatically activates the right workstream.

Branch-per-issue is enforced at the workstream level. Each workstream creates branches with a team prefix: `ui-team/issue-7-game-board`, `backend-team/issue-18-websocket`. This makes it obvious in the PR list which team owns which work, and makes cleanup trivial.

## Cost Optimization

Three Codespaces running simultaneously is expensive. At $0.18/hour for a 4-core machine, that's $0.54/hour — or roughly $13/day if you're running them 24 hours.

Workstreams enable a cheaper alternative: **sequential activation on one machine**.

```bash
squad workstreams activate ui-team
# Ralph works through ui-team issues...

squad workstreams activate backend-team  
# Now Ralph switches to backend-team issues...

squad workstreams activate cloud-team
# And now cloud-team...
```

Same branch-per-issue isolation. Same label filtering. Same folder scoping. But on one machine instead of three, at one-third the cost.

The tradeoff is speed — sequential execution takes 3x longer than parallel. But for many teams, the cost savings are worth it. You can also hybrid: run the high-priority workstream in a dedicated Codespace and cycle the lower-priority workstreams sequentially on a second machine.

The cost math gets even better when you factor in model selection. Squad already uses cheaper models for triage and planning, reserving expensive models for code generation. With Workstreams, Ralph's triage loop — scanning issues, checking labels, assigning to agents — runs almost entirely on fast/cheap models. The expensive model only activates when an agent starts writing code.

## What's Next

Workstreams solved the immediate problem of multi-team coordination on a single repo. But the experiment revealed deeper questions that we're still working on:

- **Meta-coordinator**: A coordinator of coordinators — an agent that watches all workstreams, detects cross-team dependencies, and proactively resolves conflicts before they happen. Think of it as the Borg Queen, if the Borg Queen were helpful instead of terrifying.

- **Round-robin mode**: Instead of manually activating workstreams, Ralph cycles through them automatically. Work on UI issues for 30 minutes, switch to backend for 30 minutes, switch to cloud for 30 minutes, repeat. Fully automated, fully unattended.

- **Cross-workstream dependency detection**: When Issue #14 depends on types from Issue #8, the meta-coordinator should detect this and either sequence them correctly or coordinate the type definitions up front.

- **Conflict detection for overlapping PRs**: Before two PRs from different workstreams merge, check if they modify the same files. If they do, flag it for human review or attempt an automated merge resolution.

## The Full Picture

Looking back at this three-part series, the scaling story follows a clear arc:

1. **One team, one repo** ([Part 1](/2026/03/04/scaling-ai-part1-first-team.html)) — Squad gives you a coordinated AI team that works in parallel. Riker leads, agents specialize, Ralph monitors. It's impressive and immediately useful.

2. **One team, many repos** ([Part 2](/2026/03/05/scaling-ai-part2-collective.html)) — Upstream inheritance connects isolated teams into a collective. Knowledge flows up, decisions flow down, skills accumulate across your entire organization.

3. **Many teams, one repo** (this post) — Workstreams give each team a swim lane within a shared codebase. Label filtering, folder scoping, and branch-per-issue keep teams from stepping on each other.

Together, these features let you scale from "one developer trying Squad for the first time" to "multiple AI teams across multiple repos in an organization" — all using the same framework, the same Copilot CLI foundation, the same Borg-themed casting system.

The Borg Collective assimilated entire civilizations. Your Squad Collective can assimilate your backlog. The difference is, your developers get to keep their individuality.

Resistance is futile — but collaboration is optional. Choose wisely. 🟩⬛

---

*Check out the [squad-tetris experiment repo](https://github.com/tamirdresher/squad-tetris) if you want to see the actual code, issues, and PRs from the multi-Codespace experiment. And the [Workstreams PR](https://github.com/bradygaster/squad/pull/189) if you want to see how the feature was built.*
