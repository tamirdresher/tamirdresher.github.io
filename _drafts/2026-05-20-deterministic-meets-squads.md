---
layout: post
title: "When Boring Meets Brilliant — Combining Deterministic Workflows with AI Squads"
date: 2026-05-20
tags: [durable-task-scheduler, ai-agents, squad, microsoft-agent-framework, aspire, workflows, distributed-systems, dotnet, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 14
image: /assets/deterministic-meets-squads/aspire-dashboard-squad.png
---

![The Aspire dashboard showing Squad, Foundry, and the demo running healthy side-by-side](/assets/deterministic-meets-squads/aspire-dashboard-squad.png)

I wrote a post about the Durable Task Scheduler three months ago. Stick with me — because I left something out.

It wasn't intentional. I was so deep in the history of it (2017 Azure Durable Functions, then years at Payoneer debugging Netflix Conductor at scale, then the slow realization that the technology I'd written about in 2017 had quietly grown up) that by the time I got to the end, I had one paragraph about AI agents. One paragraph. For what is honestly the most interesting part.

The paragraph said something like: "and by the way, the Microsoft Agent Framework can use DTS as a backend for durable agent workflows." I meant it as a teaser. What I should have written is: this is *the* unlock. This is why all of it matters.

So here's the follow-up I owe you.

* * *

## Two Camps, One Problem

Here's the tension I kept bumping into over the last year.

On one side: **deterministic workflows**. Durable Task Scheduler, Conductor, Temporal, Step Functions — take your pick. Same input, same output. Every time. You get checkpointing, idempotency, fan-out, human-in-the-loop pauses, observability dashboards, and horizontal scale across services. You know exactly what ran, when it ran, and what it returned. If it crashes, it picks up where it left off. It's boring in the best possible way. I spent years at Payoneer building on top of Conductor, and *boring* is a feature. Boring means your on-call doesn't get paged at 2am because the payment workflow randomly forgot where it was.

On the other side: **non-deterministic AI agents**. Squads, LLM-driven reasoning, multi-agent systems. Brilliant on open-ended judgment work. Feed a Squad agent a production incident report and it'll reason over the evidence, form hypotheses, and come back with a root-cause diagnosis that would have taken your on-call engineer 45 minutes of log spelunking to assemble. That's genuinely impressive. But: it's non-deterministic. Two identical inputs might produce subtly different outputs. Retrying is expensive (you're burning LLM tokens and time). Hallucinations are real. You can't just replay a failed Squad step the same way you replay a failed database write.

For a while, the industry seemed to think you had to *choose*. Either you build a reliable deterministic workflow and accept that it can't reason, or you build an AI system that can reason and accept that it's a reliability wildcard.

That framing is wrong.

* * *

## The Composition Pattern

You don't choose. You compose.

Here's the unlock: **the non-determinism is sandboxed inside one workflow step**. The workflow itself stays deterministic, observable, and replayable. Each step in the workflow can be:

- A **deterministic activity** — a DB write, an API call, a schema validation, a correlation check. Runs the same way every time. No LLM involved. Zero token cost.
- OR an **intelligent Squad step** — a multi-agent team that reasons over structured input, may call tools, may consult sub-agents, and produces structured output.

The durable engine doesn't care which kind of step it is. It checkpoints *after* each one. It retries on failure. It survives crashes. And the *output* of a Squad step — a structured verdict, a triage decision, a generated artifact — becomes the *deterministic input* to the next step.

![Diagram: The Composition Pattern](/assets/deterministic-meets-squads/diagram-1-composition-pattern.png)
<!-- DIAGRAM-BRIEF: Horizontal pipeline showing: [Incident Input] → dashed box labeled "🤖 Squad Triage (non-deterministic)" → solid box labeled "⚙️ Correlate (deterministic)" → dashed box labeled "🤖 Squad Diagnose (non-deterministic)" → [Action]. Above each step, a checkpoint icon (floppy disk or similar) with the label "durable engine saves state." Below each box, show the C# type flowing between steps: IncidentInput → IncidentTriage → IncidentCorrelation → IncidentDiagnosis. Use dashed borders for non-deterministic steps and solid borders for deterministic ones. Color: dashed = warm purple, solid = teal. Overall horizontal flow, clean, no clutter. -->

Let me show you exactly what this looks like in code.

I've been building a demo that runs Squad agents as participants in the Microsoft Agent Framework's workflow engine. The example that really nails the pattern is an **incident-response workflow** with three chained bindings:

**Step 1 — Squad Triage (non-deterministic):**

