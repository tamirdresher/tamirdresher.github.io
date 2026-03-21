---
layout: post
title: "Aspire + Squad = ❤️ — When Your App Platform Meets Your AI Team"
date: 2026-03-22
tags: [dotnet-aspire, squad, ai-agents, github-copilot, mcp, developer-experience, orchestration]
---

![Aspire + Squad: A Love Story](/assets/aspire-squad-love/hero.svg)

> *"Two orchestrators, one codebase, zero conflicts."*
> — me, realizing my day job and my side project were secretly dating

I work on .NET Aspire at Microsoft. Specifically, I'm on the infrastructure platform team — the people who make sure Aspire's own services don't catch fire while we're teaching other people how to build distributed systems. It's the kind of job where you spend all day thinking about orchestration, service discovery, observability, and how to make complex systems feel simple.

And at night? I run Squad — an autonomous AI team that writes code, reviews PRs, monitors work queues, and occasionally ships features while I sleep.

Here's the thing I didn't expect: **my day job and my side project turned out to be a perfect match**.

Aspire orchestrates your distributed application. Squad orchestrates your development team. And when you put them together? It's like watching two people finish each other's sentences.

---

## What Aspire Does (If You Haven't Met Yet)

.NET Aspire is Microsoft's framework for building cloud-native distributed applications. The pitch is simple: instead of running seven terminal windows with `dotnet run`, `docker-compose up`, `redis-server`, and three different database connections, you write a single `Program.cs` file that orchestrates everything.

It looks like this:

```csharp
var builder = DistributedApplication.CreateBuilder(args);

var cache = builder.AddRedis("cache");
var postgres = builder.AddPostgres("postgres");
var api = builder.AddProject<Projects.MyApi>("api")
    .WithReference(cache)
    .WithReference(postgres);

builder.AddProject<Projects.MyWebApp>("webapp")
    .WithReference(api);

builder.Build().Run();
```

Hit F5. The entire system starts. Redis spins up. PostgreSQL runs. Your API boots with connection strings already configured. Your web app knows where the API lives. The Aspire Dashboard launches and shows you logs, traces, metrics, and health checks for every single resource in your system.

**It's orchestration for local development.** Instead of asking "is Redis running on the right port?" you just... run the app. Aspire handles the rest.

But here's where it gets interesting for me: Aspire 13+ added **multi-language support** (JavaScript, TypeScript, Python, Go) and — critically — an **MCP Server**.

MCP (Model Context Protocol) is how AI agents talk to tools. And Aspire's MCP server means AI agents can *query your running application*.

---

## What Squad Does (The Quick Version)

Squad is an autonomous AI team framework I built on top of GitHub Copilot. You cast a team of AI agents — each with a personality, charter, and expertise — and they work together on your codebase like a real engineering team.

My squad looks like this:

- **Picard** (Lead) — architecture, task delegation, orchestration
- **Data** (Code Expert) — writes and reviews code in C#, Go, TypeScript
- **Worf** (Security & Cloud) — reviews security, audits infrastructure
- **Seven** (Research & Docs) — writes documentation, researches new tech
- **B'Elanna** (Infrastructure) — manages Kubernetes, Helm, Azure resources
- **Ralph** (Work Monitor) — runs every 5 minutes, triages issues, assigns work

The squad lives in `.squad/` inside your repo. Agents read their charters, make decisions, write code, and collaborate via GitHub issues and PRs. Ralph runs on a loop — checking for new issues, analyzing failures, routing work to the right agent.

If you've read [my earlier posts](/blog/2026/03/11/scaling-ai-part1-first-team), you know the squad's been running my personal repos for months. Code reviews, docs updates, dependency patches, infrastructure fixes — most of it happens without me.

But here's what I realized after adding Aspire's MCP server to my setup: **the squad can now read the application state directly**.

---

## The Love Story Begins

I was debugging a health check failure on a Friday afternoon. One of my Aspire-powered services kept showing "Unhealthy" in the dashboard, but the logs weren't obvious. I was about to dig into the traces when I thought: *what if I just asked Ralph?*

Ralph runs every 5 minutes, scanning for work. He reads GitHub issues, checks CI failures, monitors PR status. But with the Aspire MCP server configured, Ralph also has access to:

- Resource health status (Healthy, Degraded, Unhealthy)
- Logs from every service in the app
- Distributed traces for requests
- Environment variables and configuration
- Endpoint URLs and connection strings

So I opened an issue:

```
Title: API service showing Unhealthy in Aspire Dashboard
Body: Started happening around 3 PM. No obvious errors in GitHub Actions. Investigate.
```

Ten minutes later, Ralph had:

1. Queried the Aspire MCP server for the service's health status
2. Found the failing health check: `/health/ready` returning 503
3. Pulled the logs for that service
4. Identified the root cause: PostgreSQL connection pool exhausted
5. Opened a sub-issue for Data: "Increase max pool size in connection string config"
6. Commented on my original issue with full diagnosis and recommended fix

I didn't write a single line of debugging code. Ralph read the Aspire Dashboard *programmatically* and figured it out.

That's when it clicked. Aspire gives me observability. Squad gives me autonomous response. Together, they close the loop from "something's wrong" to "here's the fix" without me touching the keyboard.

---

## The Architecture (How They Actually Talk)

![How Aspire and Squad Connect](/assets/aspire-squad-love/architecture.svg)

Here's the flow:

1. **Aspire Dashboard** shows the current state of your app (services, health, logs, traces)
2. **Aspire MCP Server** exposes that state to AI agents via the Model Context Protocol
3. **Squad agents** (Ralph, Data, Worf) query the MCP server to understand what's running and what's broken
4. **GitHub Issues** become work items when agents find problems
5. **Agents write code**, open PRs, and the changes get reviewed
6. **Aspire redeploys** (via `dotnet run` or AppHost restart) and the cycle repeats

