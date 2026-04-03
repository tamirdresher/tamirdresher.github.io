---
layout: post
title: "The Language Doesn't Matter Anymore — Aspire Polyglot and the AI Team That Actually Runs"
date: 2026-04-15
tags: [aspire, polyglot, ai-agents, squad, github-copilot, python, nodejs, distributed-systems, autonomy, kubernetes, kind, platform-engineering]
series: "Scaling AI-Native Software Engineering"
draft: true
published: false
---

## A Problem I Didn't Know I Had

I've been running Squad — my personal AI engineering team — for a few months now. Picard leads. Data writes code. Worf handles security. Seven does research. Ralph watches the queue 24/7 so I don't have to. It works. It works surprisingly well, actually. I [wrote about it in Part 0](/blog/2026/03/10/organized-by-ai), and the reaction was... not what I expected. A lot of people asked the same follow-up question: *"But what happens when your agents need to run code in Python? Or Node.js? Or something other than C#?"*

The honest answer, until recently, was: nothing good.

Because here's the dirty secret of AI coding agents. They read files. They write files. They comment on PRs. But they don't *run* things. They're stateless by nature — each prompt is a conversation, not a running process. If your agent writes a FastAPI endpoint in Python, it can't spin up a local Python environment to verify it works. If your agent builds a TypeScript service, it can't actually start it, query it, watch its logs, and know that it's healthy.

They're brilliant architects who hand you blueprints and can't check if the building stands up.

And that bothered me. Because the moment you start thinking about an AI team working on real distributed systems — the kind I work on every day at my infrastructure platform team at Microsoft — you realize the language thing is a real constraint. Real systems don't speak one language. They speak many.

---

## Then Aspire Dropped the ".NET"

In November 2025, the team behind .NET Aspire shipped version 13 and made a quiet but massive announcement: they dropped "**.NET**" from the name. It's just **Aspire** now.

That's not a branding decision. That's a statement of intent.

Aspire 13 brought first-class Python support and first-class Node.js/JavaScript support alongside the C# stack it was built on. We're talking real integration — not "throw it in a container and hope for the best." Python virtual environments auto-detected. pip, uv, venv all handled. FastAPI via Uvicorn. Node.js with npm, yarn, or pnpm auto-detection. Hot reload. Debugging. Container builds. Database connection strings exposed in every format a Python or JS developer expects (URI, JDBC, individual properties).

When I first read the release notes, I had that feeling you get when a piece clicks into place that you didn't even know was missing.

Because I suddenly understood: **Aspire isn't just a developer tool for distributed apps. It's the runtime that makes autonomous AI teams actually viable.**

---

## The Gap Between "Agents" and "Running Services"

Let me explain what I mean, because I think a lot of people are still thinking about AI agents the wrong way.

When people talk about AI agents automating software development, they usually imagine something like: agent reads issue → agent writes code → agent opens PR → done. And that's real, and it works, and I [wrote a whole series about it](/blog/2026/03/11/scaling-ai-part1-first-team).

But there's a deeper level of autonomy that nobody talks about: **what if the agents themselves need to be services?**

Think about Ralph, my work monitor. Right now, Ralph is a script that fires every few minutes. It loads context, reads GitHub issues, picks up work. But Ralph could be a continuously running Node.js service with a proper health endpoint, a job queue, and an API that other agents can call. He could have state. He could manage concurrency. He could have a proper retry mechanism that's not just a PowerShell loop in my terminal.

Think about Seven, my research agent. Right now, Seven reads files and writes reports. But Seven could be a Python service with a RAG pipeline — a vector database, document ingestion, semantic search — that Data and Picard can *query* when they need to answer questions about the codebase. Instead of Seven spending half her time re-reading the same docs, she'd have a running service with an index that stays fresh.

Think about Worf, my security agent. Right now, Worf scans code when asked. But Worf could be a continuously running Python analysis service with rules and patterns, watching every file change and streaming findings to whoever needs them.

The agents I have today are brilliant but ephemeral. The agents I want are **persistent services with real state**.

And until Aspire went polyglot, there was no sane way to orchestrate them all together.

---

## The Demo I Wish I Could Build Right Now

Here's what I'm designing. I haven't built all of it yet (some pieces are still weeks away), but the architecture is clear.