```csharp
var triageBinding = new FunctionExecutor<IncidentInput, IncidentTriage>(
    "triage",
    async (incident, context, ct) =>
    {
        var triageText = await DemoRuntime.RunAgentAsync(
            squad,
            BuildTriagePrompt(incident),
            ct);

        var triage = ParseTriage(triageText, incident);
        latestTriage = triage;

        await context.YieldOutputAsync(triage, ct);
        return triage;
    }).BindExecutor();
```

A Squad agent reads the raw incident input, reasons over it, and outputs a structured `IncidentTriage`: severity, affected components, candidate hypotheses. Non-deterministic. The Squad is doing real reasoning here.

**Step 2 — Deterministic Correlation (no LLM):**

```csharp
var correlateBinding = new FunctionExecutor<IncidentTriage, IncidentCorrelation>(
    "correlate",
    (triage, context, ct) =>
    {
        var correlation = new IncidentCorrelation(
            [
                new RootCauseHypothesis(
                    1,
                    "Pricing-cache TTL reduction amplified cache misses and exposed Redis shard-2 latency.",
                    0.72,
                    ["log-2", "log-3", "change-1", "change-3"]),
                new RootCauseHypothesis(
                    2,
                    "Redis shard-2 replacement introduced a hot shard or connection instability.",
                    0.21,
                    ["log-3", "change-3"]),
                // ...
            ],
            ["log-2", "log-3", "change-1", "change-3"]);

        return correlation;
    }).BindExecutor();
```

Pure code. Takes the `IncidentTriage`, runs deterministic correlation against recent incident evidence — computes feature vectors, ranks hypotheses by confidence, decides which evidence is relevant. Not a single LLM call. Zero tokens. Same input will always produce the same output.

**Step 3 — Squad Diagnosis (non-deterministic, but with correlated context):**

```csharp
var diagnoseBinding = new FunctionExecutor<IncidentCorrelation, IncidentDiagnosis>(
    "diagnose",
    async (correlation, context, ct) =>
    {
        var triage = latestTriage ?? throw new InvalidOperationException(
            "Triage must complete before diagnosis.");

        var diagnosisText = await DemoRuntime.RunAgentAsync(
            squad,
            BuildDiagnosisPrompt(input, triage, correlation),
            ct);

        var diagnosis = ParseDiagnosis(diagnosisText, triage, correlation);
        await context.YieldOutputAsync(diagnosis, ct);
        return diagnosis;
    }).BindExecutor();
```

Another Squad agent. But now it's not reasoning from scratch over raw logs — it's reasoning over *pre-correlated, ranked, high-confidence evidence*. The deterministic step did the bookkeeping work so the non-deterministic step can focus on judgment. That's a much better use of LLM reasoning capacity.

And the workflow composition:

```csharp
var workflow = new WorkflowBuilder(triageBinding)
    .WithName("incident-analysis-brain")
    .WithDescription("Synthetic incident brain: Squad triage -> deterministic correlate -> Squad diagnose.")
    .AddEdge(triageBinding, correlateBinding)
    .AddEdge(correlateBinding, diagnoseBinding)
    .WithOutputFrom(triageBinding, correlateBinding, diagnoseBinding)
    .Build();
```

That's it. Three steps. Two Squad (non-det), one deterministic. Chained in sequence. The whole thing runs as a single observable workflow.

