---
layout: post
title: "Aspire + Squad = ❤️ — Why Your AI Team Needs This Distributed Systems Framework"
date: 2026-03-22
tags: [dotnet-aspire, squad, ai-agents, github-copilot, mcp, developer-experience, orchestration]
---

![Aspire + Squad: A Love Story](/assets/aspire-squad-love/hero.svg)

> *"Aspire makes AI agents' lives simpler, not just human devs' lives."*
> — me, after watching my squad spawn entire distributed systems with a single Program.cs

I've been teaching Aspire for over a year now. I've got eight Aspire repos on GitHub, a full workshop syllabus, and two blog posts about how Aspire simplifies distributed development. I'm a believer.

But here's the thing nobody talks about: **Aspire doesn't just make developers' lives easier. It gives AI agents superpowers**.

My platform team at Microsoft uses Aspire to orchestrate our services. And my Squad — the autonomous AI team I run for my own projects — uses Aspire to understand, test, and debug entire distributed systems. When I connected Squad to Aspire's MCP server, something clicked: the AI agents could finally *see* the whole system, not just individual files.

This post is about why that matters.

---

## The Problem AI Agents Have with Distributed Systems

Here's what happens when an AI agent tries to work on a distributed application the traditional way:

**Human gives task:** "Fix the authentication bug."

**Agent's view:**
- `auth-service/login.ts` — okay, this handles login
- `user-service/profile.ts` — this fetches user data
- `api-gateway/routes.ts` — routing config is here
- `database/schema.sql` — user table structure

**Agent's problem:** Which service is actually broken? Is the login service returning the wrong token? Is the user service rejecting it? Is there a network issue between services? Is the database connection timing out?

The agent sees *files*, not *systems*. It can read code, but it can't observe what's running. When you're debugging a distributed system, that's the difference between guessing and knowing.

---

## Why Aspire Changes Everything

In my [previous Aspire post](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html), I showed how Aspire gives AI agents "the missing isolation layer" for parallel development. But the real superpower isn't isolation — it's **system-level observability**.

### 1. Spawning Entire Systems with Minimal Code

An AI agent can spin up a complete distributed application with this:

```csharp
var builder = DistributedApplication.CreateBuilder(args);

var cache = builder.AddRedis("cache");
var db = builder.AddPostgres("db").AddDatabase("myapp");
var messaging = builder.AddRabbitMQ("messaging");

var backend = builder.AddProject<Projects.Backend>("backend")
    .WithReference(cache)
    .WithReference(db)
    .WithReference(messaging);

var frontend = builder.AddJavaScriptApp("frontend", "../frontend")
    .WithReference(backend);

builder.Build().Run();
```

Hit F5. Redis, PostgreSQL, RabbitMQ, the backend API, and the JavaScript frontend all spin up. Connection strings are configured automatically. Service discovery works. The Aspire Dashboard shows you logs, traces, metrics, and health checks for every resource.

**What this means for an AI agent:** Instead of asking "how do I run this app?" the agent just runs `dotnet run` in the AppHost project. One command. Entire distributed system running.

### 2. Querying the System via MCP

