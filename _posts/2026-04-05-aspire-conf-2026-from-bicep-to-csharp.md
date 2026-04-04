---
layout: post
title: "Aspire Conf 2026: Everything New in 13.2 and How AI Agents Use It"
date: 2026-04-05
tags: [aspire, aspire-conf-2026, book-of-news, microsoft-foundry, typescript, aws, docker-compose, kubernetes, genai, mcp, developer-experience, cloud-native, ai, ai-agents, squad, polyglot, observability]
series: "Scaling AI-Native Software Engineering"
---

Aspire Conf 2026 was the first-ever dedicated Aspire conference. Thirteen sessions. Seven hours. Ten-plus major announcements. One very clear message: Aspire isn't a .NET developer tool anymore — it's the platform for building, observing, and deploying modern distributed applications and AI agents, in any language, to any cloud.

We covered every session. And by "we" I don't mean a team of humans frantically live-tweeting. I mean Squad — an AI team framework running as a GitHub Copilot extension — that watched, digested, fact-checked, and assembled a full conference Book of News while the sessions were still streaming. More on that in a moment.

Here's what shipped, why it matters, and how AI agent teams like Squad are already using it.

---

## The Book of News Story: How an AI Team Covered a Conference

Before diving into the features, let me tell you how this post came to be — because the process itself demonstrates why Aspire matters for AI agents.

We pointed Squad at the Aspire Conf YouTube playlist and said: "Create a Book of News." Here's what happened:

1. **Squad downloaded all 13 session transcripts** from the conference
2. **Troi** (the blogger agent) wrote structured digests for each session, extracting key announcements, demo timecodes, and speaker quotes
3. **Q** (the fact-checker) cross-referenced claims against the actual Aspire 13.2 release notes and GitHub commits — catching two places where session speakers misstated version numbers
4. **Seven** (the research agent) assembled the digests into a styled 102-page HTML document with navigation, branding, and a consistent editorial voice
5. **The PDF was generated** via Edge headless printing, with branding fixes applied programmatically

The result: a professionally formatted conference digest that would have taken a human team days to produce, completed in under 30 minutes.

And here's the meta-punchline — this workflow is *exactly* the kind of distributed, multi-agent coordination that Aspire is built for. AI agents need to pass context between each other (service discovery), you need to see what each agent is doing (observability), and when something fails you need to trace it back to the source (distributed tracing). That's the Aspire value proposition, applied to AI teams instead of microservices.

📥 **[Download the Aspire Conf 2026 Book of News (PDF)](/assets/downloads/Aspire-Conf-2026-Book-of-News.pdf)** — 102 pages covering every session, every announcement, every demo.

---

## Aspire 13.2: The Top 10 Features That Matter

Aspire 13.2 shipped 110+ features and improvements. Here are the ones that fundamentally change what you can build.

---

### 1. TypeScript AppHost — Aspire Without C#

This is the feature that makes Aspire a polyglot platform instead of a .NET tool with polyglot *support*.

You can now write your entire AppHost — the orchestration layer that defines your distributed application — in TypeScript. Not a preview. Not an experiment. Production-ready, with full VS Code debugging, CodeLens gutter decorations showing live resource state, and automatic SDK code generation that keeps TypeScript bindings in sync with every .NET integration.

```typescript
import { createBuilder } from "@aspect/apphost";

const builder = createBuilder();

const redis = builder.addRedis("cache");
const api = builder.addProject("api", "../api")
    .withReference(redis);
const frontend = builder.addViteApp("frontend", "../web")
    .withReference(api)
    .withExternalHttpEndpoints();

builder.build().run();
```

Under the hood, the TypeScript AppHost runs as a guest process communicating with the .NET orchestration host via JSON-RPC. You don't need the .NET SDK installed on your machine. You don't need to know C#. You just need `npm` and the Aspire CLI.

