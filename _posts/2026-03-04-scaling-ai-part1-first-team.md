---
layout: post
title: "Resistance is Futile — Your First AI Engineering Team"
date: 2026-03-04
tags: [ai-agents, squad, github-copilot, scaling, star-trek, borg]
series: "Scaling AI-Native Software Engineering"
series_part: 1
---

> *"You will be assimilated."*
> — The Borg, Star Trek: The Next Generation

I've been using [Squad](https://github.com/bradygaster/squad) on my work repos for the past three weeks, and it's changed how I think about software engineering. Not incrementally — fundamentally. This isn't a product overview (Brady Gaster, Squad's creator, has [excellent docs and blog posts](https://github.com/bradygaster/squad) covering that). This is what it's actually like to use Squad as a practitioner, day after day, on real codebases.

![Borg cube](/assets/scaling-ai-part1-first-team/borg-cube.png)
*"Resistance is futile. Your backlog will be assimilated."*

## Why Squad, Not Just Copilot?

If you haven't seen Squad yet, the short version: [Brady Gaster](https://github.com/bradygaster) built a framework that turns GitHub Copilot CLI into a coordinated AI team — not one generalist agent, but a *team* of specialists working in parallel. For the full picture, check out the [Squad repo](https://github.com/bradygaster/squad) and its 22+ blog posts covering everything from team formation to the REPL to casting. What I want to share here is what it feels like from the practitioner side.

## Your First `squad init`

Setting up Squad starts with `squad init` in your repo. It walks you through a config file, asks about your project structure, and then does something delightful: it *casts* your team.

Squad has 31 fictional universes built in — Star Trek, Lord of the Rings, Marvel, and more. The selection is deterministic based on your repo name, so you'll always get the same team for the same project. It's an easter egg system, and it's genuinely fun.

For my repo, Squad picked **Star Trek: The Next Generation**:

| Role | Agent | Specialty |
|------|-------|-----------|
| 🎖️ Lead | **Riker** | Architecture, task decomposition, delegation |
| 🎨 Frontend | **Troi** | UI components, styling, user experience |
| ⚙️ Backend | **Geordi** | APIs, data models, business logic |
| 🧪 Tester | **Worf** | Test suites, edge cases, validation |
| 🔧 DevOps | **Picard** | CI/CD, infrastructure, deployment |

The names aren't just cosmetic. Each agent gets a persona that shapes how they communicate and approach problems. Geordi is precise and thorough. Troi is empathetic about user experience. Worf is aggressive about edge cases. It sounds gimmicky until you watch them work — the persona system actually produces meaningfully different approaches to the same problem.

## Giving Your First Task

Here's where it gets real. You type a message to your Squad:

```
Team, build the login page with email/password authentication
```

And then Riker takes over. As the Lead, he doesn't start coding — he *analyzes*. He breaks the task into subtasks, considers dependencies, and fans work out to the team:

```
🎖️ Riker: Breaking down login page task...
   → Troi: Build login form component with email/password fields
   → Geordi: Create authentication API endpoint with JWT
   → Worf: Write integration tests for login flow
   → Picard: Add auth middleware to CI pipeline
```

All four agents start working simultaneously. Troi is creating React components while Geordi is building the Express endpoint while Worf is writing test cases while Picard is updating the pipeline config. This isn't sequential — it's genuinely parallel.

The first time I saw this happen, I just sat there watching the terminal. Four agents, four branches of work, all moving forward at once. The Borg assimilation metaphor isn't accidental — it really does feel like a collective consciousness descending on your codebase.

## Ralph — The Relentless Monitor

Every Squad has a secret member that doesn't show up in the casting table: **Ralph**. Ralph is the monitor — the tireless process that never sleeps, never takes a break, and never stops looking for work to do.

When you say "Ralph, go", here's what happens:

1. Ralph scans your GitHub issues
2. Triages them by labels and priority
3. Assigns them to the right agent based on role
4. Spawns agent sessions to do the work
5. Collects results and updates issues
6. Goes back to step 1

It's a loop, and it's relentless. Ralph doesn't stop until you tell him to stop or there's nothing left to do.

But Ralph isn't just one thing — he operates at three layers:

- **In-session loop**: The basic scan-triage-assign cycle running in your current Copilot session
- **`squad watch`**: A local daemon that persists across sessions, surviving terminal restarts
- **GitHub Actions heartbeat**: A scheduled workflow that runs Ralph in CI, fully unattended — your AI team works while you sleep

The GitHub Actions layer is the one that makes enterprise teams pay attention. You can have Ralph watching your repo 24/7, picking up new issues, assigning them to agents, and creating PRs — all without a human touching the keyboard. I've woken up to merged PRs that I never manually reviewed (though Squad does support required human review, which I'll get to).

## Decisions & Memory

Here's the thing that separates Squad from "just running multiple Copilot sessions": it has a shared brain.

**decisions.md** is the team's collective knowledge base. Every architectural decision, every convention, every "we tried X and it didn't work" gets recorded here. When an agent starts working on a task, it reads decisions.md first. When it makes a significant choice, it writes it back.

