---
layout: post
title: "Make It So — But Let the Computer Handle the Math"
date: 2026-05-20
tags: [durable-task-scheduler, ai-agents, squad, microsoft-agent-framework, aspire, workflows, distributed-systems, dotnet, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 14
image: /assets/deterministic-meets-squads/aspire-dashboard-squad.png
---

![The Aspire dashboard showing Squad, Foundry, and the demo running healthy](/assets/deterministic-meets-squads/aspire-dashboard-squad.png)

*"Computer, what is the current stardate?"* — Every Starfleet officer, not because the ship's computer is smart, but because it's fast, exact, and it has never in the history of the franchise said "well, I think the answer is probably around stardate 47634.44 but I'm not entirely sure."

Nobody asks the ship's computer whether to negotiate with the Romulans. That's Picard's job. They ask it for precise data — sensor readings, crew locations, power consumption, warp trajectory. Sub-second. The same answer every time. No tokens burned. No rate limits hit.

Here's the question I keep hearing from developers building AI systems: **where does the line go between what the AI does and what code does — and how do you actually wire them together?**

That question has a good answer. This post is it.

* * *

## The False Choice

For a while, the conversation in our industry seemed to frame this as a binary. Either you build a reliable, deterministic system — clear logic, predictable outputs, boring in all the right ways. Or you build an AI-powered system that reasons and adapts and handles messy real-world inputs. Pick one.

The implication was that these are mutually exclusive. Smart systems are unreliable. Reliable systems are dumb.

The Enterprise runs on neither of those extremes, and it's the most capable ship in the quadrant. Picard makes the call. The ship's computer runs the math. Engineering follows procedures. Worf handles threat assessment. The crew handles novel situations; the automated systems handle the routine. Each tool gets used for what it's actually good at. Nobody asks the computer whether to violate the Prime Directive, and Picard never personally calculates the warp trajectory.

**That division of labor is the architecture this post is about.** Not AI *or* code, but AI *and* code, composed deliberately.

* * *

## What AI Is Actually Good At

Some problems don't have a deterministic answer. You can't write a function for them because the inputs are messy, the problem space is open-ended, and the right answer depends on judgment, context, and reasoning — things no lookup table can give you.

- "Read this production incident report and tell me what's likely wrong."
- "Here are 20 customer messages. Which ones are complaining about the same underlying issue?"
- "This contract changed three ways. Does any of it affect our SLA obligations?"

These are "Number One, what do you make of this?" problems. Riker doesn't compute an answer. He evaluates the situation, draws on experience, considers context you didn't explicitly give him, and gives you his judgment. An LLM does the same thing.

### When to reach for AI

AI steps earn their cost when the work requires:

- **Open-ended reasoning** over unstructured or semi-structured input
- **Hypothesis formation** when you don't have a lookup table
- **Adaptation to novel situations** that no hardcoded rule would have anticipated
- Producing a **structured verdict** — triage result, diagnosis, classification, risk assessment — from fuzzy evidence

That last bullet matters: the output of your AI step should be *typed and structured*. Define the output type — `IncidentTriage`, `ComplianceVerdict`, `ClassificationResult` — and have the AI produce it. That structure is what the downstream deterministic step consumes. If your AI step is producing prose and your next step is parsing it for keywords, the interface is wrong.

* * *

## What Code Is Actually Good At

*"Computer, locate Commander Riker."*

Sub-second. Deterministic. The same answer every time. Zero tokens. No rate-limit exposure. No possibility that the answer comes back as "Lieutenant Commander Riker is probably in Engineering, I think."

### When to reach for code

Deterministic C# earns its place when:

- The logic is a **database lookup, API call, schema validation, or idempotency check**
- You need the step to be **exactly reproducible on retry** — same input, same output, always
- The logic is something you could unit-test
- The output will be **cited in a compliance audit**
- You can't afford a 500ms–3 second latency hit on what is effectively a glorified `if` statement

The deterministic step is not just a cost-saver. It's a guarantee. "We ran the compliance check deterministically and it passed" means something. "The AI said it looked fine" means considerably less when a regulator asks.

* * *

## Why Not Just Run Everything Through the AI?

Good question. Let's do the math.

**Tokens cost money.** Every LLM step burns input tokens (your prompt, the context you pass) plus output tokens (everything the model generates back). If you have a 7-step workflow and 5 of those steps could be plain C# — data lookups, validation, correlation — but you route them all through an LLM anyway, you're paying 5× for work that costs single-digit milliseconds in code.

**Latency stacks fast.** A single LLM call is typically 500ms to 3 seconds. Five sequential LLM calls = 2.5 to 15 seconds of coordination overhead before any real work happens. A deterministic C# step runs in under 10 milliseconds. Stack enough unnecessary AI steps and you've built a slow pipeline for reasons that have nothing to do with the complexity of the problem.

**Rate limits are real.** Every provider enforces TPM (tokens per minute) and RPM (requests per minute) caps. In a hot workflow with many concurrent instances, unnecessary LLM calls eat into those caps fast. When you hit a 429, your retry logic re-spends *both* time and tokens. Unnecessary LLM steps are rate-limit landmines buried in your workflow.

**Determinism matters for correctness.** "Look up the customer's tier" is a database query. The answer is Gold, Silver, or Bronze — it's in the database, it's exact, and it's free. Routing that through an LLM introduces the possibility of a wrong answer where the right answer was always deterministic. You've made the system less correct and more expensive at the same time.

**Auditability is non-negotiable in some domains.** A regulator asking "why did your system flag this transaction for review?" deserves a traceable answer with inputs, outputs, and a deterministic function you can point to. "The LLM decided" is not an acceptable answer in a compliance review.

Here's the concrete number: if your workflow runs **10,000 times a day** and you replace 4 unnecessary LLM steps with C# functions, you've eliminated **40,000 LLM calls**. That's your rate-limit headroom, your latency budget, and a non-trivial line item on your inference bill — every single day.

Use AI for judgment. Use code for everything else.

* * *

## The Pattern: The Sandwich

The pattern is simple enough to show before any framework code:

```csharp
// Step 1 — let the AI read the incident and tell us what kind of problem this is
TriageVerdict verdict = await squad.RunAsync(incidentReport);

// Step 2 — plain old C#. No AI. Deterministic. Free.
// Correlate the triage against recent logs, rank hypotheses by confidence.
EvidenceBundle evidence = CorrelateEvidence(verdict, recentLogs);

// Step 3 — let the AI reason over the *pre-ranked* evidence, not the raw noise
DiagnosisResult diagnosis = await squad.RunAsync(BuildDiagnosisPrompt(evidence));
```

AI call → C# function → AI call. That's the sandwich.

Notice what the middle step does. It doesn't just save money and time — it *improves* the quality of step 3. Instead of feeding the AI a raw dump of logs and hoping it picks out the relevant signals, the deterministic step does the bookkeeping: correlate evidence, compute confidence scores, rank hypotheses, trim noise. The AI in step 3 receives a curated, pre-ranked context. Less noise, better judgment.

![Diagram: The AI / Deterministic / AI sandwich — typed data flows between steps](/assets/deterministic-meets-squads/diagram-1-composition-pattern.png)

The dashed boxes are AI steps — non-deterministic, expensive when misused, powerful when used correctly. The solid box is deterministic C#. Data types flow between them: `IncidentInput` → `TriageVerdict` → `EvidenceBundle` → `DiagnosisResult`. That's the entire pattern.

* * *

## The Same Demo, In Real Code

The [squad-agent-framework-demo](https://github.com/tamirdresher_microsoft/squad-agent-framework-demo) implements this as an incident-response workflow. Three steps. Two Squad. One deterministic. Here's the conceptual shape from `IncidentExample.cs`:

### Step 1 — Squad Triage (non-deterministic)

A Squad agent reads the raw incident report and produces a structured `IncidentTriage`. Which components are affected? What are the candidate hypotheses? The AI is doing what it's good at: reasoning over unstructured incident evidence with no predefined answer key.

### Step 2 — Deterministic Correlation (no LLM)

Pure C#. Takes the `IncidentTriage` and runs a correlation against the known evidence set — ranks root-cause hypotheses by confidence (0.72 for the most likely, 0.21 for the second, 0.07 for the third), identifies which log lines are relevant, packages everything into an `IncidentCorrelation`. No LLM involved. No tokens. Same input always produces the same output.

### Step 3 — Squad Diagnosis (non-deterministic, but with curated context)

Another Squad agent. But now it isn't reasoning from scratch over a firehose of raw logs — it's reasoning over pre-ranked, pre-correlated, high-confidence evidence. The deterministic step did the bookkeeping so the AI step can focus on judgment.

```csharp
// The shape of the three-step workflow — simplified to show the idea
var triage      = await squad.RunTriageAsync(incidentInput);          // AI step
var correlation = CorrelateEvidence(triage, incidentEvidence);        // Deterministic C#
var diagnosis   = await squad.RunDiagnosisAsync(triage, correlation); // AI step
```

The full source — including the `FunctionExecutor<>` wrappers that wire each step into the Microsoft Agent Framework workflow engine — is in the demo repo. The wrappers are framework plumbing (think of them as the wiring harness, not the engine). The shape above is what matters.

Running this under Aspire gives you visibility into everything in real time. The AppHost wires up a local Foundry LLM and injects the connection into the demo project automatically — no manual `SQUAD_AF_ENDPOINT`, `SQUAD_AF_DEPLOYMENT`, or `SQUAD_AF_API_KEY` needed.

![The Aspire dashboard — Squad, Foundry, and the demo all healthy and connected](/assets/deterministic-meets-squads/aspire-dashboard-squad.png)

You get `foundry`, `chat`, and `squad-agent-framework-demo` all healthy in one dashboard. LLM backend, model deployment, and your workflow host — orchestrated, wired, observable.

The console logs show the non-deterministic side in action:

![Aspire console trace — live Copilot SDK session events from the Squad agent reasoning over incident evidence](/assets/deterministic-meets-squads/aspire-traces-detail.png)

Those are real `TraceCopilotEvent` lines — the Squad agent's session lifecycle as it reasons over the incident. That's your window into the non-deterministic step while everything around it stays fully observable.

And a look at all running resources:

![Aspire resources view — foundry, chat model, and demo project all running healthy](/assets/deterministic-meets-squads/aspire-resources.png)

* * *

## What If the Process Crashes Mid-Sandwich?

Good news: the sandwich is durable.

The Microsoft Agent Framework workflow engine checkpoints after every step. If the process crashes between step 2 and step 3, it doesn't re-run step 1 or step 2. It reads the checkpointed output of step 2 and resumes at step 3. The non-determinism is real, but it's *bounded* — each Squad step can be retried in isolation, with the same input it received the first time. The rest of the workflow is untouched.

This is the critical difference between a Squad step failing inside a workflow versus failing in isolation. In isolation: you've lost everything and don't know where you were. Inside a workflow: you've lost at most one step, the engine knows exactly where to resume, and the retry is scoped precisely.

The [Durable Task Scheduler](https://www.tamirdresher.com/blog/2026/04/07/durable-task-scheduler) is the backend that makes this work. It externalizes workflow state, so process restarts, deployments, and transient failures don't lose progress. The Microsoft devblogs post on [Durable Workflows in Microsoft Agent Framework](https://devblogs.microsoft.com/dotnet/durable-workflows-in-microsoft-agent-framework/) covers the executor model, workflow builder, and replay semantics in full detail — highly recommend reading it alongside this post.

![Diagram: The deterministic checkpoint spine — retry boundaries are per-step, not per-workflow](/assets/deterministic-meets-squads/diagram-2-determinism-spine.png)

Starfleet probably learned this after the third time the ship's computer lost a critical process mid-execution and had to restart the entire warp diagnostic from scratch. Checkpoints exist for a reason.

* * *

## What If the Workflow Spans Services?

The same pattern works when your steps live in different services.

When you swap the in-process runner for DTS as the backend, workflow state is externalized to the DTS store — not held in memory. The triage step can run in Service A. The deterministic correlation step can run in Service B. The diagnosis step can run in Service C. The DTS orchestration holds state across all service boundaries, checkpointing at every transition.

The practical shape: your order service emits a fulfillment event. DTS kicks off a workflow. A deterministic enrichment step in the fulfillment service adds shipping data. A Squad agent in a compliance service reasons over the enriched order. A deterministic step in the order service writes the verdict to the database and sends a webhook. Three services. One workflow. One checkpoint log. One Aspire dashboard showing every step's status.

![Diagram: Cross-service workflow — three services connected through the DTS orchestration spine](/assets/deterministic-meets-squads/diagram-3-cross-service.png)

The upgrade path from the in-process demo to a full distributed DTS-backed deployment is one configuration change. The [Bulletproof Agents announcement](https://techcommunity.microsoft.com/blog/appsonazureblog/bulletproof-agents-with-the-durable-task-extension-for-microsoft-agent-framework/4467122) covers the production story.

* * *

## Where the Line Actually Goes — A Cheat Sheet

Here's the decision rule for any individual step:

**Route it to code when:**

- It's a lookup, API call, schema validation, or idempotency check
- The input-to-output mapping is a function you could unit-test
- The output needs to be cited in a compliance audit
- It touches money, security decisions, or authorization logic
- You need the output to be *identical* on retry

**Route it to AI when:**

- The input is unstructured or the problem requires open-ended judgment
- You need it to adapt to novel situations no rule would handle
- You're producing a structured verdict that downstream code will act on
- The question is "what does this mean?" not "what is this equal to?"

**Wrap AI steps in deterministic guard rails when:**

- The output drives a money transfer, a security decision, or a compliance action
- You need to produce an audit trail
- You need to bound the cost of retries

The core principle: **AI steps produce structured output that deterministic steps consume**. The handoff is typed, explicit, and deterministic on the boundary. The non-determinism stays inside the box, not on the wire.

* * *

## The Bottom Line

So, where does the line go?

The line goes wherever the *nature of the problem* tells you it should. If the problem is a judgment call — open-ended, fuzzy, novel — that's an AI step. If the problem is a function — exact, repeatable, auditable — that's code. The durable workflow engine is the composition layer that lets you mix them freely, checkpoint after each one, and recover gracefully from failures on either side.

The Enterprise is extraordinarily effective *because of* its division of labor, not despite it. The computer handles what the computer handles. Picard handles what Picard handles. The crew is remarkable precisely because nobody's job overlaps with anyone else's in ways that create confusion.

"Computer, run the diagnostic." Deterministic. Sub-second. Free.

"Number One, what do you make of this?" Judgment. Slow. Necessary.

Make it so.

* * *

**Want to dive deeper?**

- [Durable Task Scheduler — The Workflow Engine You're Not Using](https://www.tamirdresher.com/blog/2026/04/07/durable-task-scheduler) — the DTS story, the Payoneer war story, comparison table, and how to get started
- [Durable Workflows in Microsoft Agent Framework](https://devblogs.microsoft.com/dotnet/durable-workflows-in-microsoft-agent-framework/) — the deep dive on executors, workflow builders, and the replay model
- [Bulletproof Agents with the Durable Task Extension for Microsoft Agent Framework](https://techcommunity.microsoft.com/blog/appsonazureblog/bulletproof-agents-with-the-durable-task-extension-for-microsoft-agent-framework/4467122) — the official production DTS + MAF announcement
- [squad-agent-framework-demo](https://github.com/tamirdresher_microsoft/squad-agent-framework-demo) — the demo repo with `IncidentExample.cs` and the Aspire AppHost