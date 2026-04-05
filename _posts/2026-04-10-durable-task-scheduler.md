---
layout: post
title: "This Is the Best Framework and Azure Service You're Probably Not Using"
date: 2026-04-10
tags: [azure, durable-task-framework, durable-functions, orchestration, workflows, background-jobs, dotnet]
---

I've been circling this technology for almost a decade. Stick with me.

Back in 2017, I was a Senior Architect at CodeValue, and I wrote one of the early deep-dives on Azure Durable Functions for [Microsoft's MVP Award blog](https://learn.microsoft.com/en-us/archive/blogs/mvpawardprogram/azure-durable-functions). Durable Functions was barely out of beta. I had a disclaimer in the post saying "not production ready." I showed code samples with `OrchestrationTrigger` and `ActivityTrigger`, explained the checkpoint-and-replay model, even [published a sample on GitHub](https://github.com/tamirdresher/azure-functions-durable-extension/blob/master/samples/precompiled/HelloSequence.cs). I thought: *this is the future of distributed workflows*.

Then I moved to Payoneer.

If you've never worked in fintech at scale, let me paint the picture. We were running **hundreds of thousands of concurrent payment workflows**. Multi-step flows that needed to fan out across microservices, retry on transient failures, survive process crashes, and maintain perfect idempotency because you can't accidentally charge someone twice. Reliability wasn't a feature. It was oxygen.

We needed a workflow engine. We evaluated options. We ended up going deep on **Netflix Conductor** — and I mean *deep*. Custom worker SDKs. Redis fsync tuning. Queue starvation debugging. We built a disaster recovery setup with site-aware workers. We hit scaling limits that forced us to stop indexing tasks because Elasticsearch couldn't keep up. My colleague Amir Popovich [wrote up the whole journey](https://engineering.payoneer.com/our-journey-making-netflix-conductor-production-ready-for-our-platform-608d2a192035), and [I shared it publicly because I was genuinely proud of what we'd built](https://www.linkedin.com/posts/tamirdresher_when-our-platform-met-conductor-activity-7145037540994043904-GAG2). (I also [talked about it on a podcast](https://open.spotify.com/episode/1WMLngV43KELbIuTH5zbQL), if you prefer Hebrew.)

Conductor was the right call. DSL-based, language-agnostic, proven at Netflix scale. It worked.

But here's the thing that makes me laugh now: while I was tuning Redis persistence modes and writing custom event bridges and debugging why a single slow HTTP Task response would starve an entire queue — **the technology I wrote about in 2017 was quietly growing up**.

The Durable Task Framework evolved from a beta curiosity into a standalone SDK. First-class support for .NET, Python, Java, JavaScript. Battle-tested at Microsoft scale. And now? Microsoft launched the **Durable Task Scheduler** as a fully managed Azure service — and the same engine is [powering AI agent orchestrations](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) in the **Microsoft Agent Framework**. Because of course it is.

It solves **exactly** the problems I spent months wrestling with at Payoneer. The queue starvation? Built-in activity queues per task type. The Redis memory footprint from storing workflow definitions in every instance? Managed state. The idempotency concerns? Checkpointing model handles it. The worker SDK complexity? Just write C# that looks like regular async code.

Full circle. Cosmic joke. Pick your metaphor.

And here's the weirdest part: **almost nobody knows this exists.**

I talk to .NET developers all the time. They know Azure Functions. They've heard of Durable Functions. But mention "Durable Task Framework" or "Durable Task Scheduler" and I get blank stares. Which is *wild*, because this is the exact same engine powering Durable Functions under the hood. It's open source. It's battle-tested at massive scale. It solves problems that every distributed system eventually faces.

So let me tell you about the best framework and Azure service you're probably not using.

---

## The Problem: Workflows Are Hard

Let's start with a real scenario. You're building an order processing system. When a customer places an order, you need to:

1. **Charge their credit card**
2. **Reserve inventory**
3. **Send a confirmation email**
4. **Wait 30 minutes** (in case they cancel)
5. **If not canceled, ship the order**
6. **Send a shipping notification**

This seems simple, right? Until you think about what happens when things go wrong:

- What if the email service is down?
- What if your app crashes between step 3 and 4?
- What if the customer cancels during the 30-minute wait?
- What if the database connection drops after reserving inventory but before charging the card?

Suddenly, you're writing retry logic, checkpointing state, handling timeouts, and building compensation workflows (rolling back inventory if payment fails). You've turned a simple business process into a distributed systems nightmare.

Here's what this looks like with **Hangfire**:

```csharp
// Step 1: Queue the first job
BackgroundJob.Enqueue(() => ChargeCard(orderId));

// Step 2: You need to remember to queue the next step after the first succeeds
public void ChargeCard(int orderId)
{
    // Charge the card
    PaymentService.Charge(order);
    
    // Now what? Queue the next job manually
    BackgroundJob.Enqueue(() => ReserveInventory(orderId));
}

// Step 3: Keep chaining...
public void ReserveInventory(int orderId)
{
    InventoryService.Reserve(order);
    
    // Queue the next step
    BackgroundJob.Enqueue(() => SendEmail(orderId));
}

// You get the idea. And we haven't even handled failures yet.
```

This is fine for simple jobs. But for a multi-step workflow with waits, retries, and error handling? You end up with spaghetti. Each step is a separate job. State is stored in your database. You're manually tracking where you are in the flow.

---

## The Solution: Write Workflows Like They're Just Code

Here's the same workflow with the **Durable Task Framework**:

```csharp
[Function("OrderOrchestrator")]
public async Task RunOrderWorkflow(
    [OrchestrationTrigger] TaskOrchestrationContext context)
{
    var orderId = context.GetInput<int>();
    
    // Step 1: Charge the card
    await context.CallActivityAsync("ChargeCard", orderId);
    
    // Step 2: Reserve inventory
    await context.CallActivityAsync("ReserveInventory", orderId);
    
    // Step 3: Send confirmation email
    await context.CallActivityAsync("SendEmail", orderId);
    
    // Step 4: Wait 30 minutes
    await context.CreateTimer(context.CurrentUtcDateTime.AddMinutes(30));
    
    // Step 5: Check if canceled
    var isCanceled = await context.CallActivityAsync<bool>("CheckCancellation", orderId);
    
    if (!isCanceled)
    {
        // Step 6: Ship the order
        await context.CallActivityAsync("ShipOrder", orderId);
        
        // Step 7: Send shipping notification
        await context.CallActivityAsync("SendShippingEmail", orderId);
    }
}
```

That's it. **That's the whole orchestration.**

Notice what's missing:
- No manual state management
- No queue juggling
- No "remember to queue the next step" comments
- No distributed locking to prevent duplicate runs
- No custom retry logic (it's built in)

The orchestration is **declarative**. You write it like synchronous code, and the framework handles all the hard parts:

- **Checkpointing**: After each `await`, the framework saves state. If your app crashes and restarts, it picks up exactly where it left off.
- **Retries**: If an activity fails, the framework automatically retries it (with configurable backoff).
- **Durability**: The orchestration can run for hours, days, or weeks. The framework doesn't care.
- **Versioning**: You can update orchestrations while they're running. Old instances continue with the old code; new instances use the new code.
- **External Events**: Your orchestration can wait for external signals (like a user clicking "cancel") using `WaitForExternalEvent`.

---

## What Makes This Different?

I know what you're thinking. "Tamir, this just looks like Durable Functions with extra steps. Why would I use the Durable Task Framework directly?"

Great question. Here's the thing: **Durable Functions IS built on the Durable Task Framework**. When you write a Durable Function, you're using the framework under the hood. But there are scenarios where you want the framework without the Azure Functions runtime:

### Use Durable Functions When:
- You want serverless, pay-per-execution pricing
- You want built-in triggers (HTTP, Queue, Timer, Event Grid)
- You want automatic scaling with zero infrastructure management
- You're building cloud-first, Azure-native apps

### Use Durable Task Framework (the SDK) When:
- You're running on Kubernetes, VMs, or on-premises
- You need complete control over hosting and scaling
- You're building a hybrid or multi-cloud solution
- You have an existing .NET app and want to add workflow orchestration without Azure Functions
- You're building AI agent systems that need durable state management (yes, [the Microsoft Agent Framework does exactly this](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions))

The framework is **open source** (https://github.com/Azure/durabletask). You can run it anywhere. You can use Azure Storage, SQL Server, or the new **Durable Task Scheduler** as the backend.

---

## Enter the Durable Task Scheduler: The Missing Piece

Here's where it gets really good. Microsoft recently launched the **Durable Task Scheduler** as a fully managed Azure service. Think of it as the orchestration engine extracted into its own service.

Before, if you wanted to run orchestrations, you had two choices:
1. **Azure Functions** (managed, but tightly coupled to Functions runtime)
2. **Self-hosted** (flexible, but you manage storage, scaling, monitoring)

Now there's a third option: **Durable Task Scheduler**.

It's a managed backend that handles:
- State persistence (no need to configure storage accounts)
- Automatic scaling (handles millions of orchestrations)
- Monitoring and diagnostics (built-in dashboards)
- Fault tolerance (orchestrations survive failures)

You write code against the Durable Task SDK, point it at the Durable Task Scheduler, and you get all the benefits of a managed service without being locked into Azure Functions.

Here's what that looks like:

```csharp
var builder = new HostBuilder()
    .ConfigureTaskHubWorker((context, builder) =>
    {
        builder.UseDurableTaskScheduler(options =>
        {
            options.ResourceName = "my-task-scheduler";
            options.ConnectionString = "..."; // From Azure Portal
        });
        
        builder.AddOrchestrator<OrderOrchestrator>();
        builder.AddActivity<ChargeCardActivity>();
        builder.AddActivity<ReserveInventoryActivity>();
        // ... other activities
    });

var host = builder.Build();
await host.RunAsync();
```

Your orchestrations run in your container, VM, or Kubernetes cluster. The state, scheduling, and reliability? All managed by Azure. You get the best of both worlds.

---

## The Demo: What I'd Put in a Repo

If I were to create a demo repo for this (and I might!), here's what it would contain:

### 1. **Basic Orchestration Example**
A simple "Hello, World" orchestration showing the fundamentals:
- Orchestrator calling activities
- Built-in retries
- Durable timers

### 2. **Fan-Out/Fan-In Pattern**
A classic pattern where you parallelize work and wait for all results:

```csharp
[Function("ProcessBatchOrchestrator")]
public async Task ProcessBatch(
    [OrchestrationTrigger] TaskOrchestrationContext context)
{
    var items = context.GetInput<List<int>>();
    
    // Fan-out: Process all items in parallel
    var tasks = items.Select(item => 
        context.CallActivityAsync<string>("ProcessItem", item)
    );
    
    // Fan-in: Wait for all to complete
    var results = await Task.WhenAll(tasks);
    
    return results;
}
```

This runs all the activities in parallel (subject to concurrency limits) and waits for all of them to finish. Try doing that with Hangfire without building your own coordination logic.

### 3. **Human-in-the-Loop Pattern**
An orchestration that waits for human approval:

```csharp
[Function("ApprovalOrchestrator")]
public async Task RunApproval(
    [OrchestrationTrigger] TaskOrchestrationContext context)
{
    var request = context.GetInput<ApprovalRequest>();
    
    // Send approval email
    await context.CallActivityAsync("SendApprovalEmail", request);
    
    // Wait for approval event (with 48-hour timeout)
    var approvalTask = context.WaitForExternalEvent<bool>("ApprovalResponse");
    var timeoutTask = context.CreateTimer(context.CurrentUtcDateTime.AddHours(48));
    
    var winner = await Task.WhenAny(approvalTask, timeoutTask);
    
    if (winner == approvalTask)
    {
        var approved = await approvalTask;
        if (approved)
        {
            await context.CallActivityAsync("ProcessApprovedRequest", request);
        }
        else
        {
            await context.CallActivityAsync("RejectRequest", request);
        }
    }
    else
    {
        // Timeout - auto-reject
        await context.CallActivityAsync("AutoRejectRequest", request);
    }
}
```

The orchestration can literally wait for days for a user to click a button. The framework doesn't care. It checkpoints, sleeps, and resumes when the event arrives.

### 4. **Comparison to Alternatives**
A side-by-side comparison showing the same workflow implemented with:
- Hangfire (manual state, queuing, retry logic)
- Quartz.NET (cron-based, not workflow-friendly)
- Durable Task Framework (clean, declarative)

### 5. **Deployment Examples**
How to run this on:
- Azure Functions (serverless)
- Azure Container Apps (containers with the Durable Task Scheduler backend)
- Kubernetes (self-hosted with SQL or Azure Storage backend)

---

## Why Isn't Everyone Using This?

Good question. I think it's a combination of factors:

1. **Naming Confusion**: "Durable Functions," "Durable Task Framework," "Durable Task Scheduler" — people think they're all the same thing or don't understand the differences.

2. **Hidden in Plain Sight**: Most developers encounter Durable Functions first and assume that's the only way to use this pattern. They don't realize the underlying framework is available independently.

3. **Perceived Complexity**: The async/await orchestration model looks weird the first time you see it. "Wait, I can just `await` a 30-minute timer? That doesn't make sense!" (It does. It's brilliant.)

4. **Documentation Fragmentation**: Microsoft's docs are getting better, but there's still a lot of "if you want X, read this doc; if you want Y, read that doc; if you want Z, good luck."

But once you get past these hurdles, this is **the** way to build reliable workflows in .NET. It's not just for Azure. It's not just for serverless. It's a general-purpose orchestration framework that happens to have a world-class managed backend option.

---

## The Honest Reality

This isn't a silver bullet. There are scenarios where Hangfire or Quartz.NET is still the right choice:

- **Use Hangfire if**: You need simple fire-and-forget jobs with a nice dashboard, and you're okay with your database as a queue.
- **Use Quartz.NET if**: You need complex cron scheduling, enterprise clustering, and precise timing guarantees.
- **Use Durable Task Framework if**: You need workflows — multi-step processes with state, retries, compensation, external events, or anything that could run longer than a few minutes.

But if you're building a system where you're manually stitching together background jobs into workflows, tracking state in your database, and writing custom retry logic? You're reinventing the Durable Task Framework. Stop. Use the thing that's already built and battle-tested.

---

## Getting Started

Here's the fastest path to trying this out:

### 1. **Start with Durable Functions** (easiest)
If you're new to this, start with Durable Functions. It's the fastest way to see the orchestration model in action:

```bash
# Create a new Durable Functions app
func init MyDurableFunctionsApp --worker-runtime dotnet-isolated
cd MyDurableFunctionsApp
func new --template "Durable Functions orchestration" --name OrderWorkflow

# Run it locally
func start
```

Microsoft's [Durable Functions quickstart](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-create-first-csharp) is excellent.

### 2. **Try the Durable Task SDK** (for self-hosting)
If you want to run outside Azure Functions, check out the [Durable Task SDK samples](https://github.com/Azure/durabletask):

```bash
git clone https://github.com/Azure/durabletask.git
cd durabletask/samples
dotnet run
```

### 3. **Explore Durable Task Scheduler** (managed backend)
The Durable Task Scheduler is in GA for dedicated SKU and public preview for consumption SKU. Check out the [official docs](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-task-scheduler/durable-task-scheduler) for setup instructions.

---

## Where I See This Fitting

Having lived through building a production Conductor deployment at Payoneer — tuning Redis persistence, debugging queue starvation, writing custom worker SDKs for hundreds of thousands of concurrent workflows — I can tell you exactly where the Durable Task Framework shines:

1. **Multi-step payment processing**: The same fan-out patterns, the same retry semantics, the same survival guarantees we needed at Payoneer. Except instead of learning a DSL and maintaining separate workflow definitions, you write it as plain C# that looks like regular async code.

2. **Fan-out/fan-in at scale**: What we built with custom worker SDKs and bulk processing logic becomes 50 lines of orchestration code. The coordination that required careful queue management? Built in.

3. **Human-in-the-loop workflows**: Orchestrations that wait for approval with timeout escalations — a first-class pattern. The framework doesn't care if it waits five minutes or five days. No queue starvation debugging required.

4. **AI agent orchestration**: This is the one that broke my brain a little. The **[Microsoft Agent Framework](https://github.com/microsoft/agent-framework)** has a [durable task extension](https://learn.microsoft.com/en-us/agent-framework/integrations/azure-functions) for building stateful AI agents and multi-agent workflows. Same checkpointing. Same fault tolerance. Same scaling patterns. The technology I used for "don't accidentally charge someone twice" now solves "don't lose your AI agent's reasoning mid-conversation." I wrote about this framework in 2017. I built workflow orchestration at Payoneer. And now the same underlying tech is coordinating AI agents. The cosmic joke keeps getting funnier.

If I were starting that Payoneer project today with a .NET stack? I'd absolutely evaluate the Durable Task Framework with the Scheduler backend. The code-first approach maps to how .NET developers already think. And I wouldn't have to tune Redis fsync intervals at 2 AM.

---

## The Bottom Line

If you're building distributed systems in .NET, you need to know about the Durable Task Framework and Durable Task Scheduler. It's not a niche tool. It's not just for Azure Functions. It's a fundamental pattern for reliable workflows that happens to have first-class support in Azure.

Stop manually building orchestrations with job queues and database tables. Stop writing custom retry logic. Stop reinventing the wheel.

Use the framework that Microsoft built, open-sourced, and uses internally at scale. It's excellent. It's underrated. And you're probably not using it.

---

**Want to dive deeper?** Here are the resources I wish someone had handed me earlier:

- [What is Durable Task? (Official Docs)](https://learn.microsoft.com/en-us/azure/azure-functions/durable/what-is-durable-task)
- [Durable Task Framework GitHub](https://github.com/Azure/durabletask)
- [Durable Task Scheduler Docs](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-task-scheduler/durable-task-scheduler)
- [Durable Functions Patterns](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview?tabs=in-process%2Cnodejs-v3%2Cv1-model&pivots=csharp)

If you're already using this and I've missed something important, or if you have your own workflow orchestration war stories (Conductor, Temporal, Hangfire, home-grown state machines — I've seen them all), I'd love to hear them. Find me on [Twitter/X](https://twitter.com/tamirdresher) or [LinkedIn](https://www.linkedin.com/in/tamirdresher).

Now go build something durable. 🚀

---