At Aspire Conf, Chris Ays demonstrated Go, Python, JavaScript/Vite, Spring Boot, and C# all running under a single TypeScript AppHost. Josh Goldberg gave a deep dive on TypeScript's type system in the Aspire ecosystem. The message was unmistakable: one AppHost, many languages.

**Why this matters for AI teams:** Most AI agent frameworks live in the JavaScript/Python ecosystem. A TypeScript AppHost means teams building agent systems in Node.js or Deno can adopt Aspire's orchestration and observability without touching C#. When the team dropped ".NET" from Aspire's name, it wasn't rebranding — it was a mission statement. The TypeScript AppHost is the proof. That's the difference between "interesting .NET thing" and "we're actually using this."

---

### 2. Docker Compose Deployment Target — `aspire deploy` to Compose

Docker Compose publishing hit GA. You can now generate a production-ready `docker-compose.yaml` directly from your AppHost via `AddDockerComposeEnvironment()`.

This sounds simple. It's not. Aspire resolves your entire resource dependency graph — services, databases, volumes, network configuration, health checks — and emits a Compose file that actually works. Port mappings, environment variables, service dependencies, volume mounts — all derived from the same AppHost model you use for local development.

```bash
aspire deploy --target docker-compose
```

**Why this matters:** Not every deployment target is Kubernetes or Azure Container Apps. Plenty of teams run Docker Compose in production (or need it for staging environments, CI, or on-prem deployments). Compose GA means Aspire now covers the full deployment spectrum from single-machine Docker to multi-cloud Kubernetes.

---

### 3. AWS Lambda + CDK Integration — Aspire Beyond Azure

The conference's jaw-dropping moment came when Norm Johanson from AWS performed a live, unscripted deployment of an Aspire application to AWS. Not a canned demo — live on stream, with real AWS accounts.

AWS Lambda support is now GA. You can debug Lambda functions locally in Visual Studio with a built-in API Gateway emulator, and Lambda telemetry flows into the Aspire Dashboard with full OpenTelemetry visibility.

The CDK integration (preview) goes further. `builder.AddAWSCDKEnvironment()` maps Aspire resources to CDK constructs — Redis becomes ElastiCache, .NET services become ECS Fargate tasks — and deploys them with `aspire deploy`.

```csharp
var builder = DistributedApplication.CreateBuilder(args);

var lambda = builder.AddAWSLambdaFunction("processor", "../lambda")
    .WithApiGateway();

var queue = builder.AddAWSSQSQueue("tasks");

builder.AddProject<Projects.Api>("api")
    .WithReference(lambda)
    .WithReference(queue);
```

**Why this matters:** "Deploy anywhere" stopped being aspirational marketing copy and became working code at this conference. If your AI agents need to run close to data that lives in AWS, you can now orchestrate that from the same AppHost model. Multi-cloud is real.

---

### 4. CLI Overhaul — Built for Humans *and* Agents

The Aspire CLI got a complete redesign in 13.2, and the design goal was explicitly dual: make it great for developers typing in a terminal, *and* make it great for AI agents driving it programmatically.

**`aspire start --isolated`** — Run your AppHost with randomized ports and isolated user secrets. This is critical for parallel workflows: git worktrees, CI matrix builds, or — and this is the one that matters to us — multiple AI agents running experiments simultaneously without port collisions.

**`aspire describe --follow`** — Real-time resource inspection from the CLI with streaming state changes. AI agents can monitor application health, check resource status, and read environment variables without needing GUI access to the dashboard.

**`aspire wait`** — Block until a resource reaches a target status (`healthy`, `up`, `down`). This is the synchronization primitive that agentic workflows have been missing.

**`aspire doctor`** — Environment health checks covering HTTPS certs, Docker/Podman, .NET SDK, WSL2, and agent configuration. Reduces onboarding to a single diagnostic command.

**`aspire export`** — Capture telemetry, logs, and resource data into shareable zip files. Bug reports become reproducible scenarios.