Imagine a Squad AppHost — `squad-demo/AppHost/Program.cs` — that looks like this:

```csharp
var builder = DistributedApplication.CreateBuilder(args);

// Shared infrastructure
var postgres = builder.AddPostgres("postgres")
    .WithDataVolume();
var redis = builder.AddRedis("redis");
var qdrant = builder.AddContainer("qdrant", "qdrant/qdrant", "latest")
    .WithHttpEndpoint(targetPort: 6333, name: "http");

// Picard — the C# coordinator
var picard = builder.AddProject<Projects.Picard>("picard")
    .WithReference(postgres)
    .WithReference(redis);

// Seven — Python RAG service
var seven = builder.AddPythonApp("seven", "../agents/seven", "main.py")
    .WithEnvironment("QDRANT_URL", qdrant.GetEndpoint("http"))
    .WithEnvironment("OPENAI_API_KEY", builder.AddParameter("openai-key", secret: true))
    .WithReference(qdrant);

// Ralph — Node.js queue monitor  
var ralph = builder.AddNpmApp("ralph", "../agents/ralph")
    .WithReference(redis)
    .WithReference(postgres);

// Data — C# code analysis service
var data = builder.AddProject<Projects.Data>("data")
    .WithReference(postgres)
    .WithReference(picard);

// Worf — Python security scanner
var worf = builder.AddPythonApp("worf", "../agents/worf", "scanner.py")
    .WithReference(data);

builder.Build().Run();
```

Four languages, one `dotnet run`. One Aspire Dashboard. Every service visible, every log streamable, every trace queryable.

And here's what gets me excited: all of them get **OpenTelemetry for free**. Aspire instruments them automatically. So I can see, from a single dashboard, that Ralph is processing 12 issues per minute, Seven is returning semantic search results in 180ms, Worf flagged two potential SQL injection patterns in the last commit, and Data is sitting at 98% CPU trying to analyze that 40,000-line legacy file (classic Data).

**No custom monitoring setup. No separate observability stack. It's just there.**

---

## What Polyglot Actually Unlocks

Let me be specific about what changes when your agents run in their natural language.

**Python agents become real AI services.** Hugging Face, LangChain, LlamaIndex, PyTorch — all of this is the Python ML/AI ecosystem, and it's unmatched. My Seven agent, doing research and RAG, is dramatically better as a Python FastAPI service with LangChain than as a C# service trying to import everything through HTTP wrappers. The semantic search quality is better. The embedding models are more accessible. The code is half the length.

**Node.js agents get the frontend-backend bridge.** If you're building an AI team that needs to interact with your web applications — scraping, testing, generating UI, validating design systems — Node.js is where Playwright lives natively, where the web ecosystem breathes. Ralph, monitoring issues and webhooks, feels natural as a Node.js service because that's the ecosystem webhooks were designed for.

**C# remains the coordination layer.** Picard and Data stay in C#. The Aspire AppHost itself stays in C#. The service discovery, the dependency injection, the orchestration logic — this is what C# and .NET are exceptional at. You're not abandoning .NET. You're just letting it be what it's best at, while Python and Node.js do what they're best at.

This is how real engineering teams work. You don't write your ML pipeline in Java just because your API gateway happens to be Spring Boot. You use the right tool for the job. Now your AI team can too.

---

## The Observability Magic

Here's the part that surprises people when I explain it: once your agents are Aspire resources, you can *observe them the way you observe any microservice*.

With Aspire's MCP server (or the `aspire` CLI, which I [wrote about recently](/blog/2026/03/22/aspire-squad-love)), any agent in your squad can query any other agent's state. Data needs to know if Seven has already indexed the docs for a repo? She calls `aspire-list_resources` and checks Seven's health status. Ralph detects an unhealthy Worf service and automatically creates a GitHub issue. Picard sees that Seven's P95 latency spiked to 4 seconds and routes research tasks to a fallback path.

The agents aren't just running in parallel — they're **aware of each other's operational state**. That's not possible when they're just stateless prompts. That's only possible when they're running services that Aspire can observe.

The Aspire Dashboard becomes the control plane for both your distributed application *and* your AI team. Two birds, one beautiful dashboard.

---

## Setting It Up (The `aspire agent init` Shortcut)

The practical thing I want to call out: Aspire 13.2 shipped a command that makes all of this embarrassingly easy to start.

