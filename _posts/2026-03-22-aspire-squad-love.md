---
layout: post
title: "Aspire + Squad = ❤️ — When Multiple AI Agents Share One Running System"
date: 2026-03-22
tags: [aspire, squad, ai-agents, github-copilot, mcp, polyglot, distributed-systems]
---

![Aspire + Squad: A Love Story](/assets/aspire-squad-love/hero.svg)

> *"Agents can't look at a screen. They need programmatic access to system state. Aspire MCP gives them exactly that."*
> — me, after watching five agents simultaneously query different aspects of the same running AppHost

I've been using Aspire since before it was cool. I wrote about [solving npm authentication headaches](/2025/11/15/seamless-private-npm-feeds-in-dotnet-aspire.html) back in November 2025. I wrote about [port isolation for parallel AI development](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html) in December. I teach Aspire workshops. I have eight Aspire repos on GitHub. I'm a fan.

But here's what I didn't expect: **Aspire was designed to simplify distributed development for humans, but it turns out it's even more useful for AI agents**.

Because humans can look at the Aspire Dashboard — a beautiful web UI showing logs, traces, metrics, and health checks. But AI agents can't look at a screen. They need programmatic access to system state.

Aspire's MCP server gives them exactly that. And Squad's coordinator explicitly detects `aspire_*` tools and passes them to agents. This isn't hypothetical. These are real tools, shipping in Squad right now.

Let me show you what happens when multiple AI agents share one running Aspire AppHost.

---

## The Tools: What Agents Can Actually Do

When you run an Aspire AppHost and connect Squad to the MCP server, agents get access to these tools:

**System-wide visibility:**
- `aspire-list_resources` — see all running services, their state, endpoints, health status
- `aspire-list_apphosts` — list all running AppHost instances (useful when working with [worktrees](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html))

**Observability:**
- `aspire-list_console_logs` — read stdout from any resource (containers, projects, executables)
- `aspire-list_structured_logs` — query structured logs across all resources with filters
- `aspire-list_traces` — see distributed traces spanning multiple services
- `aspire-list_trace_structured_logs` — drill into logs for a specific trace ID

**Operations:**
- `aspire-execute_resource_command` — restart or stop resources
- `aspire-doctor` — diagnose environment issues (Docker, .NET SDK, ports)

**Documentation:**
- `aspire-list_docs` — browse Aspire documentation
- `aspire-search_docs` — search docs by keyword
- `aspire-get_doc` — retrieve full doc pages

These aren't wrappers around the Aspire CLI. They're direct integrations with the Aspire Dashboard's backend APIs. The same observability that humans get via the web UI, agents get programmatically via MCP.

---

## The Scenario: Multiple Agents, One System

Here's what makes this interesting. When a Squad with multiple agents works on a distributed app orchestrated by Aspire, each agent queries different aspects of the same running system.

Let me show you what this looks like in practice.

### Act 1: Data Makes a Code Change

**Data** (backend dev agent) is working on issue #342: "API response times are slow for user profile queries."

He modifies `UserService.cs` to add database connection pooling:

```csharp
services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString, npgsqlOptions =>
        npgsqlOptions.MaxPoolSize(50)  // ← Data's fix
    )
);
```

Data commits the change, opens a PR. So far, this is standard AI agent work.

But here's where Aspire comes in: the AppHost is running. Aspire sees the file change, automatically rebuilds the backend service, and restarts it. Data doesn't have to manually restart anything — Aspire handles it.

### Act 2: Multiple Agents Query the Running System

Now watch what happens. **Four different agents**, each with different roles, all query the same running AppHost to validate the change:

**Worf** (security agent) runs:
```
aspire-list_structured_logs resource="backend" level="error"
```

He's checking: did the connection pool change introduce any auth errors? Any database permission issues? Worf sees clean logs. He comments on the PR: "Security review: no elevated permissions required, connection pooling uses existing credentials. ✅"

**Seven** (research agent) runs:
```
aspire-list_traces resource="backend" 
```