**`aspire agent init`** — (Renamed from `aspire mcp init`.) Generates MCP configuration and a `SKILL.md` file that teaches AI coding agents what the CLI can do, how to invoke it, and what output to expect. This is the "agents teaching agents" pattern — Aspire bootstraps AI agent integration with a single command.

```bash
# Start isolated instance (no port conflicts)
aspire start --isolated

# AI agent monitors resource health
aspire describe api-service --follow --format json

# Wait for everything to be healthy before running tests
aspire wait api-service --status healthy --timeout 120

# Export diagnostics for bug report
aspire export --output ./diagnostics.zip
```

**Why this matters for AI teams:** The `--isolated` flag alone changes the game. We can now have Picard (the lead agent) spin up an Aspire instance to test a hypothesis, while Data (the code agent) has a separate instance running for a completely different experiment. No coordination needed. No port conflicts. Just parallel execution.

---

### 5. GenAI Telemetry — See What Your AI Is Actually Doing

The Aspire Dashboard now visualizes GenAI spans as first-class telemetry. System prompts, tool definitions, model names, token costs, streaming chunk counts — all visible in the same trace view you use for database queries and HTTP calls.

This means when your AI agent makes a call to GPT-4o, you see:

- The system prompt that was sent
- The tool definitions that were registered
- The model's response (truncated for large payloads, expandable on click)
- Token counts and estimated costs
- Latency breakdown between time-to-first-token and total generation time

The GenAI Visualizer improvements in 13.2 add better schema handling, non-ASCII support (critical for multilingual prompts), and direct navigation from tool call spans to tool definition spans.

**Why this matters:** Debugging AI agent behavior without seeing what prompts were sent and what tools were called is like debugging a web app without seeing HTTP requests. GenAI telemetry makes agent behavior transparent and debuggable with the same tooling developers already know.

---

### 6. MCP Server — AI Agents Querying Live Traces

The Model Context Protocol (MCP) integration lets AI coding agents query your running Aspire application's live traces, structured logs, and resource state programmatically.

The `WithMcpServer()` app model extension declares MCP server endpoints in your AppHost. The VS Code extension can auto-register the Aspire MCP server for AI agents with one click. And the telemetry HTTP API (`/api/telemetry/{resources,spans,logs,traces}`) provides RESTful access with real-time streaming.

At the conference, Pierce and Mike demonstrated an AI agent in VS Code using MCP to read live traces from a running Aspire application, identify a performance regression, and suggest a fix — all grounded in real observability data rather than guessing from source code alone.

Luke Parker then showed how OpenCode uses Aspire as the shared observability surface for both human developers and AI agents. Same dashboard, same traces, same data — but AI agents can consume it programmatically while humans look at the same information visually.

**Why this matters for Squad:** We're already using the Aspire MCP server in our development workflow. When Data (the code agent) is investigating a bug, it can query live traces from the running application instead of guessing from static code analysis. The agent goes from "I think this endpoint is slow" to "this endpoint took 3.2 seconds because the database query at span `db-query-7` returned 14,000 rows." That's the difference between a helpful suggestion and a precise diagnosis.

---

### 7. Microsoft Foundry Hosting — From Bicep to C#

This was the original focus of this post, and it's still a major story. Aspire 13.2 ships first-class support for Microsoft Foundry via `Aspire.Hosting.Foundry`.

The cognitive gap between application code and infrastructure disappears. Your AI infrastructure — Foundry hubs, projects, model deployments, hosted agents — lives in the same `AppHost/Program.cs` alongside your databases, message buses, and microservices.

```csharp
var builder = DistributedApplication.CreateBuilder(args);

// Declare a Microsoft Foundry hub + project
var foundry = builder.AddFoundry("foundry");

// Add model deployments — no portal clicking, no Bicep, no ARM
var chat = foundry.AddDeployment("chat", FoundryModel.OpenAI.Gpt4o);
var embeddings = foundry.AddDeployment("embeddings", FoundryModel.OpenAI.TextEmbeddingAda002);

// Your application service gets connection details injected automatically
var aiService = builder.AddProject<Projects.MyAiService>("ai-service")
    .WithReference(chat)
    .WithReference(embeddings)
    .WaitFor(chat);

builder.Build().Run();
```