```bash
cd your-project
aspire agent init
```

This command auto-detects your agent environment — VS Code with Copilot, Copilot CLI, Claude Code — and generates the right config file plus a skill file that teaches your agent all the Aspire CLI commands. For Copilot CLI (which is what I run), it creates `~/.copilot/mcp-config.json` automatically.

Then to add a Python agent to an existing Aspire app:

```bash
aspire add python-app --name seven --project-path ../agents/seven
```

Aspire sets up the venv, writes the AppHost integration code, wires up the health endpoints. You write the Python service itself.

For Node.js:

```bash
aspire add npm-app --name ralph --project-path ../agents/ralph
```

You don't have to figure out how to get Node.js service discovery working with Aspire's environment variables. The `AddNpmApp` extension handles it. Your Node.js service just reads `process.env.ConnectionStrings__redis` and it connects. Done.

---

## The Part That's Still Hard

I want to be honest here, because I've learned to be suspicious of blog posts that make everything sound easy.

**Writing agents that behave well as long-running services is harder than writing agents as stateless prompts.**

When Ralph is a stateless script, a crash means nothing — you just run it again. When Ralph is a Node.js service with a queue and state in Redis, a crash means you need proper error handling, retry logic, dead-letter queues, and someone (Aspire, in this case) to restart him. The operational complexity goes up.