(You can see the full `IncidentExample.cs` in [the demo repo](https://github.com/tamirdresher_microsoft/squad-agent-framework-demo).)

* * *

## Why The Workflow Stays Deterministic (Even When Steps Aren't)

I know what you're thinking. "Tamir, if two of your three steps are non-deterministic, how do you call this a deterministic workflow?"

Fair. Let me be precise.

The *workflow engine* is deterministic. After every step — Squad or otherwise — the engine checkpoints the output. If the process crashes after step 1 completes, it doesn't re-run step 1. It reads the checkpointed `IncidentTriage` and picks up at step 2. If step 3 fails with a transient error and needs to be retried, it re-runs step 3 with the *exact same* `IncidentCorrelation` input that it received the first time. The non-determinism is real, but it's *bounded*. Each retry of a Squad step is isolated to that step. The rest of the workflow is untouched.

This is the crucial difference between a Squad step failing inside a workflow and a Squad agent failing in isolation. In isolation, you've lost everything. In a workflow, you've lost at most one step, and the engine knows exactly where to resume.

![Diagram: Why the Workflow Stays Deterministic](/assets/deterministic-meets-squads/diagram-2-determinism-spine.png)
<!-- DIAGRAM-BRIEF: A horizontal row of 5 workflow "boxes" (steps), labeled alternately det/non-det. A horizontal bar running the full width under all boxes, labeled "Checkpointed by the durable engine after every step." Each box has a small checkpoint icon on its right edge. Show one box (the non-det Squad step) with a lightning bolt indicating a failure/retry. Arrow shows it re-runs from the checkpoint boundary, NOT from the beginning of the workflow. The overall visual message: the spine is deterministic even if individual boxes are not. Color scheme: deterministic boxes in teal, non-deterministic in warm purple, checkpoint bar in gray. Clean, flat design. -->

There's a reason DTS charges by step completion, not by total tokens or wall-clock time. Every completed step is a checkpoint. Every checkpoint is a guarantee. That's the mental model.

* * *

## Across Services, At Scale

Here's where things get interesting for real production systems.

Everything I've described so far runs in-process in the demo — `InProcessExecution.Default.RunAsync(...)` — which is intentional for a demo. But the same workflow composition code works with the Durable Task Scheduler as the backend. Swap one line of configuration, and your workflow now:

- Runs **across services** — the Correlate step can be hosted in Service B, the Diagnose Squad can be hosted in Service C, and the orchestration manages the whole thing from a managed DTS backend
- **Survives process restarts, deployments, even region failovers** — state is externalized to DTS, not held in memory
- **Scales horizontally** — you can run dozens of concurrent incident-analysis workflows, each checkpointed independently
- Is **observable in the DTS dashboard** — you can see every running workflow, every step, its status, its input/output history

Think about the architectural implication. Your order service emits a fulfillment event. DTS picks it up, kicks off an orchestration. Step 1: a deterministic enrichment task in the fulfillment service adds shipping address and inventory data. Step 2: a Squad agent in a separate service reasons over the enriched order and decides whether it triggers any compliance flags. Step 3: back in the order service, a deterministic activity writes the compliance verdict to the database and sends a webhook. Three services, two deterministic steps, one non-deterministic Squad step. One workflow. One checkpoint log. One observability dashboard.

![Diagram: Cross-Service Fan-Out at Scale](/assets/deterministic-meets-squads/diagram-3-cross-service.png)
<!-- DIAGRAM-BRIEF: Three service boxes arranged in a row: "Service A (Order API)", "Service B (Fulfillment)", "Service C (Compliance Squad)". Below all three: a horizontal "DTS Orchestration" bar with a checkpoint at each step transition. Flow: Service A emits event → DTS starts workflow → Step 1 (deterministic enrichment in Service B) → Step 2 (Squad reasoning in Service C) → Step 3 (deterministic DB write back in Service A). Arrows connecting the steps pass through the DTS bar, indicating the durable engine holds state across all service boundaries. Show the DTS dashboard icon (optional) above the orchestration bar. Clean, flat design. -->

The Microsoft [Bulletproof Agents announcement](https://techcommunity.microsoft.com/blog/appsonazureblog/bulletproof-agents-with-the-durable-task-extension-for-microsoft-agent-framework/4467122) covers the production story for this. Worth reading if you want the full picture of how DTS plugs into the Microsoft Agent Framework in production.

* * *

## Why The Demo Uses Aspire

The demo runs with `dotnet run --project Squad.AgentFramework.Demo.AppHost`, and Aspire handles the rest. Here's the AppHost:

```csharp
var foundry = builder.AddAzureAIFoundry("foundry")
    .RunAsFoundryLocal();

var chat = foundry.AddDeployment("chat", "phi-3.5-mini", "1", "Microsoft");

builder.AddProject<Projects.Squad_AgentFramework_Demo>("squad-agent-framework-demo")
    .WithEnvironment("SQUAD_AF_PROVIDER", "foundry-local")
    .WithReference(chat)
    .WaitFor(chat);
```

Three lines and Aspire has wired up a local Foundry LLM, configured the chat connection, and told the demo project to wait until the model is ready before starting. The demo app gets `ConnectionStrings__chat` injected automatically. You don't set `SQUAD_AF_ENDPOINT`, `SQUAD_AF_DEPLOYMENT`, or `SQUAD_AF_API_KEY` anywhere. Aspire injects the contract; the app reads it.

I know this seems like a small thing. It isn't. In a system where you're composing deterministic and non-deterministic steps, the *configuration* of the non-deterministic side (which LLM provider? which model? which endpoint?) is exactly the kind of detail that becomes friction in production. When that friction is handled by the orchestration layer — which Aspire effectively is — you can focus on the composition instead of the plumbing.

![Aspire dashboard showing Squad, Foundry, and the demo all running healthy](/assets/deterministic-meets-squads/aspire-resources.png)

The Aspire dashboard shows what's running. You can see `foundry`, `chat`, and `squad-agent-framework-demo` all in a healthy state. That's the full stack: LLM backend, model deployment, and your workflow host — all orchestrated, all observable, all wired together automatically.

And when you want to watch what's actually happening during a workflow run, the Console logs tab shows you the Copilot SDK session events in real time:

![Aspire Console logs showing live Copilot SDK session events from the Foundry Local LLM call](/assets/deterministic-meets-squads/aspire-traces-detail.png)

Those are real trace lines from `TraceCopilotEvent` — you can see the Squad agent's session lifecycle as it reasons over the incident evidence. That observability is free when you run under Aspire. It's not wired up to OpenTelemetry OTLP (yet — that's a separate topic), but for local development, it's exactly what you need to understand what your non-deterministic steps are actually doing.

* * *

## The Cheat Sheet

I know some of you are already building workflows and wondering where the line is. Here's how I think about it:

### Make a step deterministic when:

- The logic is pure bookkeeping: DB writes, API calls, schema validation, idempotency checks
- You need the step to be **exactly reproducible** on retry with zero token cost
- The input-to-output mapping is a function you could unit-test
- Performance and cost predictability matter (deterministic steps are cheap and fast)

### Make a step a Squad when:

- The work requires **open-ended judgment** — triage, diagnosis, risk assessment, anomaly classification
- The input is unstructured or semi-structured (natural language, log text, documents)
- The output is a **verdict or hypothesis** that a downstream deterministic step will act on
- You need the step to **adapt to novel inputs** that no hardcoded rule could handle

The key principle: **Squad steps produce structured output that deterministic steps consume**. If your Squad step is producing unstructured free text that the next step has to parse, you're doing it wrong. Define the output type (`IncidentTriage`, `ComplianceVerdict`, `RootCauseHypothesis`) and have the Squad step produce it. Then the deterministic step can process it reliably.

* * *

## What I Wish I'd Said In The DTS Post

[When I wrote about the Durable Task Scheduler](/blog/2026/04/07/durable-task-scheduler), I focused mostly on the mechanics of durable workflows — checkpointing, the replay model, the comparison with Hangfire and Conductor, the "use DTS when" cheat sheet. All of that stands.

But I ended the post with one paragraph about AI agents and then moved on. What I should have said is: the reason DTS matters *for AI systems* isn't just that it gives your agents durable state. It's that it gives you a **composition model** where you can mix agents and code, where the non-determinism is bounded and auditable, where you get production-grade reliability without sacrificing the judgment capabilities of an intelligent Squad.

The fan-out patterns from [Part 12 of this series](/blog/2026/04/25/scaling-ai-part12-fanout-squads) apply here too. You can fan out to *multiple* Squad teams in parallel, have each run its own non-deterministic reasoning, and then aggregate their outputs in a deterministic step. The durable engine handles the fan-out, the timeout, the "wait for all of them" join. You just write the composition.

And yes, this scales. The same code that runs in-process in the demo runs against DTS in production. The upgrade path is one config change.

* * *

## The Bottom Line

If you're building AI systems and you're not thinking about workflow composition, you're going to hit the reliability wall. Maybe not in the demo. Probably in the first production incident.

The pattern is this: **use deterministic steps where logic is a function, use Squad steps where logic is judgment, and use a durable workflow engine to compose them both**. DTS is the engine. Microsoft Agent Framework is the composition model. Aspire is the dev-time orchestration. And `IncidentExample.cs` is the template.

Start there. Build a three-step workflow. Make two steps deterministic, one a Squad. Run it. Watch the Aspire dashboard. Then scale it up.

Now go compose something durable. 🚀

* * *

**Want to dive deeper?**

- [Durable Task Scheduler — The Workflow Engine You're Not Using](/blog/2026/04/07/durable-task-scheduler) — Part 1: the DTS story, Payoneer war story, comparison table, and how to get started
- [Scaling AI Part 12: Fan-Out with Squads](/blog/2026/04/25/scaling-ai-part12-fanout-squads) — parallel Squad composition and the fan-out/fan-in pattern
- [Bulletproof Agents with the Durable Task Extension for Microsoft Agent Framework](https://techcommunity.microsoft.com/blog/appsonazureblog/bulletproof-agents-with-the-durable-task-extension-for-microsoft-agent-framework/4467122) — the official Microsoft announcement
- [squad-agent-framework-demo](https://github.com/tamirdresher_microsoft/squad-agent-framework-demo) — the demo repo with `IncidentExample.cs`, `WorkflowExample.cs`, and Aspire AppHost
- [Microsoft Agent Framework docs](https://learn.microsoft.com/en-us/agent-framework/) — the full framework documentation
