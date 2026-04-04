---
layout: post
title: "The Azure Service I Should Have Been Using For Years (But Wasn't)"
date: 2026-04-10
tags: [azure, durable-task, orchestration, dotnet, workflow, distributed-systems]
description: "A deep dive into the Durable Task Framework and Azure Durable Task Scheduler — the underrated orchestration stack that handles all the hard stuff so you don't have to."
---

> *"The greatest trick the devil ever pulled was convincing the world he didn't exist."*  
> — Keyser Söze, The Usual Suspects  
> *(Also: every underrated Azure service ever.)*

Let me tell you about the conversation I had with myself last spring.

I was neck-deep in a distributed workflow problem. We had a multi-step process that needed to fan out across dozens of parallel tasks, aggregate results, handle retries on transient failures, survive process restarts, and — the kicker — wait for an external human approval that might come back in five minutes or five days.

My first instinct was to reach for a message queue and a state table and a timer and maybe some Blob storage for checkpoints, and before I knew it I was looking at a whiteboard that looked like someone had taken a flight map and asked it to explain itself. I'd been here before. I'd solved this before. And I was about to solve it *again*, from scratch, the hard way.

A colleague (who had clearly been waiting for the right moment) asked: "Have you looked at Durable Task?"

Reader, I had not. Not really. I knew it existed. I'd skimmed a docs page once. I had lumped it in with "things that are probably cool but require Azure Functions" and filed it under *look at later*. Later never came.

That was a mistake. Let me save you from making the same one.

---

## What Is the Durable Task Framework, Actually?