The squad doesn't just *monitor* the app — it actively responds to what it sees.

---

## What I'm Building With This

Since connecting Squad to Aspire's MCP server, I've started leaning on this pattern for everything:

**Automatic Issue Triage:** When a health check fails in Aspire, Ralph opens an issue with full diagnostic context. Data picks it up, investigates, and either fixes it or escalates to me with analysis attached.

**Proactive Monitoring:** Ralph runs a script every 5 minutes that queries Aspire's MCP server for degraded services. If anything's unhealthy for more than two consecutive checks, he files an issue and tags the relevant agent (Data for code issues, Worf for security, B'Elanna for infrastructure).

**Post-Deployment Validation:** After a PR merges and Aspire restarts the app, Ralph checks that all services come back healthy. If something breaks, he bisects the recent commits and identifies the breaking change. I wake up to "PR #47 caused API service to fail health check — reverting" instead of a broken app.

**Configuration Drift Detection:** Seven periodically compares Aspire's environment variables and connection strings against what's documented in `.squad/knowledge/`. When config drifts, she opens a PR to sync the docs.

**Dependency Monitoring:** Worf uses Aspire's MCP server to list all running containers and their image versions. When a CVE drops that affects one of our base images, he opens an issue with upgrade instructions.

It's not perfect. Sometimes Ralph over-files issues (I've had mornings with 12 notifications for the same root cause). Sometimes the squad mis-diagnoses a problem and goes down a rabbit hole. But the *trajectory* is right. Every week, the squad handles more of the operational stuff that used to eat my evenings.

---

## Why This Combination Works

Here's what makes Aspire + Squad such a natural fit:

**Same Philosophy:** Both are built on "make the complex simple." Aspire doesn't hide your distributed system — it gives you visibility and control. Squad doesn't replace your judgment — it handles the grunt work so you can focus on decisions.

**Complementary Layers:** Aspire orchestrates *what's running*. Squad orchestrates *who's working on what*. One manages runtime, the other manages development. Together, they cover the full lifecycle.

**Observability Meets Autonomy:** Aspire gives you unprecedented visibility into your distributed app. Squad gives you autonomous agents that can act on what they see. The MCP bridge is the secret — it turns logs and metrics into actionable intelligence.

**Multi-Language by Design:** Aspire 13+ supports JavaScript, Python, Go, and .NET as first-class citizens. So does Squad. Whether you're running a TypeScript API or a Go microservice, both frameworks handle it without friction.

**Local-First, Cloud-Ready:** Aspire excels at local development but deploys to production (Kubernetes, Azure Container Apps, etc.). Squad runs on your laptop but scales to distributed work queues on AKS. Both are designed to grow with you.

---

## What's Next

I'm still figuring out how deep this integration can go. Here are the experiments I'm running:

**Auto-Recovery Workflows:** When Aspire reports a service crash, Ralph triggers a pre-defined recovery script (restart, rollback, or escalate to human). The squad becomes the first line of defense.

**Chaos Engineering:** B'Elanna randomly kills a service in the Aspire Dashboard (via MCP command), then monitors how the system recovers. If recovery fails, she files a bug with the trace attached.

**Cost Optimization:** Seven tracks resource usage (CPU, memory, network) via Aspire metrics and periodically audits whether we're over-provisioned. When she finds waste, she opens a PR to adjust resource limits.

**Continuous Learning:** Every time the squad investigates an Aspire health check failure, it logs the diagnosis to `.squad/knowledge/troubleshooting/`. Over time, the squad builds a runbook of known failure modes and fixes.

**Cross-Squad Sharing:** I'm exploring how multiple squads (personal repo, work repo, content projects) can share Aspire MCP insights. Imagine one squad learning how to fix a PostgreSQL connection issue and automatically teaching the other squads the same pattern.

---

## The Honest Version

This isn't production-ready "set it and forget it" automation. The squad makes mistakes. Ralph sometimes mis-diagnoses issues. Data occasionally writes fixes that break other things. The Aspire MCP server is still evolving — not every API surface is exposed yet.

But the *direction* is right. Aspire gives me the observability I need to understand what's happening. Squad gives me the autonomy to act on what I see. And the MCP bridge is the connection that makes the whole thing work.

If you're running .NET Aspire and you're curious about AI-assisted development, or if you're running Squad and want better visibility into your app's runtime state, this is the combo I'd recommend trying.

Two orchestrators. One codebase. Zero conflicts.

---

## Links and Resources

- [.NET Aspire Docs](https://learn.microsoft.com/dotnet/aspire/) — official docs, getting started, samples
- [Aspire MCP Server](https://github.com/dotnet/aspire) — the MCP server lives in the main Aspire repo
- [Squad Framework](https://github.com/microsoft/squad) — open-source autonomous AI team framework
- [My Squad Setup](https://github.com/tamirdresher/tamresearch1) — my personal repo with `.squad/` fully configured
- [Part 1: Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team) — how I set up Squad from scratch
- [Part 5: How an AI Squad Learns to Evolve](/blog/2026/03/18/scaling-ai-part5-evolution) — knowledge compounding and multi-squad coordination

If you're experimenting with Aspire + Squad, I'd love to hear what you find. Tag me on [Twitter/X](https://twitter.com/TamirDresher) or open a discussion in the Squad repo.

And if you work on .NET Aspire and want to talk about what MCP integrations would make this even better? I'm all ears. My DMs are open, my calendar is (mostly) available, and I promise to bring strong opinions and real-world use cases.

---

*Written by Troi, voice-matched to Tamir. If the jokes landed, that's me. If they didn't, blame the human.*
