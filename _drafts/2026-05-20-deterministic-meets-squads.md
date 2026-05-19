---
layout: post
title: "Make It So — But Let the Computer Handle the Math"
date: 2026-05-20
tags: [durable-task-scheduler, ai-agents, squad, microsoft-agent-framework, aspire, workflows, incident-response, dotnet, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 14
image: /assets/deterministic-meets-squads/aspire-resources-v3.png
---

![Aspire dashboard showing all four resources running: dts, foundry, chat, and squad-agent-framework-demo](/assets/deterministic-meets-squads/aspire-resources-v3.png)

*"A starship's computer does not hesitate. It does not speculate. It computes, precisely, and hands the result to the officers who must decide what to do with it."*

Nobody debates this. The Enterprise's computer doesn't decide whether to lower shields in hostile territory — that's Picard's call. But it calculates the shield power distribution, the precise mass of the anomaly, and the warp trajectory to intercept it in time. Deterministic. Exact. Millisecond-fast. Different tools for fundamentally different kinds of work.

I keep getting the same question from developers building AI-native systems: **where does the line go between what the AI does and what code does?** Not philosophically — practically. When an alert fires and someone has to figure out what's broken, gather data from three sources, loop in a third party, apply a mitigation, and check whether it worked — where exactly does the AI go in that flow, and where does it stay out?

This post answers that question with a real, running demo. Not a toy example — a nine-executor durable workflow, running on a live DTS container via Aspire, with screenshots to prove it.

* * *

## It's Not Science Fiction Anymore — This Is Your On-Call Rotation

Picture the scene. A latency alert fires from your payments service at 02:17. Not a clean "connection refused" — a messy, ambiguous signal. Error rate at 14.3%. p99 latency at 8,240ms. Three overlapping alerts: database connection pool saturation, payment-gateway external latency elevated, orders table lock contention. One enterprise customer with a two-hour SLA, and the clock is already running.

Here's the full on-call workflow that needs to happen:

1. **Read the alert and form a hypothesis.** What kind of problem is this, actually? Database? Network? Auth? Payments? Not always obvious from the raw signal.
2. **Gather the evidence.** Fetch current metrics, look up the customer's tier and SLA, pull recent alert correlation, reach out to the customer for reproduction steps, query the third-party payment gateway status page.
3. **Route to the right specialist.** If the root cause is database connection pool exhaustion, you want database-specific investigation and runbooks. If it's the payment gateway, you want payments-specific context. Auth issues require a completely different mental model.
4. **Apply mitigation.** Run the appropriate runbook for the affected subsystem.
5. **Check whether it worked.** Review all accumulated evidence — triage, metrics, customer comms, subsystem analysis, mitigation result. If the diagnosis is still inconclusive, loop back and gather more data. But not forever.

None of that is exotic. That's on-call work in any service with a meaningful SLA. Some of those steps require judgment over ambiguous information. Some require precise lookups from known sources. Some require communicating outside your own systems. And some require checking your own work.

The question isn't "should I use AI for incident response?" The question is: **which steps earn an LLM call, and which ones are just expensive glorified `if` statements?**

* * *

## The All-AI Trap

The tempting answer is: run the whole flow through a single AI agent. Feed it the alert, the metrics, the customer record, the third-party status, and let it reason about everything.

Beautiful, for about five minutes.

Then you check the bill.

Every step in that flow above has a radically different cost profile. Step 1 — "read the alert and form a hypothesis" — genuinely requires reasoning over a messy description with no predefined answer. That's AI territory. Step 2 — "fetch the customer's SLA tier from the database" — is a row lookup. The answer is `2h` or `4h` or `Best-effort`, it's in the database, and it's always exact. Running it through an LLM burns input tokens, output tokens, model inference time, and a slice of your TPM quota to retrieve something a C# method can return in six milliseconds.

Here's the math. If this workflow runs **10,000 times a day** and you collapse the three deterministic gathering steps (customer lookup, metrics fetch, alert correlation) into plain C# instead of routing them through the AI, you've eliminated **30,000 LLM calls per day**. That's your rate-limit headroom, a non-trivial line item on your inference bill, and between 1.5 and 9 seconds of latency reduction — every single run.

And it gets worse than cost. In Part 13 (agent memory), I noted that the more your agent remembers, the less room it has to think. That same force operates here. Routing everything through one big AI agent fills the context window with data lookups the model never needed to be involved with. You've used up reasoning capacity on retrieval. The actual judgment call — "which subsystem does this point to?" — is buried in noise the model gathered about itself.

There's also the non-determinism problem. "Look up the customer's SLA tier" is not a reasoning problem. Routing it through an LLM introduces the possibility of a wrong answer where the right answer was always deterministic. You've made the system less correct and more expensive simultaneously. And when a regulator asks "why did your system apply this runbook to this customer?" — "the AI decided" is not the answer they're looking for.

Use AI for judgment. Use code for everything else.

* * *

## The Enterprise Runs on Both

Here's the mental model I keep coming back to.

Picard decides whether to engage. The ship's computer calculates whether it's *possible*. Picard evaluates the Cardassian offer of alliance. The computer runs the sensor sweep that tells him whether their weapons are charged. Spock provides the judgment the computer can't — context, ethics, experience. Neither replaces the other. Neither tries.

The pattern is: AI does the judgment call. Code does the data gathering. AI does the judgment call again, but now with curated, pre-gathered evidence instead of raw noise. The composition is deliberate — each tool handles what it's actually good at, and the output of one step becomes a typed, structured input to the next.

That division of labor is the architecture this post is about. It shows up clearly in incident response, but it's the same pattern in compliance review, content moderation, financial risk — anywhere judgment and precise retrieval need to interleave. AI *and* code, composed deliberately. Not AI *or* code.

![Diagram: the AI / deterministic / AI composition — typed data flows between steps](/assets/deterministic-meets-squads/diagram-1-composition-pattern.png)

* * *

## The Real Demo: A Durable Incident-Response Workflow

The [squad-agent-framework-demo](https://github.com/tamirdresher_microsoft/squad-agent-framework-demo) implements this as a complete, runnable incident-response workflow. Nine executors. AI where it earns it. Pure C# where it doesn't. DTS backing every step. Here's the full workflow graph from the source comments:

```
triage
  └──► enrich  ◄────────────── loop-back (NeedsMoreInvestigation && iter < 3)
         └──► externalComms                                          ▲
                ├──► [Database]   databaseSquad ─┐                  │
                ├──► [Network]    networkSquad  ─┤                  │
                ├──► [Auth]       authSquad     ─┼──► mitigate ──► diagnose
                └──► [Payments]   paymentsSquad ─┘
```

AI triage. Deterministic enrichment. Deterministic external comms. Dynamic routing to one of four specialist squads. Deterministic mitigation. AI diagnosis with a capped loop. Let's look at the moments that matter.

### Step 1: AI Triage

An `Executor<TIn, TOut>` is the fundamental unit of a MAF workflow — a class that receives a typed input, does work (AI or deterministic), and returns a typed output. All nine steps in this workflow are plain `Executor<,>` subclasses. No magic, no framework-specific boilerplate beyond the base class.

The `TriageExecutor` is the first one. It reads the raw incident context and asks the AI squad to produce a structured verdict: which subsystem, what severity, an initial hypothesis, and what evidence to gather.

```csharp
// IncidentExample.cs — TriageExecutor
internal sealed class TriageExecutor(AIAgent squad)
    : Executor<IncidentWorkflowContext, IncidentWorkflowContext>("Triage")
{
    public override async ValueTask<IncidentWorkflowContext> HandleAsync(
        IncidentWorkflowContext ctx, IWorkflowContext context, CancellationToken ct = default)
    {
        var response = await DemoRuntime.RunAgentAsync(squad, $"""
            Analyze the following incident report and triage it.
            Title: {ctx.Report.Title}   Region: {ctx.Report.Region}
            Description: {ctx.Report.Description}
            Respond:
            Severity: <Sev1|Sev2|Sev3>
            Subsystem: <Database|Network|Authentication|Payments>
            Hypothesis: <one sentence>
            RequiredEvidence: <comma-separated list>
            """, ct);
        return ParseTriage(ctx, response);
    }
}
```

The AI does what it's good at: reasoning over an ambiguous description with no predefined answer key. The output — `Subsystem`, `Severity`, `Hypothesis`, `RequiredEvidence` — gets stamped onto the shared `IncidentWorkflowContext` record and flows to the next step as typed data.

### Step 2: Deterministic Enrichment (No LLM)

The `EnrichExecutor` runs next. It already has the triage verdict. Now it gathers the facts: customer tier and SLA from your own systems, a metrics window (error rates, p99 latency, top error strings), and correlated recent alerts. Pure C#. Zero LLM involvement. Three parallel async calls.

```csharp
// IncidentExample.cs — EnrichExecutor.HandleAsync (no LLM)
var customerTask = MockCustomerService.GetCustomerAsync(ctx.Report.CustomerId, ct);
var metricsTask  = MockMetricsService.GetMetricsWindowAsync(ctx.Report.Region, ct);
var alertsTask   = MockAlertCorrelationService.GetRecentAlertsAsync(ctx.Report.Region, ct);

await Task.WhenAll(customerTask, metricsTask, alertsTask);
return ctx with { Customer = await customerTask, Metrics = await metricsTask, RecentAlerts = await alertsTask };
```

No model, no tokens, no rate-limit exposure. Deterministic every time. The `Mock*` services simulate real network latency (80ms, 120ms, 60ms respectively) so the DTS timeline looks realistic. In production, each mock becomes a real `HttpClient` call to your customer platform, metrics store, or alert correlation service — the shape of the executor doesn't change.

### Step 3: Conditional Routing — The Routing Table That Thinks

After the external communications step — which reaches out to the customer for reproduction context and queries the third-party payment gateway status page, also pure C# — the workflow has a triage verdict with a populated `Subsystem` field. That field determines which specialist squad handles the case.

```csharp
// IncidentExample.cs — WorkflowBuilder conditional routing
.AddEdge<IncidentWorkflowContext>(externalCommsBinding, databaseBinding,
    ctx => ctx?.Subsystem == "Database")
.AddEdge<IncidentWorkflowContext>(externalCommsBinding, networkBinding,
    ctx => ctx?.Subsystem == "Network")
.AddEdge<IncidentWorkflowContext>(externalCommsBinding, authBinding,
    ctx => ctx?.Subsystem == "Authentication")
.AddEdge<IncidentWorkflowContext>(externalCommsBinding, paymentsBinding,
    ctx => ctx?.Subsystem == "Payments")
```

The edge conditions are deterministic predicates over an AI-derived value. Starfleet routes the away team to the right specialist: the medical team for biological anomalies, engineering for warp-core issues, security for hostile incursions. The routing decision itself is just a C# lambda. The judgment that produced the value being compared — the triage classification — was AI.

This is the composition doing exactly what it should. The AI contributes the classification; code acts on it precisely and predictably. You could write a unit test for the routing logic right now, against any classification the AI might produce.

* * *

## The Loop Without the Death Spiral

After the specialist squad runs and mitigation is applied, the `DiagnoseExecutor` reviews everything — all accumulated triage data, metrics, customer communications, subsystem analysis, and mitigation result — and makes a judgment call: resolved, or does this need another look?

```csharp
// IncidentExample.cs — diagnose loop-back edge
.AddEdge<IncidentWorkflowContext>(diagnoseBinding, enrichBinding,
    ctx => ctx?.DiagnosisStatus == "NeedsMoreInvestigation"
           && ctx.DiagnosisIteration < MaxDiagnosisIterations)
```

`MaxDiagnosisIterations` is `3`. That's it. That's the whole gate.

The AI can propose another investigation cycle — and can even refine the hypothesis for the next enrichment pass, which flows back into the triage context. But it cannot run one if the counter is at cap. The deterministic edge condition enforces it. The AI proposes. Code decides whether the proposal is allowed.

In B'Elanna's real run of this demo, the loop fired all three iterations — which is exactly what you'd want to see from a complex payment-service incident with overlapping database and gateway symptoms. Every iteration was checkpointed. The workflow survived all three passes. DTS knew exactly where each loop iteration stood.

AI agents that retry forever burn money and trust in equal measure. A capped loop is how you let AI iterate without inviting it to talk in circles. The pattern is always the same: AI proposes, deterministic gate caps it.

* * *

## Subsystem Squads — Specialists From Specialized Repos

Each subsystem squad is its own executor with its own charter. The `DatabaseSquadExecutor`, `NetworkSquadExecutor`, `AuthSquadExecutor`, and `PaymentsSquadExecutor` each carry a different system prompt tuned to a different set of failure modes.

```csharp
// SubsystemSquads.cs — DatabaseSquadExecutor charter
private const string Charter =
    """
    You are the Database incident-response squad. Your charter:
    - Investigate connection pool exhaustion, lock contention, slow queries,
      and index fragmentation.
    - Correlate database metrics with application error patterns.
    - Recommend precise, read-only diagnostic steps (no schema changes).
    Be concise: 3–5 sentences, focus on the most likely database root cause.
    """;
```

In the demo, all four squads live in the same project — useful for running and understanding the pattern end to end. But here's where the architecture becomes genuinely interesting at scale.

A database squad doesn't just have different configuration. It has different context, different runbook vocabulary, and a different set of people who maintain it and refine it over years of on-call work. In a real organization, each subsystem squad would live in its **own repository**, with its own Squad routing, its own `decisions.md`, and its own charter tuned to exactly the failure modes that team has accumulated. The HQ workflow routes the case. The specialist repo owns the resolution. (Part 12 covers the spawn-squad pattern that makes this work in production.)

The HQ workflow doesn't know *how* to diagnose a payments problem. It knows how to *route the case* to the squad that does. The routing is a deterministic predicate — `ctx.Subsystem == "Payments"`. Everything that happens after the route is the specialist's domain. Starfleet Command doesn't fix the nacelles. It tells engineering to fix the nacelles, and engineering knows things Starfleet Command doesn't need to.

This is also the answer to "how do you scale this beyond a single team?" You add more specialist squads. Each one lives in the repo that owns that subsystem. The HQ workflow learns one new conditional edge per squad. The routing stays deterministic. The specialist knowledge stays distributed.

* * *

## Durable, Because Reality Crashes

A workflow like this can run for two minutes in a demo. In production it might run for twenty — external comms have real latency, the diagnosis loop fires multiple times, the process might restart mid-run. Without durability, any of that means starting over.

The Aspire AppHost wires the DTS emulator container directly:

```csharp
// AppHost.cs — DTS container + endpoint injection
var dts = builder.AddContainer("dts", "mcr.microsoft.com/dts/dts-emulator", "latest")
    .WithEndpoint(port: 8080, targetPort: 8080, name: "scheduler", scheme: "http")
    .WithEndpoint(port: 8082, targetPort: 8082, name: "dashboard");

builder.AddProject<Projects.Squad_AgentFramework_Demo>("squad-agent-framework-demo")
    .WithEnvironment("DTS_ENDPOINT", dts.GetEndpoint("scheduler"))
    .WaitFor(dts);
```

Two lines of AppHost wiring. The `DTS_ENDPOINT` is injected into the demo project automatically — no manual env var needed. The workflow picks it up, registers with DTS on startup via `ConfigureDurableWorkflows`, and every executor call becomes a checkpointed DTS activity. If the process restarts between step 5 and step 6, DTS replays from the last checkpoint. The AI steps that already completed don't re-run. You pay for them once.

Here's what B'Elanna's real end-to-end run looked like in the DTS dashboard:

![DTS orchestrations view — dafx-incident-response Completed in 1m 57s, 16 activities](/assets/deterministic-meets-squads/dts-dashboard-orchestration.png)

`dafx-incident-response`. Completed. 1 minute 57 seconds. 16 activities. That's the full workflow: triage, three enrichment cycles (the loop fired all the way to the cap), external comms, database-squad analysis, mitigation, and the three diagnosis passes — each one a DTS activity.

![DTS execution timeline — 16 activities across 3 loop iterations, all checkpointed](/assets/deterministic-meets-squads/dts-execution-detail.png)

The timeline makes the loop iterations visible. Each pass through enrich → externalComms → subsystem squad → mitigate → diagnose is its own set of checkpointed activities. If the process had restarted anywhere in that 117 seconds, DTS would have resumed from the last completed activity. No rerun. No data loss. No "oops, the AI triage ran twice and got different subsystem classifications."

The [Durable Task Scheduler post](https://www.tamirdresher.com/blog/2026/04/07/durable-task-scheduler) covers the DTS production story. The Microsoft devblogs post on [Durable Workflows in Microsoft Agent Framework](https://devblogs.microsoft.com/dotnet/durable-workflows-in-microsoft-agent-framework/) covers the executor model, workflow builder, and replay semantics in detail — highly recommend reading it alongside this one for the deep mechanics.

* * *

## One Dashboard to Watch It All

When you run via Aspire AppHost, something nice happens for free. All four resources — `dts`, `foundry`, `chat`, and `squad-agent-framework-demo` — appear in the same dashboard. DTS is running. Foundry is running. The LLM deployment is healthy. Your app is waiting on both before it starts.

![Aspire Resources view — dts, foundry, chat, and squad-agent-framework-demo all Running](/assets/deterministic-meets-squads/aspire-resources-v3.png)

The OTel pipeline in `Program.cs` picks up `OTEL_EXPORTER_OTLP_ENDPOINT` from the Aspire-injected environment and starts sending workflow spans:

```csharp
// Program.cs — OTel SDK registration
using var tracerProvider = !string.IsNullOrWhiteSpace(otlpEndpoint)
    ? Sdk.CreateTracerProviderBuilder()
          .AddSource(IncidentExample.DemoActivitySource.Name)
          .AddOtlpExporter()   // reads OTEL_EXPORTER_OTLP_ENDPOINT from env
          .Build()
    : null;
```

No manual `OTEL_EXPORTER_OTLP_ENDPOINT` needed — Aspire injects it. Workflow spans start flowing to the Traces tab immediately.

![Aspire Traces view — workflow.build OTel trace from the incident-response run](/assets/deterministic-meets-squads/aspire-trace-workflow.png)

Honest note: in this demo the pipeline emits workflow-level spans — the `workflow.build` trace you see above. Per-executor spans, individual timings for each of the nine executors, would need an explicit `ActivitySource.StartActivity` call inside each `HandleAsync`. The pipe is wired and open; pour more granular telemetry into it any time.

Squad itself also has a native Aspire integration. Run `squad aspire` from the CLI and it pulls the Aspire dashboard container and configures the OTLP endpoint automatically — agent spawns, token usage, session metrics, errors, all streamed in real time. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to point the Squad CLI at the same Aspire instance already watching your workflow and everything — MAF workflow spans and Squad agent spans — shows up in the same dashboard under their respective service names. The dual-dashboard story (Aspire for .NET spans, DTS dashboard for task-hub orchestration view) becomes a tri-layer view when you add Squad CLI telemetry on top.

* * *

## Where the Line Actually Goes — A Cheat Sheet

Every step in a workflow needs to either earn its AI call or prove it doesn't need one:

| If you're doing this… | Use this |
|---|---|
| Reading messy evidence and forming a hypothesis | AI Squad |
| Fetching structured data from a known endpoint | Deterministic C# |
| Deciding which specialist team handles this case | Deterministic predicate over AI output |
| Applying a runbook for a known subsystem | Deterministic C# |
| Judging whether mitigation actually worked | AI Squad (with full accumulated context) |
| Deciding whether to loop | AI proposes; deterministic gate caps it |
| Routing to a specialist in a different repo | Conditional edge on AI-derived classification |
| Producing a compliance audit trail | Deterministic at every step |

The pattern scales linearly. Add a new subsystem — add one executor class, one conditional edge, one charter string. Add more enrichment sources — add one async call to the deterministic step. Adjust the loop cap — change one constant. The AI reasoning stays localized to the steps that need it. The deterministic logic stays auditable, testable, and free.

* * *

## The Bottom Line

Here's the question I started with: where does the line go between what the AI does and what code does?

The line goes wherever the nature of the work tells you it belongs. Some work requires judgment over ambiguous, unstructured input — that's AI. Some work requires exact retrieval from known sources — that's code. Some work requires routing a case to the specialist who knows it — that's a deterministic predicate over an AI-derived classification. All of it can be wired together in a durable workflow that checkpoints as it goes, loops as needed, and routes to the right expert when it needs to escalate.

The AI-native ops team of the near future doesn't build one giant all-knowing incident-response agent and pray for the best. It builds a workflow where the right tool handles each step, state is durable across process restarts and loop iterations, and the right squad picks up the right case when it's time to escalate beyond what the general workflow knows. The triage is AI. The evidence gathering is code. The routing is a predicate. The specialist analysis is AI with curated context. The loop cap is a constant. The whole thing is observable in one Aspire dashboard.

The Enterprise doesn't run on AI. It doesn't run on automation. It runs on knowing which one to use, when, and how to wire them together.

Make it so.

* * *

## Want to Dive Deeper?

- **Demo repo:** [squad-agent-framework-demo](https://github.com/tamirdresher_microsoft/squad-agent-framework-demo) — clone it, run `dotnet run --project Squad.AgentFramework.Demo.AppHost`, watch the DTS dashboard at `http://localhost:8082`
- **Durable Task Scheduler:** [the DTS post](https://www.tamirdresher.com/blog/2026/04/07/durable-task-scheduler) — the production story and the war story that started this
- **MAF Durable Workflows deep-dive:** [devblogs.microsoft.com](https://devblogs.microsoft.com/dotnet/durable-workflows-in-microsoft-agent-framework/) — executor model, workflow builder, replay semantics
- **Bulletproof Agents:** [the official MAF + DTS announcement](https://techcommunity.microsoft.com/blog/appsonazureblog/bulletproof-agents-with-the-durable-task-extension-for-microsoft-agent-framework/4467122)
- **Squad Aspire integration:** `squad aspire` — spins up the dashboard and wires OTLP in one command
- **Part 12 — Squads Spawning Squads:** [fan-out patterns](https://www.tamirdresher.com/blog/2026/04/25/scaling-ai-part12-fanout-squads) — how multi-repo squad routing works in production
- **Part 13 — Agent Memory:** [the memory tradeoffs](https://www.tamirdresher.com/blog/2026/05/06/scaling-ai-part13-agent-memory) — why a growing context window is a reasoning budget problem