Aspire handles the provisioning graph automatically. Want to swap models? Change one line. Aspire detects the infrastructure drift and reprovisioning happens on the next run. The strongly-typed `FoundryModel` enum gives you IntelliSense autocomplete over all available models and a compile error if you reference one that doesn't exist.

The `PublishAsHostedAgent()` extension method takes this further — deploy Aspire-coordinated agents directly to the managed Foundry runtime. And `AddAndPublishPromptAgent()` lets you publish prompt-based agents from your AppHost definition.

For teams with existing Bicep templates, `AddBicepTemplate()` lets you reference them from your AppHost and migrate incrementally. Most teams report completing the migration in a single afternoon.

---

### 8. VNet Support for Azure Container Apps — Enterprise Networking in C#

The `Aspire.Hosting.Azure.Network` package brings Azure Virtual Network configuration into the AppHost. Define VNets, subnets, Network Security Groups, NAT gateways, and private endpoints — all in C#.

```csharp
var vnet = builder.AddAzureVirtualNetwork("app-vnet");
var subnet = vnet.AddSubnet("services-subnet");

var privateEndpoint = builder.AddPrivateEndpoint("db-endpoint")
    .WithSubnet(subnet);

var cosmos = builder.AddAzureCosmosDB("cosmos")
    .WithPrivateEndpoint(privateEndpoint);
```

The shorthand methods `AllowInbound()`, `DenyInbound()`, `AllowOutbound()`, `DenyOutbound()` make NSG rules readable. `AddPrivateEndpoint()` automatically creates private DNS zones and disables public access.

At the conference, this was called out as the feature that unblocks enterprise adoption. Regulated industries that required hand-crafted Bicep for their networking configuration can now define it in the same AppHost as everything else.

**Why this matters:** AI applications handling sensitive data need network isolation. Defining VNet configuration in the AppHost means your security posture is version-controlled, reviewable in pull requests, and reproducible across environments. No more portal clicking for private endpoints.

---

### 9. Kubernetes Helm Chart Generation — One Command to K8s

Aspire can now generate Helm charts from your AppHost definition. This was one of the conference's jaw-dropping demo moments — Mitch Denny live-deployed an Aspire application to Kubernetes on a Raspberry Pi using generated Helm charts.

The Kubernetes YAML publishing also received significant fixes in 13.2. `ExcludeFromManifest` handling is more reliable, and the generated manifests require less manual fixup.

Combined with Docker Compose GA, Aspire now has three production deployment targets: Azure Container Apps (via `azd`), Docker Compose, and Kubernetes via Helm. The same AppHost definition drives all three.

**Why this matters for AI teams:** If you're running AI agents on Kubernetes (and at scale, you probably are), Helm chart generation from your AppHost means the orchestration model you develop against locally is the same model that deploys to production. No translation layer. No "works on my machine" followed by a week of Helm chart debugging.

---

### 10. Standalone Dashboard — Works With Any OTel App

The Aspire Dashboard can now run as a standalone Docker container that works with *any* OpenTelemetry-compatible application, in *any* language, without an AppHost.

```bash
docker run -p 18888:18888 -p 4317:4317 \
  mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

Point your application's OTLP exporter at `http://localhost:4317`, and you get the full Aspire Dashboard experience — structured logs, distributed traces, resource state — for your Go, Python, Java, or Node.js services. No .NET required.

The dashboard improvements in 13.2 include telemetry export/import (share diagnostic sessions as zip files), a telemetry HTTP API for programmatic access, 12h/24h time format settings, aggregate replica states, and persistent UI state across sessions.