This is where it gets powerful. Aspire has an [MCP (Model Context Protocol) server](https://aspire.dev/dashboard/mcp-server/) that lets AI agents programmatically interact with running applications.

My Squad agents can now:

```
Agent: "Check if all resources are healthy"
→ Uses list_resources MCP tool
→ Gets status: backend (Healthy), cache (Healthy), db (Degraded)

Agent: "Why is the database degraded?"
→ Uses list_console_logs for db resource
→ Reads: "connection pool exhausted after 50 concurrent requests"

Agent: "Show me traces for slow requests"
→ Uses list_traces tool
→ Finds: 12 requests took >5s, all waiting on db connection
```

The agent isn't guessing. It's reading the actual running system.

### 3. Understanding the Full Topology

Here's what changed for me. Before Aspire + MCP, when my squad worked on a distributed app, agents would:
- Read files in isolation
- Make changes based on code patterns
- Hope the changes work when the system runs

After Aspire + MCP, the workflow is:
- Agent starts the AppHost (entire system spins up)
- Agent queries the system state via MCP
- Agent identifies the actual broken component from logs/traces
- Agent makes targeted fixes
- Agent re-runs and validates via MCP

The agent works on the **whole system**, not just individual components. That's the difference.

---

## How Squad Uses Aspire: A Real Example

Let me show you what this looks like in practice. This is from my own repo where Squad runs autonomously.

**Friday afternoon:** One of my services kept showing "Unhealthy" in the Aspire Dashboard. I was about to dig into the traces when I thought: *why not just ask Ralph?*

Ralph is my monitor agent — runs every 5 minutes, scanning for work. With Aspire's MCP server configured, Ralph has access to:
- Resource health status (Healthy, Degraded, Unhealthy)
- Logs from every service
- Distributed traces
- Environment variables and connection strings
- Endpoint URLs

I opened a GitHub issue:

```
Title: API service showing Unhealthy in Aspire Dashboard
Body: Started around 3 PM. Investigate.
```

**Ten minutes later, Ralph had:**

1. Queried Aspire MCP for the service's health status
2. Found the failing health check: `/health/ready` returning 503
3. Pulled the logs for that service via MCP
4. Identified root cause: PostgreSQL connection pool exhausted
5. Opened a sub-issue for Data: "Increase max pool size in connection string config"
6. Commented on my issue with full diagnosis and recommended fix

I didn't write a single debugging command. Ralph read the Aspire Dashboard *programmatically* and figured it out.

**This is what I mean by "Aspire gives AI agents superpowers."** The agent didn't just read code. It observed the running system, diagnosed the issue, and proposed a fix — all autonomously.

---

## The Architecture (How It Actually Works)

![How Aspire and Squad Connect](/assets/aspire-squad-love/architecture.svg)

Here's the flow:

1. **Aspire Dashboard** shows your system state (services, logs, traces, health checks)
2. **Aspire MCP Server** exposes that state via Model Context Protocol
3. **Squad agents** (Ralph, Data, Worf) query the MCP server to understand what's running and what's broken
4. **GitHub Issues** become work items when agents find problems
5. **Agents write code**, open PRs, and the changes get reviewed
6. **Aspire redeploys** (via `dotnet run` or F5) and the cycle repeats

The squad doesn't just monitor the app — it actively responds to what it sees.

---

## What I'm Building With This

Since connecting Squad to Aspire's MCP server, here's what I've been running:

**Automatic Issue Triage:** When a health check fails in Aspire, Ralph opens an issue with full diagnostic context (logs, traces, resource status). Data picks it up, investigates, and either fixes it or escalates to me with analysis.

**Proactive Monitoring:** Ralph runs every 5 minutes, querying Aspire's MCP server for degraded services. If anything's unhealthy for more than two checks, he files an issue and tags the relevant agent.

**Post-Deployment Validation:** After a PR merges and Aspire restarts, Ralph checks that all services come back healthy. If something breaks, he bisects the recent commits and identifies the breaking change. I wake up to "PR #47 caused API service to fail health check — reverting" instead of a broken app.

**Configuration Drift Detection:** Seven periodically compares Aspire's environment variables against what's documented in `.squad/knowledge/`. When config drifts, she opens a PR to sync the docs.

**Dependency Monitoring:** Worf uses Aspire's MCP to list all running containers and their image versions. When a CVE drops that affects our base images, he opens an issue with upgrade instructions.

It's not perfect. Ralph sometimes over-files issues (I've had mornings with 12 notifications for the same root cause). The squad occasionally mis-diagnoses a problem. But the trajectory is right. Every week, the squad handles more of the operational work that used to eat my evenings.

---

## Why This Combination Works

**Same Philosophy:** Aspire is built on "make the complex simple." You don't hide the distributed system — you give developers visibility and control. Squad is built the same way: AI agents handle grunt work so humans focus on decisions.