The [Durable Task Framework (DTFx)](https://github.com/Azure/durabletask) is an open-source .NET library that lets you write long-running, fault-tolerant workflows using ordinary async/await code. No state machines. No compensation tables. No custom checkpoint logic. You write a method, you `await` things, and the framework handles making it survive crashes, retries, and the general chaos of distributed systems.

Here's the magic of it. Imagine you want to model this workflow:

1. Receive an order
2. Verify payment (can fail, should retry)
3. Fan out to notify warehouse, shipping, and analytics in parallel
4. Wait for warehouse to confirm inventory (could take hours)
5. Update order status

Without orchestration primitives, this is a nightmare of queues, timers, and state tracking spread across multiple services. With DTFx, it looks like this:

```csharp
[DurableTask]
public class OrderFulfillmentOrchestration : TaskOrchestrator<OrderInput, OrderResult>
{
    public override async Task<OrderResult> RunAsync(
        TaskOrchestrationContext context, OrderInput order)
    {
        // Step 1: Verify payment — retries on transient failure
        var paymentResult = await context.CallActivityAsync<PaymentResult>(
            nameof(VerifyPaymentActivity), order,
            new TaskOptions { Retry = new RetryPolicy(maxRetries: 3, firstRetryInterval: TimeSpan.FromSeconds(5)) });

        if (!paymentResult.Success)
            return OrderResult.PaymentFailed(paymentResult.Reason);

        // Step 2: Fan out notifications in parallel
        var tasks = new[]
        {
            context.CallActivityAsync(nameof(NotifyWarehouseActivity), order),
            context.CallActivityAsync(nameof(NotifyShippingActivity), order),
            context.CallActivityAsync(nameof(NotifyAnalyticsActivity), order),
        };
        await Task.WhenAll(tasks);

        // Step 3: Wait for external inventory confirmation — could be hours, no polling
        var confirmation = await context.WaitForExternalEventAsync<InventoryConfirmation>(
            "InventoryConfirmed",
            timeout: TimeSpan.FromHours(48));

        return OrderResult.Fulfilled(confirmation.EstimatedShipDate);
    }
}
```

Read that again. That `WaitForExternalEventAsync` call — your process can sleep for 48 hours waiting for that event, and if the host crashes while waiting, when it comes back up the orchestration resumes exactly where it left off. No polling. No stored timer records. No "check if we have a pending approval row in the database." The framework reconstructs the orchestration's state by replaying the history.

This is the bit that took me a minute to fully appreciate. The code looks synchronous and simple. Under the hood, the framework is storing every step as an event log and replaying that log to reconstruct state. It's event sourcing, but you never write the event sourcing code.

---

## The Part I Glossed Over: DTFx vs. Durable Functions vs. Durable Task SDKs

Okay, this is where the naming gets a little confusing, and I want to untangle it properly because I definitely got confused.

- **DTFx (Durable Task Framework)** — the original, community-maintained open-source library. Think of it as the core engine. Powerful, battle-tested (Microsoft's own teams use it in production), but community-supported rather than Microsoft-supported.

- **Durable Functions** — Azure Functions' hosted orchestration experience. Built on DTFx under the hood. If you're already in the Functions world, this is the natural path. Full Microsoft support, tight Functions integration.

- **Durable Task SDKs** — the modern, officially-supported, polyglot evolution. Available for .NET, Python, Java, and JavaScript/TypeScript. These work on *any compute* — Azure Container Apps, AKS, VMs, your laptop. Not tied to Azure Functions at all.

- **Azure Durable Task Scheduler** — the managed Azure backend for the Durable Task SDKs and Durable Functions. Think of it as "we run the hard orchestration infrastructure, you just run your app."

For a new project? Start with the **Durable Task SDKs + Azure Durable Task Scheduler**. You get official Microsoft support, a built-in dashboard, multi-language support, and you're not locked to Functions hosting. That's the stack I'll focus on for the rest of this post.

---

## Why the Scheduler Changes Things

When I say "managed backend," I don't want that to sound boring. Here's what it actually means.

In the old DIY world of running DTFx yourself, you had to provision storage (Service Bus queues, Azure Storage accounts, or a SQL database), manage connection strings, deal with partition management overhead consuming your app's CPU, and figure out how to observe what's actually happening in your orchestrations.

The **Azure Durable Task Scheduler** is a purpose-built Azure resource (`Microsoft.DurableTask/schedulers`) that takes all of that away:

**No polling.** Work items are pushed to your app over a gRPC connection. Your app isn't burning cycles asking "anything for me?" — the scheduler pushes work the moment it's ready.

**No storage account to manage.** State lives inside the scheduler resource. Highly optimized for this exact use case. Lower latency, better durability, less operational noise.

**A dashboard that actually ships with the product.** Not "here's how to hook up Azure Monitor and build some queries." An actual UI, out of the box, where you can see all your orchestration instances, drill into their history, see what steps ran, how long each activity took, and perform management operations like pausing or terminating a stuck workflow.

**Task hubs for isolation.** One scheduler resource, multiple task hubs — one per environment, one per team, whatever makes sense. They share the scheduler's resources but stay logically isolated.

And for local development: a **Docker emulator** that runs the full scheduler locally. No Azure subscription needed to iterate.

```bash
docker run --name dtsemulator -d -p 8080:8080 -p 8082:8082 \
  mcr.microsoft.com/dts/dts-emulator:latest
```

That's it. Full local scheduler, with the same dashboard UI, pointing at `http://localhost:8082`.

---

## Getting Started: A Real Code Walkthrough

Let me show you a minimal but complete example using the .NET SDK. We're building a fan-out/fan-in orchestration — kick off a bunch of parallel tasks, wait for all of them, aggregate the results. Classic pattern, surprisingly painful to implement yourself.

**Install the packages:**

```bash
dotnet add package Microsoft.DurableTask.Worker.AzureManaged
dotnet add package Microsoft.DurableTask.Client.AzureManaged
```

**Define the orchestration and activities:**

```csharp
// The orchestration — runs on the worker, coordinates everything
[DurableTask]
public class BatchProcessingOrchestration : TaskOrchestrator<string[], BatchResult>
{
    public override async Task<BatchResult> RunAsync(
        TaskOrchestrationContext context, string[] items)
    {
        context.SetCustomStatus("Processing started");

        // Fan out: kick off one activity per item, all in parallel
        var tasks = items.Select(item =>
            context.CallActivityAsync<ItemResult>(
                nameof(ProcessItemActivity), item));

        var results = await Task.WhenAll(tasks);

        // Fan in: aggregate
        return new BatchResult
        {
            ProcessedCount = results.Length,
            SuccessCount = results.Count(r => r.Success),
            TotalDuration = results.Sum(r => r.ProcessingMs)
        };
    }
}

// An activity — the unit of work, runs independently
[DurableTask]
public class ProcessItemActivity : TaskActivity<string, ItemResult>
{
    public override async Task<ItemResult> RunAsync(
        TaskActivityContext context, string item)
    {
        // Your actual work here — call an API, process a record, whatever
        await Task.Delay(Random.Shared.Next(100, 500)); // simulate real work
        return new ItemResult { Item = item, Success = true, ProcessingMs = 250 };
    }
}
```

**Wire up the worker (Program.cs):**

```csharp
var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddDurableTaskWorker(workerBuilder =>
{
    workerBuilder.AddTasks<BatchProcessingOrchestration>();
    workerBuilder.AddTasks<ProcessItemActivity>();
    
    // Uses emulator by default if no env vars set — production uses Azure
    workerBuilder.UseAzureManaged();
});

builder.Services.AddDurableTaskClient(clientBuilder =>
{
    clientBuilder.UseAzureManaged();
});

var host = builder.Build();
await host.RunAsync();
```

**Schedule an orchestration from the client:**

```csharp
var client = host.Services.GetRequiredService<DurableTaskClient>();

var items = new[] { "Item1", "Item2", "Item3", "Item4", "Item5" };
var instanceId = await client.ScheduleNewOrchestrationInstanceAsync(
    nameof(BatchProcessingOrchestration), items);

Console.WriteLine($"Started orchestration: {instanceId}");

// Wait for it to complete
var result = await client.WaitForInstanceCompletionAsync(instanceId);
Console.WriteLine($"Completed: {result.SerializedOutput}");
```

Run the emulator first, then start the worker and client. Open `http://localhost:8082` in your browser and watch the orchestration run through the dashboard. See each activity start and complete in real time. That's not a demo rig — that's what your production setup looks like too.

---

## When Should You Reach for This?

Not everything needs orchestration. Simple queue-consumer patterns work fine. But if you find yourself building any of these, stop and look at Durable Task first:

**Long-running processes that need to survive restarts.** Data pipeline that takes hours. Approval workflows waiting on humans. Anything where "the host died, start over" is not acceptable.

**Fan-out/fan-in with real parallelism.** You need to spin up 50 parallel tasks, collect all their results, and make a decision. Doing this with a message queue and a correlation ID table works, but it's annoying to build and annoying to debug. Durable Task makes it three lines of code.

**Workflows with complex error handling and retries.** Built-in retry policies with exponential backoff, per-activity. Automatic state persistence means a retry doesn't re-run everything from scratch — it picks up from the last successful checkpoint.

**External event integration.** "Wait until a human approves this" or "wait until the webhook fires" or "wait up to 72 hours for a payment confirmation." Without orchestration, this is a timer + database row + polling loop. With Durable Task, it's `WaitForExternalEventAsync`.

**Multi-agent orchestration.** This one is increasingly relevant. If you're building AI workflows where Agent A kicks off work, waits for Agent B and Agent C to finish in parallel, collects their outputs, and feeds them to Agent D — that's exactly what Durable Task is designed for. The framework already powers a lot of the infrastructure behind Semantic Kernel's process orchestration features.

---

## The Thing I Wish Someone Had Told Me

Here's my honest take after spending real time with this stack: the hardest part isn't the framework. The framework is excellent. The hardest part is accepting that you don't need to build the orchestration infrastructure yourself.

I spent years writing bespoke workflow engines. Queues and state machines and compensation tables and checkpoint logic. And I'm not saying that experience was wasted — understanding what the framework is doing underneath makes you use it better. But at some point, "I could build this myself" stops being a reason to do so.

The Durable Task Scheduler is a managed service that Microsoft's own engineering teams use in production. The Durable Task SDKs are officially supported, actively developed, and available in four languages. The local emulator ships a full dashboard. The pricing model has both dedicated and consumption tiers.

This is a production-ready, fully-supported, genuinely well-designed piece of infrastructure. The fact that it's not in every architecture conversation is the thing I can't explain.

So here's my challenge to you: next time you're about to draw a state machine on a whiteboard and figure out which queue goes where — look at Durable Task first. Spend 30 minutes with the quickstart. Run the emulator locally. Open the dashboard.

I'll bet the whiteboard stays clean.

---

## Quick Reference

| What you want | What to use |
|---|---|
| Serverless, Azure Functions hosting | Durable Functions |
| Any compute (.NET, Python, Java, JS) | Durable Task SDKs |
| Managed backend + dashboard | Azure Durable Task Scheduler |
| Local development | Docker emulator (`mcr.microsoft.com/dts/dts-emulator`) |

**Useful links:**

- [Durable Task SDKs overview](https://learn.microsoft.com/azure/azure-functions/durable/durable-task-scheduler/durable-task-overview)
- [Azure Durable Task Scheduler docs](https://learn.microsoft.com/azure/azure-functions/durable/durable-task-scheduler/durable-task-scheduler)
- [Quickstart: Fan-out/fan-in with Durable Task SDKs](https://learn.microsoft.com/azure/azure-functions/durable/durable-task-scheduler/quickstart-portable-durable-task-sdks)
- [Sample code repository (Azure-Samples/Durable-Task-Scheduler)](https://github.com/Azure-Samples/Durable-Task-Scheduler)
- [Original DTFx repo (Azure/durabletask)](https://github.com/Azure/durabletask)

---

## Demo Repo

> **Demo repo: [TBD — to be built]**
>
> I'm building a companion repo that walks through a realistic end-to-end scenario: an order processing workflow with payment verification, parallel notifications, a human approval step, and full observability via the Durable Task Scheduler dashboard. Watch this space (or the GitHub issue) for the link when it's ready.

---

*Have you used Durable Task in production? I'd love to hear what patterns you've hit and what tripped you up. Find me on [GitHub](https://github.com/tamirdresher) or [LinkedIn](https://linkedin.com/in/tamirdresher).*