**Why this matters:** The Aspire Dashboard is genuinely one of the best local observability tools available. Making it standalone means any team can adopt it, even if they have zero interest in the rest of the Aspire ecosystem. For AI agent teams specifically, the telemetry HTTP API means agents can query dashboard data programmatically — same data, machine-readable format.

---

## Why This Matters for AI Agent Teams

The conference made a compelling case that AI agents and Aspire are converging. Here's the thesis, backed by what we saw.

But first, the problem that makes all of this urgent.

AI coding agents today are brilliant at reading files, writing code, and opening PRs. But they don't *run* things. They're stateless by nature — each prompt is a conversation, not a running process. Your agent can write a FastAPI endpoint but can't spin up a local Python environment to verify it works. They're brilliant architects who hand you blueprints and can't check if the building stands up.

Aspire's polyglot support cracks that ceiling. When your agents become real services instead of stateless prompts, everything changes. Ralph, the work monitor, stops being a script you fire every few minutes and becomes a continuously running Node.js service with a job queue, a health endpoint, and an API other agents can call. Seven, the research agent, becomes a Python service with a RAG pipeline that other agents query via API instead of re-reading the same docs every time. Each agent runs in the language where its ecosystem is strongest — Python for ML/AI (Hugging Face, LangChain, PyTorch), Node.js for webhooks and web tooling, C# for coordination and orchestration:

```csharp
// Squad polyglot AppHost — four languages, one dotnet run
var builder = DistributedApplication.CreateBuilder(args);

var redis = builder.AddRedis("redis");
var postgres = builder.AddPostgres("postgres");

var picard = builder.AddProject<Projects.Picard>("picard")
    .WithReference(postgres).WithReference(redis);

var seven = builder.AddPythonApp("seven", "../agents/seven", "main.py")
    .WithReference(postgres);

var ralph = builder.AddNpmApp("ralph", "../agents/ralph")
    .WithReference(redis).WithReference(postgres);

builder.Build().Run();
```

The agents stop being consultants you summon and start being colleagues who are always at their desks. And once they're Aspire resources, the platform kicks in:

**Aspire gives agents the observability backbone they need.** When Squad's Data agent investigates a failing service, it doesn't guess from source code. It reads live traces from the Aspire MCP server. When Picard routes work to specialists, the dashboard shows which agents are processing what. When something fails, the distributed trace tells you exactly where and why.

**`aspire start --isolated` enables parallel agent experiments.** Before isolated mode, running two AppHost instances meant port conflicts. Now each instance gets randomized ports and isolated configuration. Two agents, two experiments, zero coordination overhead.

**Skill files teach agents how to use the CLI.** The `aspire agent init` command generates a `SKILL.md` that serves as machine-readable documentation. AI agents learn what commands are available, what flags they accept, and what output to parse. This is agents bootstrapping other agents.

**The conference itself proved the thesis.** The Windows 365 team showed a pre-recorded video of AI agents orchestrating automated fixes across 35+ enterprise repositories, with a centralized rollout dashboard. They used Aspire as the observability layer. At enterprise scale. In production.

Aspire is becoming the operating system for distributed AI agent systems — the infrastructure that makes multi-agent coordination observable, debuggable, and production-ready.

---

## What's Next

The Aspire community is thriving — 600+ pull requests, 170+ contributors, and 2,400+ community issues. The community session closed the conference by celebrating this growth and painting a welcoming picture for the next wave of contributors.

Here's what to do from here:

1. **📥 [Download the Aspire Conf 2026 Book of News](/assets/downloads/Aspire-Conf-2026-Book-of-News.pdf)** — 102 pages, every session, every announcement, every demo. Made by an AI team. About the tool that makes AI teams work.

2. **Try Aspire 13.2** — Install the CLI, run `aspire new` to get a polyglot starter template, and experience the dashboard. Fifteen minutes is all it takes to see why this is different.

   ```bash
   curl -sSL https://aspire.dev/install.sh | bash
   aspire new aspire-py-starter
   aspire run
   ```

