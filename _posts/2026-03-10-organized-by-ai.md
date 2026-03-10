---
layout: post
title: "Organized by AI — How Squad Changed My Daily Workflow"
date: 2026-03-10
tags: [ai-agents, squad, github-copilot, productivity, star-trek, voyager, workflow]
series: "Scaling AI-Native Software Engineering"
series_part: 0
---

> *"I am not an organized guy. Never have been."*
> — Me, to literally everyone who knows me

I've tried everything. Notion — abandoned after ten days. Microsoft Planner — lasted a week. Outlook Tasks — three days. Various todo apps whose names I can't even remember — a day or two each. I even tried blocking out "planning meetings with myself" on my calendar. I skipped my own meetings.

The pattern was always the same: I'd find a shiny new tool, set it up with enthusiasm, use it religiously for a few days, and then... forget. Not forget the tool existed — forget to *use* it. Every system required me to remember to check it, update it, maintain it. And I just don't have that muscle. I never developed it, and after twenty years of trying, I stopped pretending I would.

Then AI happened. Not the "ask ChatGPT a question" kind of AI — the kind where an AI team works alongside you, remembers things you forgot, picks up tasks you dropped, and nudges you when something needs your attention.

**AI doesn't forget. AI doesn't need willpower. AI just... works.**

This is the story of how [Squad](https://github.com/bradygaster/squad) — an AI agent team framework by [Brady Gaster](https://github.com/bradygaster) — turned me from the least organized engineer I know into someone who has a team of specialists working 24/7, scanning my emails, monitoring tech news, contributing to open-source projects, and even building tools I didn't know I needed.

This is Part 0 of a series about scaling AI-native software engineering. The later parts dive into team composition ([Part 1](/2026/03/04/scaling-ai-part1-first-team.html)), knowledge sharing ([Part 2](/2026/03/05/scaling-ai-part2-collective.html)), and multi-team coordination ([Part 3](/2026/03/06/scaling-ai-part3-streams.html)). This post is the personal story — how I got here, what my daily workflow looks like, and why it works when nothing else did.

---

## What Is Squad?

[Squad](https://github.com/bradygaster/squad) is a framework built by Brady Gaster that turns GitHub Copilot CLI into a coordinated AI team. Instead of one generalist agent, you get a *team* of specialists — each with a defined role, expertise, and personality — working in parallel on your codebase.

Brady used the Star Trek universe for team casting (it's deterministic per repo name, and there are 31+ universes built in). My team on this repo got **Star Trek: Voyager**:

| Role | Agent | Specialty |
|------|-------|-----------|
| 🎖️ Lead | **Picard** | Architecture, task decomposition, delegation |
| 🔧 Infrastructure | **B'Elanna** | Build systems, CI/CD, infrastructure |
| 🛡️ Security | **Worf** | Security reviews, vulnerability scanning, hardening |
| 💻 Code | **Data** | Implementation, refactoring, code quality |
| 📚 Research & Docs | **Seven** | Research, documentation, technical writing |

Plus **Ralph** — the tireless background monitor who never sleeps, scanning for new issues, picking up work, and keeping the pipeline moving.

And yes, there's also **Neelix** — but I'll get to him later. He does something unexpected.

Why Star Trek? Because it's a team we respect. Each character has a distinct specialty. They disagree productively. They have strong opinions but defer to the captain when it matters. It sounds gimmicky until you watch Data refactor your authentication module while Seven researches the latest OAuth best practices and Worf flags a security vulnerability in your dependency tree — all at the same time.

![Squad site](/assets/img/posts/scaling-ai/squad-site.png)
*The Squad framework — turning Copilot CLI into coordinated AI teams*

---

## GitHub Issues as My Todo System

Here's the thing that finally made task management stick for me: **I don't manage tasks. My Squad does.**

I use a [GitHub Project Board](https://github.com/users/tamirdresher_microsoft/projects/1/views/1) as my daily dashboard. Every morning, I open it and see what's in progress, what's waiting for my input, and what's been completed overnight. But I rarely *create* issues manually anymore. Here's how it works:

1. I have a thought — "we should add retry logic to the API client"
2. I tell my Squad agent (which is always running in my CLI): "Hey, we need retry logic on the API client"
3. Picard (Lead) analyzes it, creates a GitHub issue with proper context, labels it, and either assigns it to an agent or puts it in the backlog
4. If it's high priority, Data picks it up immediately and starts working

The issues aren't fire-and-forget tickets. They're **conversations**. My agents comment on issues as they work — explaining decisions, asking for clarification, posting progress. Every issue becomes a living record of *how* a decision was made, not just *what* was decided.

The decisions themselves get stored in `.squad/decisions.md` — a persistent knowledge base that survives across sessions. When Seven makes a decision about documentation format in March, Data still knows about it in June. No decision gets lost in a Slack thread or buried in a meeting recording.

---

## Communication — TLDRs Required

One thing I learned fast: AI agents can be *verbose*. When Seven researches a topic, she can produce pages of analysis. When Data implements a feature, the PR description reads like a novel. I love the thoroughness, but I also need to know what happened in 30 seconds.

So I established a rule: **every communication needs a TLDR.** Every issue comment, every PR, every decision — starts with a bolded summary. If I only read the first line, I should know what happened and whether I need to act.

My Squad also sends me **Teams notifications**. When something needs my attention — a decision that requires human judgment, a PR that's ready for review, a build that failed — I get a ping on Teams. I don't have to watch the terminal. I respond from my phone during lunch, and Squad picks up the thread.

---

## Side Projects Spawned

Here's something I didn't expect: Squad started *creating* projects I didn't plan for.

When I asked for a way to monitor what the agents were doing, they didn't just build a logging feature — they built [**squad-monitor-standalone**](https://github.com/tamirdresher_microsoft/squad-monitor-standalone), a full live dashboard showing agent activity, token usage, and cost tracking. It's now its own open-source repo.

When I asked Seven to research a complex topic, she didn't just write a summary — she created a research repository with structured findings, references, and follow-up questions. The research repos became a pattern: self-contained knowledge bases that persist beyond any single issue or session.

This is what happens when your AI team takes initiative. You give a direction, and they build more than you asked for — not because they're hallucinating scope, but because they see the logical next step and take it.

---

## The Ralph Watch Loop

Ralph is Squad's built-in work monitor. You say "Ralph, go" and he starts scanning GitHub issues, picking up work, and processing the backlog. But in the early days, Ralph needed a push — a continuous loop that kept him running.

I wrote a PowerShell script that runs continuously:

```powershell
while ($true) {
    git pull origin main
    # Start a copilot session with squad context
    squad start --yolo
    # Ralph scans for new issues and starts working
    Start-Sleep -Seconds 300  # Check every 5 minutes
}
```

It's crude. It works. Every five minutes, Ralph wakes up, pulls the latest code, checks for new issues, and starts working on whatever's highest priority.

**But here's the thing**: Squad CLI now has a proper `watch` command (`squad start --watch`) that does this natively — no script needed, built-in loop with proper backoff and error handling. The PowerShell loop was my hacky v1; the `watch` command is the real deal. One of the PRs I contributed upstream ([PR #280](https://github.com/bradygaster/squad/pull/280)) helped wire this up.

---

## Auto-Scanning Emails and Teams

This is where it gets wild. I wanted my Squad to know what was happening in my inbox and Teams channels — not to respond on my behalf, but to surface things I might miss.

Using the **WorkIQ MCP** server (a Microsoft 365 Copilot integration), my agents can query my emails, meetings, and Teams messages. Seven scans my inbox every morning and creates a summary issue: "Here's what came in overnight that might be relevant to our projects."

For Teams, I use **Playwright browser automation** to read channels and threads. It's not pretty — it's a headless browser logging into Teams and scraping messages — but it works. When someone mentions a topic related to our current work, Seven flags it.

The key insight: **I'm not automating responses. I'm automating awareness.** My Squad makes sure nothing falls through the cracks, and I decide what to act on.

---

## Two-Way Teams Communication

Reading Teams is one direction. The other direction — sending messages *to* Teams — uses **webhooks**. When Squad needs my input or wants to share a status update, it posts to a Teams channel via an incoming webhook.

But the really fun part is **Neelix** — the podcaster agent.

### The Podcaster Agent

Neelix takes long-form content — research reports, PR descriptions, decision summaries — and generates **audio summaries**. Think of it as an AI podcast host who reads you the highlights of what your Squad did while you were away.

Why audio? Because I commute. Because I cook dinner. Because sometimes I want to absorb information without staring at a screen. Neelix records summaries as audio files that I can listen to on my phone. It's my personalized tech podcast, generated daily, covering exactly what I care about.

---

## Cross-Repo Contributions

Using Squad didn't just change how I work on my own repos — it changed how I contribute to other projects. My team started contributing back to the Squad repo itself:

- **ADO Platform Adapter** ([PR #191](https://github.com/bradygaster/squad/pull/191)) — Made Squad work with Azure DevOps, not just GitHub
- **CommunicationAdapter** ([PR #263](https://github.com/bradygaster/squad/pull/263)) — Abstracted communication so Squad can talk through different channels
- **SubSquads** ([PR #272](https://github.com/bradygaster/squad/pull/272)) — Renamed and restructured how nested squad teams work
- **Upstream & Watch commands** ([PR #280](https://github.com/bradygaster/squad/pull/280)) — Wired up the watch loop and upstream sync natively in the CLI
- **Test resilience** ([PR #283](https://github.com/bradygaster/squad/pull/283)) — Improved test stability across CI environments
- **Remote Control** — The [squad start --tunnel](/2026/02/26/squad-remote-control.html) feature that lets you control your Squad from your phone

These contributions weren't planned. They emerged from daily use — I'd hit a limitation, my Squad would research a solution, Data would implement it, and we'd submit the PR upstream. The boundary between "using a tool" and "building a tool" dissolved completely.

---

## The Scheduling System

One of the more sophisticated things my Squad built — for itself — is a **scheduling system**. Agent **Kes** manages deferred and scheduled issues.

Need something to happen next Tuesday? Create an issue with a `scheduled:2026-03-15` label. Kes tracks it and surfaces it when the time comes. Need to check on something weekly? Kes handles recurring tasks too.

This is the system that replaced my calendar blocks. I don't schedule meetings with myself anymore — I tell Kes to remind me, and she does. Reliably. Every time. Unlike my Outlook calendar, Kes doesn't let me snooze the reminder into oblivion.

---

## Squad Monitor — What Are They Doing?

When you have multiple agents working in parallel across repos, you need visibility. The [**Squad Monitor**](https://github.com/tamirdresher_microsoft/squad-monitor-standalone) is a live dashboard that shows:

- **Active agents** — who's working on what, right now
- **Token usage** — how many tokens each agent has consumed per session
- **Cost tracking** — estimated cost per task (even though I'm blessed with unlimited tokens at Microsoft, it's good to know)
- **Session history** — what was done, when, and by whom

I even asked the team to open-source the monitor tool. It's on GitHub now. The irony of AI agents building their own monitoring dashboard is not lost on me.

---

## Tech News Scanning

With Squad's internet access and the scheduling system, I set up automated scanning of tech news sources:

- **Hacker News** — top stories relevant to AI, developer tools, .NET
- **Reddit** — r/programming, r/dotnet, r/artificial
- **Dev.to** — trending posts in relevant tags
- **Microsoft blogs** — official announcements, new features, deprecations

Seven scans these sources daily and creates a digest issue: "Here's what's interesting today." If something is directly relevant to our work — a new library, a security advisory, a competitor's approach to a problem we're solving — she flags it with higher priority.

I went from "I should check Hacker News but I'll forget" to "Seven already checked and the one post I need to read is pinned to my project board." This is what I mean by AI handling the stuff my brain refuses to.

---

## GitHub Workflows and Actions

To stitch everything together, I created GitHub workflows and actions — automation that connects Squad's work to the broader CI/CD pipeline:

- Workflows that trigger when Squad creates PRs
- Actions that validate agent-generated code against project standards
- Scheduled workflows that wake up Ralph at specific intervals
- Notification workflows that ping Teams when builds complete or fail

The workflows are the glue. They turn individual agent actions into a cohesive, automated pipeline that runs whether I'm at my desk or asleep.

---

## My Day-to-Day Now

So what does a typical day look like?

I sit in front of my [GitHub Project Board](https://github.com/users/tamirdresher_microsoft/projects/1/views/1) and give instructions to my Squad team. I always have the Squad agent running in my CLI, so I can ask questions, make decisions, or redirect work at any moment. Sometimes the agent decides to open an issue for itself — which is genuinely fun to watch.

The morning routine:
1. Check the project board — see what was done overnight
2. Read Seven's email digest — anything urgent from inbox or Teams?
3. Review PRs that agents opened — usually just the diff and the TLDR
4. Give new instructions — "Data, pick up issue #42" or "Seven, research how Kubernetes handles..."
5. Go about my actual work — meetings, design reviews, architecture decisions

The agents keep working while I'm in meetings. When I come back, there are new PRs, updated issues, and progress on things I started days ago. It genuinely feels like having a brain extension — one that doesn't forget, doesn't get tired, and doesn't need to be motivated.

I never thought I'd say this, but: **I'm organized now.** Not because I developed discipline or willpower. Because I have a team that handles the parts my brain refuses to.

---

## What's Next

The frontier I'm exploring now:

**Cross-Squad orchestration** — I'm working with Brady to figure out how Squads can talk to each other and delegate tasks across teams. Think of it like different teams in your org that sometimes need to collaborate — each with its own expertise, access, and context. One Squad handles infrastructure, another handles the frontend, and a coordinator Squad routes work between them.

**The wife's task system** — okay, don't tell her, but I asked my Squad to build a mechanism where my wife can send me tasks (via a shared list or a simple text) and my Squad starts working on them. Grocery list management, appointment scheduling, home project tracking — all flowing through the same GitHub issue system that runs my engineering work. We'll see how far I can push this. 😄

---

## Honest Reflection

I don't know how far I can take this. Some days it feels like I'm genuinely 10x more productive. Other days, I spend more time correcting agent mistakes than I would have spent doing the task myself.

But here's what I know for sure: my relationship with productivity tools has fundamentally changed. For twenty years, every system required *me* to change — to become more disciplined, more organized, more consistent. AI is the first approach that meets me where I am. It adapts to my chaos instead of demanding I adapt to its structure.

Squad isn't perfect. The agents sometimes go down rabbit holes. Token costs can spike on complex research tasks. The Ralph loop occasionally picks up an issue that should have been left alone. But the trajectory is clear: every week, the system gets a little smarter, a little more autonomous, a little more like the brain extension I always wanted.

I'm organized by AI now. And I never thought I'd say that. 🖖

---

> 📚 **Series: Scaling Your AI Development Team**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/2026/03/10/organized-by-ai.html) ← You are here
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/2026/03/04/scaling-ai-part1-first-team.html)
> - **Part 2**: [The Collective — Organizational Knowledge for AI Teams](/2026/03/05/scaling-ai-part2-collective.html)
> - **Part 3**: [Unimatrix Zero — Scaling Squad with Workstreams](/2026/03/06/scaling-ai-part3-streams.html)