This means your team accumulates institutional knowledge. Session 1, Geordi decides to use bcrypt for password hashing. Session 5, Troi is building a password reset form and she already knows bcrypt is the standard because it's in decisions.md.

Each agent also has **history.md** — their individual learning. Geordi's history tracks every API he's built, every database schema decision, every performance optimization. Over time, agents develop genuine expertise in *your specific codebase*.

Then there are **skills** — reusable patterns that agents discover and share. When Geordi figures out your project's error handling pattern, he captures it as a skill. Next time Troi needs to handle errors in a frontend API call, that skill is available to her. Knowledge doesn't just persist — it flows across the team.

The team literally gets smarter session over session. That's not marketing copy — I've watched it happen. By session 10, my Squad was making decisions that would have taken a new human developer weeks to learn about the codebase.

## Human Team Members

This is the feature that made me realize Squad isn't a toy — it's a legitimate engineering workflow tool.

You can add humans to the Squad roster. Real people, with real GitHub handles, assigned to real roles. When work routes to a human team member, Squad doesn't hallucinate their response or skip the step — it **pauses and waits**.

I added myself to the roster as a human member. Now when Riker's Lead review needs my input, Squad pauses and pings me:

```
📌 Waiting on @tamirdresher for architecture review...
   Task: Login API design needs sign-off before implementation
   Status: Pinged on GitHub, awaiting response
```

The AI team continues working on everything else that doesn't depend on that human review. When I respond, Squad picks up the thread and continues.

This is the killer feature for enterprise adoption. It means Squad doesn't replace your team — it augments it. Senior architects can still own critical decisions. Security reviews still go through humans. But the implementation work, the boilerplate, the test scaffolding — that's handled by agents while humans focus on the hard problems.

"📌 Still waiting on Tamir for architecture review." I've seen this message more times than I'd like to admit. But it means the system is working correctly — it respects human authority in the loop.

## Features the Squad Blogs Don't Cover (From a User's Perspective)

Squad has a lot of surface area. Brady's docs and blog posts cover the architecture well — but here are the features I discovered as a practitioner that changed my daily workflow:

### Export/Import

I exported my team from one repo and imported into another. All the decisions and skills came with them. `squad export` packages your team's accumulated knowledge — decisions.md, skills, routing rules — into a portable bundle. `squad import` drops it into a new repo. Instead of repeating three weeks of learning, my new repo's Squad was productive from session one.

### `squad doctor`

Run `squad doctor` and it validates your entire setup — 9 checks covering config files, agent definitions, upstream connections, and more. All green means you're good. Anything wrong gets a clear diagnostic with a fix suggestion. I run it every time I modify the Squad config. It's saved me from "why isn't this working?" debugging sessions more times than I can count.

### Notifications

Squad pings me on Teams when it needs input. I don't have to watch the terminal. When Riker's review needs my sign-off, or Worf finds a test failure that requires a human decision, I get a notification on my phone. I respond in Teams, and Squad picks up the thread. This is what makes "human in the loop" actually practical — you're not chained to your desk watching agent output scroll by.

### OpenTelemetry + Aspire

I can see agent work in an Aspire dashboard. Traces, logs, metrics — full observability into what every agent is doing, how long tasks take, and where bottlenecks form. When Geordi spent 8 minutes on what should have been a 2-minute API endpoint, I could see exactly where the time went in the trace waterfall. This isn't just debugging — it's understanding your AI team's performance characteristics over time.

### Label Taxonomy

Squad's 7-namespace label system (`status:`, `type:`, `priority:`, `squad:`, `go:`, `release:`, `era:`) gives structure to the chaos. Before Squad, my GitHub issues were a flat list with inconsistent labeling. Now every issue has a clear lifecycle (`status:new` → `status:triaged` → `status:in-progress` → `status:done`), a type (`type:feature`, `type:bug`, `type:chore`), and Squad knows exactly how to route it. It's opinionated, and the opinions are right.

### Context Optimization

decisions.md was getting huge. After three weeks of accumulated decisions across multiple features, it had ballooned in token count. Squad auto-prunes it — consolidating redundant decisions, archiving stale ones, keeping the active context lean. I watched it go from 80K tokens down to 33K without losing any important context. My agents got faster because they weren't wading through outdated decisions about features that shipped two weeks ago.

### Remote Control

`squad start --tunnel` exposes your session via a devtunnel URL. Open it on your phone, and you're controlling your AI team from the couch. I built this integration and [wrote about it here](/2026/02/26/squad-remote-control.html). It's become my default way to monitor Squad — kick off work at my desk, check progress from my phone during lunch.

## What's Next

This post covered a single repo with a single Squad team. But here's the question that kept me up at night after the first week:

*What happens when you have 5 repos? Do you copy-paste your Squad config into each one? Do decisions in repo A automatically apply to repo B? What about shared coding standards across your organization?*

In [Part 2: "The Collective — Sharing Knowledge Across Repos"](/2026/03/05/scaling-ai-part2-collective.html), I'll show how Squad's upstream inheritance model turns isolated teams into a connected collective — and why the Borg analogy is even more apt than you think.

Resistance is futile. Your backlog will be assimilated. 🟩⬛