3. **Check out Squad** — The AI team framework that created the Book of News lives at [github.com/tamirdresher/squad](https://github.com/tamirdresher/squad). The routing table, agent personas, the decisions.md pattern — it's all open source.

4. **Join the conversation** — The [Aspire Discord](https://aka.ms/aspire-discord) community is one of the most active in the .NET ecosystem.

Aspire Conf 2026 made one thing crystal clear: Aspire has crossed the chasm from "interesting developer tool" to "the platform for modern distributed applications, agents, and deployments."

The first dedicated Aspire conference won't be the last.

## What to Look Forward To

Aspire 13.2 was described as the "biggest ever release" — but the roadmap discussion makes clear that the team views this as a foundation, not a finish line. Here's what's actively coming next.

**First-class testing experience** is the biggest gap the team has publicly acknowledged. The `aspire wait` command shipped in 13.2 as a useful building block for CI scripts, but the vision goes much further: a live dashboard during test runs, capture-and-replay for reproducing production issues locally, partial AppHost execution for component-level testing, and request redirection and mocking at the infrastructure layer. If you've ever wanted the same observability you get in production to be present while your tests run, that's exactly where this is heading.

**Run Subsets** is the other major local development gap. Detached mode and `aspire resource start/stop` give you more manual control, but the goal is a first-class "run only these resources" experience — declare which slice of your application you want, and Aspire handles the rest. For large projects with 20+ resources, this will be transformational.

**TypeScript AppHost is moving toward GA.** It's in preview today and the team is actively expanding integration coverage, improving error messages, and tuning performance. More polyglot export targets are coming too: Go, Java, and Rust code generation are on the roadmap, which means the 30+ integrations already exported to TypeScript will eventually reach the entire language spectrum.

**Authentication integrations** — Entra ID, Keycloak, and Azure Easy Auth — are in active development. If setting up auth in your Aspire AppHost still feels like a gap, that's the next area getting first-class treatment.

**Package manager distribution via Homebrew and WinGet** is nearly done and will land very soon, making `aspire` a one-command install for most developers.

**Debugging in containers** remains one of the most-requested features on the tracker. It requires coordinated work across both Visual Studio and VS Code, and it's actively in progress.

And for teams with distributed codebases: **multi-repo support** is on the radar, with the team acknowledging it as a consistent enterprise ask.

The Aspire community — 600+ contributors, 2,400+ community issues filed — is as engaged as ever. The [Aspire GitHub discussions](https://github.com/microsoft/aspire/discussions) are the best place to follow the roadmap, flag priorities, and shape what gets built next.

Aspire 13.2 wasn't the peak. It was the launchpad.

---

### Resources

- [What's new in Aspire 13.2](https://aspire.dev/whats-new/aspire-13-2/)
- [Aspire CLI documentation](https://aspire.dev/cli/)
- [TypeScript AppHost guide](https://aspire.dev/docs/apphost/typescript/)
- [Microsoft Foundry hosting integration](https://aspire.dev/integrations/cloud/azure/azure-ai-foundry/azure-ai-foundry-host/)
- [AWS Lambda integration](https://aspire.dev/integrations/cloud/aws/aws-lambda/)
- [Docker Compose publishing](https://aspire.dev/docs/deployment/docker-compose/)
- [Standalone Aspire Dashboard](https://aspire.dev/docs/dashboard/standalone/)
- [Aspire MCP server](https://aspire.dev/docs/ai/mcp-server/)
- [NuGet: Aspire.Hosting.Foundry](https://www.nuget.org/packages/Aspire.Hosting.Foundry)
- [Aspire Conf 2026 YouTube playlist](https://www.youtube.com/playlist?list=PLdo4fOcmZ0oUfBmjEGMNKdR4VTjxthgAO)
- [Aspire GitHub repository](https://github.com/dotnet/aspire)