She's checking: did API latency actually improve? Seven queries distributed traces, sees that `/api/users/{id}` requests dropped from 450ms to 85ms. She comments on the PR with a trace ID and the performance delta.

**Ralph** (monitor agent) runs:
```
aspire-list_resources
```

He's watching for unhealthy services. If the backend had crashed on restart, Ralph would see `status: Unhealthy` and immediately create a GitHub issue. But the service is healthy, so Ralph logs the observation and moves on.

**B'Elanna** (infrastructure agent) runs:
```
aspire-list_console_logs resource="backend" tail_lines=50
```

She's checking: any warnings in the startup logs? Any resource contention? B'Elanna sees a warning about database connection timeouts during the first 10 seconds after restart (connection pool warming up), notes it in the PR, and suggests adding health check grace period configuration.

### Act 3: The PR Gets Merged

Data's change gets four different perspectives from four different agents — security, performance, operations, infrastructure — all based on querying the SAME running system via Aspire MCP.

No human looked at the Aspire Dashboard. No human ran `kubectl logs`. No human SSH'd into anything. The agents queried the system programmatically and provided targeted feedback.

**That's the breakthrough.**

---

## Why This Works: Aspire Orchestrates the Whole Polyglot Stack

Here's the enabler: Aspire doesn't just orchestrate .NET services. It orchestrates **C#, TypeScript, Python, and Go** as first-class citizens.

Which means an agent can:
1. Modify a Python ML service (`ml-service/predict.py`)
2. Aspire rebuilds and restarts it automatically
3. Agent queries `aspire-list_traces` to see if predictions now flow correctly through the C# API gateway
4. Agent queries `aspire-list_structured_logs` from the TypeScript frontend to verify UI rendering
5. Agent validates the entire flow across four languages and six services

Before Aspire, an agent could test ONE component. With Aspire orchestrating the whole polyglot stack from one place, agents test the ENTIRE distributed system.

That's why [I wrote](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html) that Aspire gives agents "the missing isolation layer." It's not just isolation — it's **system-wide observability across multiple languages and services**.

---

## How Squad Detects Aspire Tools

This isn't magic. Squad's coordinator (`squad.agent.md`) explicitly looks for MCP tools prefixed with `aspire-*` and routes them to agents based on their roles.

From the Squad source:

```markdown
## Tool Routing Rules

When an MCP tool is available:
- aspire-* tools → route to Data, Worf, Seven, Ralph (system operators)
- azure-devops-* tools → route to Picard, Data, Ralph (work trackers)
- playwright-* tools → route to Data, Seven (UI testers)
```

When an agent loads, it checks which tools are available. If `aspire-list_resources` is present, the agent knows it can query running services. If `aspire-list_traces` is available, the agent knows it can analyze distributed traces.

This is first-class integration. Not a workaround, not a script — Squad was designed to work with Aspire MCP.

---

## The Architecture (How It Actually Works)

![How Aspire and Squad Connect](/assets/aspire-squad-love/architecture.svg)

Here's the flow:

1. **Aspire AppHost** runs your distributed system (C#, Python, TypeScript, Go services)
2. **Aspire Dashboard** collects logs, traces, metrics, health checks
3. **Aspire MCP Server** exposes programmatic access via Model Context Protocol
4. **Squad agents** query the MCP server to understand system state
5. **Agents act** based on what they observe (comment on PRs, create issues, fix bugs)
6. **Aspire rebuilds** when code changes, agents re-query to validate

The key insight: agents don't just read files. They observe the running system, across all services and languages.

---

## What I'm Building With This

Since connecting Squad to Aspire MCP, here's what's running autonomously in my repos:

**Post-Deploy Validation (Ralph):**
After a PR merges, Ralph queries `aspire-list_resources` to verify all services come back healthy. If anything stays degraded for more than two health check cycles, he bisects recent commits and identifies the breaking change.

**Performance Regression Detection (Seven):**
Seven queries `aspire-list_traces` after every backend deployment. If P95 latency increases by >20%, she opens an issue with trace IDs showing the slow requests. Data investigates.

**Security Audit on Config Changes (Worf):**
When connection strings or secrets configuration changes, Worf queries `aspire-list_structured_logs` with filter `level="warning"` to check for authentication failures or permission errors. Catches misconfigurations before they reach production.

**Automatic Issue Triage from Unhealthy Resources (Ralph):**
Ralph runs every 5 minutes, queries `aspire-list_resources`. If a service is unhealthy, he pulls console logs via `aspire-list_console_logs`, extracts the error, searches past issues for similar failures, and either:
- Auto-fixes if it's a known issue (e.g., database connection pool exhausted → increase pool size)
- Creates a new issue with full diagnostic context if it's novel

**Documentation Sync (Seven):**
When Seven updates the docs, she queries `aspire-search_docs` to check if Aspire's official docs have changed. If a new feature was added to Aspire, she opens an issue to update our internal documentation.

---

## What's Next: Ralph as an Aspire Resource

Here's where it gets really interesting. I'm working on making **Ralph itself an Aspire resource** (tracked in issue #1037).

Imagine this: when you run the Aspire AppHost, Ralph shows up in the Aspire Dashboard as a resource with a health endpoint. The dashboard displays:
- Ralph's last run timestamp
- How many issues Ralph has triaged
- Whether Ralph is healthy (connected to GitHub, MCP working, no rate limit errors)

And Squad Monitor becomes an **Aspire Dashboard extension** — a custom UI panel showing:
- Which agents are working on which issues
- Agent-to-agent communication (Data → Worf for security review)
- Work queue status (5 pending, 3 in progress, 12 done)

The Aspire Dashboard becomes the control plane for both your distributed app AND your AI team.

That's the vision.

---

## What's Coming in Aspire 13.2: The Tooling Meets Squad Halfway

I've been playing with the daily Aspire builds ahead of the 13.2 release (yes, I'm brave enough to run daily builds), and there are changes coming that make the Squad integration even more interesting.

### `aspire mcp` Becomes `aspire agent`

The Aspire CLI command was renamed from `aspire mcp` to `aspire agent` in 13.2. This isn't just a naming change — it's a philosophical shift. The tooling is literally called "agent" now, as if Aspire is meeting Squad halfway.

When you run `aspire agent`, you're not just exposing an MCP server. You're explicitly positioning the Aspire Dashboard as something AI agents interact with. The naming makes the intent clear: **Aspire is built for agents, not just humans**.

This matters for Squad because it signals that the Aspire team is thinking about AI-first workflows. The renaming (tracked in [aspire.dev#410](https://github.com/microsoft/aspire.dev/issues/410)) is a declaration: agents are first-class citizens in the Aspire ecosystem.

### `aspire do`: Autonomous Build/Test Pipelines

New in 13.2: `aspire do` is a dependency-tracked, parallelizable pipeline for build/test/deploy. Developers can define custom steps, visualize deployment pipelines, and Aspire handles the orchestration.

Here's why this matters for Squad: **agents can now drive the entire build/test cycle autonomously**.

Imagine this workflow:
1. Data makes a code change
2. Data runs `aspire do build` to build the service
3. Aspire automatically runs dependent steps (restore packages, compile, containerize)
4. Data then runs `aspire do test` to validate
5. Aspire runs integration tests against the full AppHost
6. If tests pass, Data runs `aspire do deploy-dev` to push to the development environment

All of this is dependency-tracked — if the build hasn't changed, `aspire do test` skips re-building. Agents get a declarative pipeline they can invoke without understanding the full build graph.

This is the missing piece. Before `aspire do`, agents could query the running system (via MCP), but they couldn't easily drive the build/test/deploy cycle. Now they can.

### Dashboard Agent Hooks: One-Click Integration

The Aspire Dashboard in 13.2 has direct integration for the agent/MCP, making it possible for AI tools to connect with one click. No more manually configuring MCP proxy scripts or hunting for port numbers — the dashboard exposes the agent endpoint prominently, and tools like Squad can auto-discover it.

This lowers the barrier for agents to connect to Aspire. Instead of requiring developers to read the port isolation post and set up the proxy, Squad can detect the Aspire Dashboard, connect to the agent endpoint, and start querying immediately.

### Even Deeper Polyglot Support

Aspire 13 brought polyglot support (JavaScript, Python, Go as first-class citizens). Aspire 13.2 goes further:
- **Native debugging** for Python and JavaScript projects
- **Containerization out of the box** for all languages
- **Uvicorn for FastAPI** (Python), **Vite for JS frameworks** — framework-specific optimizations
- **Multi-language distributed tracing** that just works

This strengthens the Squad integration because agents working across languages now get even better observability. A Python FastAPI service, a C# backend, and a TypeScript frontend all show up in the same distributed trace — and agents can query the entire flow via `aspire-list_traces`.

### What This Means for the Future

Aspire 13.2 isn't just an incremental update — it's a signal that the Aspire team is thinking about AI agents as core users. The `mcp` → `agent` rename, the `aspire do` pipeline, the dashboard agent hooks — these aren't features added for humans. They're features added because **agents need them**.

And Squad benefits directly. The gap between "agents can query the system" and "agents can build, test, deploy, and monitor the system" is closing fast.

---

## The Honest Version

This isn't production-ready "set it and forget it" automation. Ralph sometimes over-files issues (I've had mornings with 12 notifications for the same root cause because five agents all independently detected the same unhealthy service). The agents occasionally mis-diagnose a problem — they see an error in the logs and assume causation when it's just correlation.

And the Aspire MCP integration is still rough around the edges. Not every API surface is exposed yet. Some queries are slower than I'd like (retrieving 10,000 structured log entries takes ~3 seconds). The tooling is evolving.

But the direction is right. Aspire gives me system-wide observability. Squad gives me autonomous agents that can act on what they see. And the MCP bridge connects them.

If you're running Aspire and you're curious about AI-assisted development, this is the combo I'd recommend trying. The agents go from "code readers" to "system operators," and that's transformative.

---

## Getting Started

**1. Run an Aspire AppHost:**
```bash
cd your-app/AppHost
dotnet run
# Aspire Dashboard starts on https://localhost:18888
# MCP server runs on a dynamic port (check dashboard for URL)
```

**2. Configure Squad to use Aspire MCP:**

In your `.copilot/mcp-config.json`:
```json
{
  "mcpServers": {
    "aspire": {
      "command": "dotnet",
      "args": ["aspire-mcp-proxy.cs"],
      "description": "Aspire Dashboard MCP integration"
    }
  }
}
```

(See my [port isolation post](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html) for the full proxy setup.)

**3. Agents automatically detect aspire-* tools:**

No configuration needed. Squad's coordinator routes `aspire-list_resources`, `aspire-list_traces`, etc. to the right agents based on their roles.

**4. Watch agents query the system:**

Open a GitHub issue, assign it to an agent (e.g., Data), and watch the agent query Aspire for logs, traces, and resource status as it works.

---

## Links and Resources

- [Aspire Documentation](https://learn.microsoft.com/dotnet/aspire/) — official docs
- [Aspire MCP Server](https://aspire.dev/dashboard/mcp-server/) — how the MCP integration works
- [My Aspire Workshop](https://github.com/tamirdresher/aspire-workshop) — 3-day hands-on course
- [Squad Framework](https://github.com/microsoft/squad) — open-source autonomous AI team
- [Scaling AI Agents with Aspire: Port Isolation](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html) — my previous Aspire post (foundation for this one)
- [Seamless Private NPM Feeds in Aspire](/2025/11/15/seamless-private-npm-feeds-in-dotnet-aspire.html) — polyglot support in practice
- [Part 1: Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team) — how I set up Squad

If you're experimenting with Aspire + Squad, I'd love to hear what you find. Tag me on [Twitter/X](https://twitter.com/TamirDresher) or open a discussion in the Squad repo.

---

*Written by Troi, voice-matched to Tamir. If the jokes landed, that's me. If they didn't, blame the human.*