**Complementary Layers:** Aspire orchestrates *what's running*. Squad orchestrates *who's working on what*. One manages runtime, the other manages development. Together, they cover the full lifecycle.

**Observability Meets Autonomy:** Aspire gives you unprecedented visibility into your distributed app via the Dashboard and MCP. Squad gives you autonomous agents that can act on what they see. The MCP bridge turns logs and metrics into actionable intelligence.

**Multi-Language by Design — The Real Enabler:** This is the insight that changed everything for me. Aspire 13+ supports JavaScript, Python, Go, and C# as first-class citizens (I wrote about [using private npm feeds with Aspire](/2025/11/15/seamless-private-npm-feeds-in-dotnet-aspire.html)). Squad agents work across all those languages too. Before Aspire, an agent could only test one component at a time — the Python AI service OR the C# backend OR the TypeScript frontend. With Aspire orchestrating the whole polyglot stack from one place, agents can test the ENTIRE distributed system. That's the enabler. That's why full AI teams working autonomously becomes possible.

**Local-First, Production-Ready:** Aspire excels at local development (F5 experience) but deploys to production (Kubernetes, Azure Container Apps). Squad runs on your laptop but scales to distributed work queues. Both are designed to grow with you.

---

## Why I'm Betting on This Stack

I've been teaching Aspire workshops for over a year. My course syllabus covers everything from [orchestrating distributed apps to using Aspire with AWS](https://github.com/tamirdresher/aspire-aws-feedback). I've written posts about [npm authentication](/2025/11/15/seamless-private-npm-feeds-in-dotnet-aspire.html) and [port isolation for AI agents](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html).

But this post is different. It's not about *how* to use Aspire — it's about *why* Aspire changes what's possible for AI agents.

When I first connected Squad to Aspire's MCP server, I expected incremental improvements. Agents would read logs faster. Diagnosis would be a bit easier.

What I got was a qualitative shift. The agents stopped being "code readers" and became "system operators." They could spawn entire distributed systems, observe them holistically, diagnose failures across service boundaries, and validate fixes end-to-end.

That's not just a productivity boost. That's a different way of working.

---

## The Honest Version

This isn't production-ready "set it and forget it" automation. Ralph makes mistakes. Data occasionally writes fixes that break other things. The MCP integration is still rough around the edges — not every Aspire API surface is exposed yet, and some queries are slower than I'd like.

But the direction is right. Aspire gives me the observability I need to understand what's happening. Squad gives me the autonomy to act on what I see. And the MCP bridge connects them.

If you're running Aspire and you're curious about AI-assisted development, or if you're running Squad and want better visibility into your app's runtime state, this is the combo I'd recommend trying.

Two orchestrators. One codebase. Zero conflicts.

---

## Links and Resources

- [Aspire Docs](https://learn.microsoft.com/dotnet/aspire/) — official docs, getting started, samples
- [Aspire MCP Server](https://aspire.dev/dashboard/mcp-server/) — how AI agents query Aspire programmatically
- [My Aspire Workshop](https://github.com/tamirdresher/aspire-workshop) — 3-day hands-on course for distributed apps with Aspire
- [Squad Framework](https://github.com/microsoft/squad) — open-source autonomous AI team framework
- [My Squad Setup](https://github.com/tamirdresher/tamresearch1) — my personal repo with `.squad/` fully configured
- [Part 1: Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team) — how I set up Squad from scratch
- [Scaling AI Agents with Aspire: The Missing Isolation Layer](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html) — my previous Aspire + AI agents post (the foundation for this one)
- [Seamless Private NPM Feeds in Aspire](/2025/11/15/seamless-private-npm-feeds-in-dotnet-aspire.html) — handling private packages in Aspire

If you're experimenting with Aspire + Squad, I'd love to hear what you find. Tag me on [Twitter/X](https://twitter.com/TamirDresher) or open a discussion in the Squad repo.

---

*Written by Troi, voice-matched to Tamir. If the jokes landed, that's me. If they didn't, blame the human.*