**Language boundaries mean communication overhead.** When Picard (C#) needs to ask Seven (Python) something, it's an HTTP call. That's fine. But you need contracts — OpenAPI, gRPC, whatever you choose — and you need both sides to agree. Stateless agent prompts don't have this problem because there are no sides. Persistent services do.

**The Python ML ecosystem and the C# enterprise ecosystem want different things from their infrastructure.** Python services expect environment variables for configuration. C# services love DI containers and strongly-typed config. Aspire bridges this reasonably well, but there are rough edges, especially when you start mixing secrets management across the language boundary.

None of this is a reason not to do it. It's just a reason to build it incrementally — start with the agents that benefit most from persistence (Ralph and Seven, in my case), prove the pattern, then expand.

---

## Why This Is the Actual Inflection Point

I've been building with AI agents long enough to have opinions about what's real and what's hype. The hype is "AI will replace developers." The reality is "AI is the best force multiplier developers have ever had."

But even within the "real" category, there's been a ceiling. AI coding agents are genuinely good at reading and writing code within a context window. They're less good at operating continuously, maintaining state, and making decisions across long time horizons.

Aspire's polyglot support cracks that ceiling.

When your Squad agents are real services with health checks and telemetry, they stop being consultants you summon and start being colleagues who are always at their desks. Ralph isn't "the monitor agent you run before going to bed" — he's a service that runs whether you're there or not, observing the system, catching regressions, filing issues, and handling the 80% of work that doesn't need your input.

Seven isn't "the agent I ask to do research" — she's a knowledge service with a live index of everything the team has learned, available to every other agent via a simple API call.

That's the AI team I actually want. Not a collection of prompts I have to invoke. A running system that works.

---

## Aspire 13.2 and the Kind Resource: Kubernetes-in-Docker as an Aspire Primitive

Since I drafted the sections above, Aspire 13.2 shipped — and alongside features like the TypeScript AppHost preview, there's something I've been quietly building with [Andrey Noskov](https://github.com/andrey-noskov) that I think changes who Aspire is *for*.

We've been creating a **Kind resource** for Aspire. [Kind](https://kind.sigs.k8s.io/) — Kubernetes IN Docker — is the tool that lets you spin up a full, conformant Kubernetes cluster inside Docker containers on your local machine. No cloud provider. No VM. Just Docker and a real K8s API server.

Our integration, `CommunityToolkit.Aspire.Hosting.Kind`, makes a Kind cluster a first-class Aspire resource. You add it to your AppHost with `AddKindCluster()`, and Aspire manages the entire lifecycle — creating the cluster on startup, health-checking it, wiring kubeconfig into dependent services, and optionally tearing it down when the AppHost stops.

Here's what it looks like:

```csharp
var builder = DistributedApplication.CreateBuilder(args);

// A local Kind cluster — Kubernetes in Docker, managed by Aspire
var k8s = builder.AddKindCluster("dev-cluster")
    .WithKubernetesVersion("v1.32.2")
    .WithWorkerNodes(2)
    .WithClusterLifetime(ClusterLifetime.Persistent);

// Your operator controller — gets KUBECONFIG injected automatically
var controller = builder.AddProject<Projects.TenantController>("tenant-controller")
    .WithReference(k8s);

// A Python CRD validation webhook
var webhook = builder.AddPythonApp("admission-webhook", "../webhooks/admission", "main.py")
    .WithReference(k8s);

builder.Build().Run();
```

One `dotnet run`. The Kind cluster spins up, your operator gets a `KUBECONFIG` environment variable pointing at the cluster, your Python admission webhook connects to the same cluster, and everything shows up in the Aspire Dashboard — cluster health, controller logs, webhook traces, all of it.

The builder API is designed to feel like every other Aspire resource:

- **`WithKubernetesVersion("v1.32.2")`** — pin the cluster to a specific K8s version
- **`WithWorkerNodes(2)`** — add worker nodes for realistic scheduling
- **`WithClusterLifetime(ClusterLifetime.Persistent)`** — keep the cluster across AppHost restarts (great for long dev sessions)
- **`WithReference(k8s)`** — inject `KUBECONFIG` and `K8S_CLUSTER_NAME` into any dependent resource, in any language

Under the hood, we handle the gnarly bits: generating Kind config YAML, creating a container-compatible kubeconfig that replaces `127.0.0.1` with the control-plane container name (so your Docker-hosted services can actually reach the API server), managing the Docker network, pre-flight-checking that the Kind CLI is installed, and running health checks that verify the cluster is genuinely ready — not just "the container started."

### Why This Matters: Platform Engineers Get a Dev Loop

Here's the thing that excites me most about this work. **Aspire's audience just expanded dramatically.**

Until now, Aspire was primarily for application developers — people building microservices, APIs, web apps. The dashboard shows your services, your databases, your message brokers. Great.

But there's an entire class of engineers who build the infrastructure *under* those apps: platform engineers. The people writing Kubernetes operators, custom controllers, admission webhooks, CRD-based platform abstractions. Their daily work is `kubectl apply`, YAML templating, watching reconcile loops in terminal logs, and praying that the controller they just changed doesn't crash-loop when it hits a real cluster.

Their dev loop has been terrible. To test a Kubernetes controller, you've historically needed to:

1. Have a cluster running somewhere (or spin one up manually with `kind create cluster`)
2. Apply your CRDs with `kubectl apply -f`
3. Build and deploy your controller
4. Tail logs with `kubectl logs -f`
5. Manually verify resource states with `kubectl get`
6. Tear everything down and start over when something breaks

No dashboard. No distributed tracing. No health checks. No unified view of what's happening across your controller and the services it manages.

With the Kind Aspire resource, that entire workflow becomes:

1. `dotnet run`
2. Open the Aspire Dashboard
3. See your cluster, your controller, your webhooks — all as observable resources with health status, structured logs, and traces
4. Change code, hot-reload, watch the reconcile loop adapt
5. Use `aspire logs tenant-controller` or the MCP tools to let your AI agents inspect controller state

**The cluster is just another resource in the graph.** It starts, it gets healthy, other things reference it, and Aspire watches all of it. The same pattern that makes distributed app development smooth now makes platform development smooth.

### The AI Team Connection

And here's where it loops back to Squad.

If your agents are building platform tooling — controllers, operators, infrastructure-as-code — they can now run the full stack locally through Aspire. Data can write a controller, run `aspire resources` to see the Kind cluster come up, check health status, inspect the reconcile output. Seven can query the cluster's API server through the injected kubeconfig to verify that CRDs were applied correctly. Worf can scan the admission webhook for security issues and test them against the live cluster.

The Kind resource turns Aspire from "the tool that runs your distributed app" into "the tool that runs your entire platform development environment." And that's exactly the kind of environment that autonomous AI agents need — observable, controllable, and runnable with a single command.

### Where We Are

The Kind hosting integration is being built in the open as part of the [Aspire Community Toolkit](https://github.com/andrey-noskov/aspire-kind). Andrey and I have been collaborating on the implementation — he's handling the YAML config generation and test infrastructure, I've been working on the lifecycle hooks, async patterns, and the docs. It's not shipped to NuGet yet, but the core is working: cluster creation, health checks, kubeconfig injection, worker node support, persistent cluster lifetime, and Docker network integration.

If you're a platform engineer who's been jealous of how smooth the app-developer experience is with Aspire — this is being built for you. And if you want to contribute, the [feature branch](https://github.com/andrey-noskov/aspire-kind/tree/feature/kind-hosting) is where the action is.

---

## Getting Started

If you want to experiment with this, here's the actual starting point:

**1. Install Aspire 13+ and add polyglot support:**
```bash
dotnet workload install aspire
aspire --version  # Should show 13.x
```

**2. Create a new polyglot AppHost:**
```bash
dotnet new aspire-apphost -o squad-demo
cd squad-demo
aspire agent init  # Auto-configures Copilot integration
```

**3. Add your first Python agent:**
```bash
mkdir ../agents/seven && cd ../agents/seven
# Create your FastAPI service: main.py, requirements.txt
cd ../../squad-demo/AppHost
aspire add python-app --name seven --project-path ../../agents/seven
```

**4. Run everything:**
```bash
dotnet run
# Aspire Dashboard starts at https://localhost:18888
# Python FastAPI service starts automatically
# Health checks, logs, traces — all visible
```

**5. Ask your Copilot agent to query the running system:**
```bash
aspire resources          # See all your squad services
aspire logs seven         # Stream Seven's logs
aspire telemetry traces   # See distributed traces across all agents
```

The full concept for the `squad-polyglot-demo` — with Picard as the C# coordinator, Seven as a Python RAG service, Ralph as Node.js, and Worf as a Python scanner — is something I'm actively building. When it's ready, I'll share the repo. The architecture I described here is the real target. The plumbing Aspire provides is already there.

---

## One More Thing

There's a meta-observation I can't stop thinking about.

Aspire dropped "**.NET**" from its name because it's no longer just a .NET framework. That's the technical fact. But there's a deeper reason it matters for AI teams specifically.

AI agents themselves are language-agnostic. GitHub Copilot agents run JavaScript/TypeScript. Many LLM tools are Python-first. C# is great for enterprise coordination. The best AI agent for a given job is often the one built in the language where the relevant ecosystem is strongest.

A truly autonomous AI team needs infrastructure that matches how AI tooling is actually built — spread across Python, TypeScript, and C#, each doing what it's best at. Aspire's polyglot support isn't incidental to AI teams. It's **designed for** AI teams.

The name change wasn't rebranding. It was a mission statement.

And I, for one, am here for it.

---

## Links

- [Aspire What's New in Version 13](https://aspire.dev/whats-new/aspire-13/) — official polyglot feature docs
- [Aspire CLI Reference](https://aspire.dev/install-aspire-cli/) — `aspire agent init` and all the CLI goodies
- [Aspire Python Support Docs](https://learn.microsoft.com/dotnet/aspire/get-started/add-python-app) — how `AddPythonApp` works
- [Aspire + Squad = ❤️](/blog/2026/03/22/aspire-squad-love) — my previous post on Aspire MCP + Squad agents
- [Scaling AI Agents with Aspire: Port Isolation](/blog/2025/12/16/scaling-ai-agents-with-aspire-isolation) — how I use Aspire with git worktrees
- [Part 0: Organized by AI](/blog/2026/03/10/organized-by-ai) — the Squad series start
- [Squad Framework](https://github.com/microsoft/squad) — open-source, if you want to build your own team
- [My Aspire Workshop](https://github.com/tamirdresher/aspire-workshop) — 3-day hands-on, if you want to go deep on Aspire itself
- [Aspire Community Toolkit — Kind Integration](https://github.com/andrey-noskov/aspire-kind/tree/feature/kind-hosting) — the Kind hosting resource we're building
- [Kind (Kubernetes IN Docker)](https://kind.sigs.k8s.io/) — the upstream Kind project

If you're building something like this — polyglot agents, Squad integration, autonomous services — I genuinely want to hear about it. Find me on [Twitter/X](https://twitter.com/tamirdresher) or [LinkedIn](https://www.linkedin.com/in/tamirdresher).

---

*This post is part of the "Scaling AI-Native Software Engineering" series. Previous: [Part 7: Enterprise State and the Local-First Realization](/blog/2026/03/23/scaling-ai-part7-enterprise-state)*
