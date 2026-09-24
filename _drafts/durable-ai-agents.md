---
layout: post
title: "Durable AI Agents: Remembering the Conversation Is Not Enough"
tags: [dotnet, ai-agents, agent-framework, durable-task-scheduler, orchestration]
---

In [the first post][first-post], we followed what happens when an orchestration awaits an activity. In [the previous post][previous-post], we looked at changing the workers and implementations around a running workflow, and recovering an eligible failed instance. I ended with AI agents, because that is where the difference between remembering a conversation and remembering completed work becomes particularly interesting.

Suppose two agents are reviewing a proposed software change. One checks the design. Another checks failure and recovery risks. An editor will combine their reviews, and a human will decide whether to approve the result.

The design reviewer finishes. The risk reviewer is still working. Then the process coordinating them disappears.

What should happen when it comes back?

I want the design review we already paid for, not another interpretation of the same proposal. I want the risk review to remain pending, not disappear from the plan. And I definitely don't want "the model sounded positive" to become the human approval.

The restart should not become a second design meeting. We already have enough of those.

**Remembering the conversation is not the same as remembering which work completed.** That is the distinction I want to follow through this post: what a durable agent invocation preserves, where recovery stops, and why those boundaries matter more when several agents work together.

## Three specialists, one piece of work

Let's keep the workflow concrete. Our input is a proposal, not an open ended instruction to improve the entire company.

The design reviewer receives that proposal and returns a design review. The risk reviewer receives the same proposal and returns a review of failure and recovery concerns. They can work independently. The editor receives those two explicit results and returns a combined review note. Only then does the controller wait for a human decision.

The **controller** owns the order of work. The agents supply judgments within that order. The human decision is a separate input, not text extracted from an agent response.

This is a useful division even when none of the agents calls an external tool. Asking the same model again can produce a different answer and another bill. Once tools can create tickets, change configuration, or submit a payment, repeating work is no longer just a question of consistent wording.

For a multiagent system such as [Squad][squad], the same architectural question applies: how do we distinguish a specialist's completed work from a conversation that merely mentions it? This does not mean Squad automatically uses Durable Task Scheduler. It means coordinating several agents gives us more places where one branch has finished and another has not.

Nor does this mean an ordinary Microsoft Agent Framework agent cannot persist a conversation. It can use persisted or service owned history. Conversation persistence and recoverable workflow execution solve different problems.

## Put the durable boundary in the right place

Before the code, here are the roles in the [durable Agent Framework integration][durable-agent].

The controller gets a **durable agent reference**. Calling that reference asks for an operation on an **agent session entity**. The entity runs the registered agent, which calls the model and any ordinary tools it has been given. Those roles can share a worker process; they are not a requirement for four deployments.

In the implementation used here, `TaskOrchestrationContext.GetAgent(...)` returns a `DurableAIAgent`. Its `RunCoreAsync` calls `context.Entities.CallEntityAsync<AgentResponse>(...)` with the session identity and the operation name `"Run"`. The controller is scheduling an entity operation, not opening an HTTP connection to the model from replaying orchestrator code.

The [entity operation][entity] supplies retained conversation messages to the underlying agent, consumes its response, updates its conversation state, and returns the complete response. Once the successful call result is recorded for the controller, a later replay can use it.

The important unit here is **the agent invocation**. It is not automatically every model request, every tool call, or every streamed token inside that invocation.

Read the following sequence from top to bottom. The optional tool exchange happens inside the agent operation, before its full outcome is recorded. The two controller activation bars are separate passes; no controller invocation stays alive across the wait. Click to enlarge.

[![Sequence showing a controller scheduling an agent entity operation, the agent calling a model and optionally an ordinary tool, and a later controller pass using the recorded full response. Interruption before durable completion can repeat model or tool work.](/assets/durable-ai-agents/agent-invocation-boundary.svg)](/assets/durable-ai-agents/agent-invocation-boundary.svg)

*Figure 1. The durable boundary surrounds the agent operation, not each internal model or tool exchange. Arrows describe the public scheduling and completion contract, not a network trace or a transaction spanning the model service and external tools.*

Now move the failure across that boundary.

If the model has answered but the agent operation has not durably committed its outcome, a subsequent attempt can call the model again. The answer might differ. Seeing streamed text is not proof that the full invocation is durably complete.

If an ordinary tool has already changed an external system, that change does not vanish when the agent operation loses its outcome. A later attempt may reach the tool again. An appropriate business operation key, honored by the destination, can support deduplication. Some integrations instead need reconciliation or compensation. Tool authorization still belongs in the application.

If the successful agent response **has** been recorded for the controller, losing the controller's worker is different. Replay can supply that response without asking the agent to produce it again just because the controller restarted.

That is the same distinction we followed with activities in the first post, but at a boundary that may contain several model and tool exchanges. A durable agent does not imply exactly once inference or exactly once external effects.

### A long tool needs an explicit boundary too

What if an agent needs to request work that takes hours?

The public [`DurableAgentContext.ScheduleNewOrchestration(...)` API][agent-context] lets a tool explicitly request a separate workflow. The [long running tool sample][long-tools] uses that pattern. The scheduling request participates in the entity operation's durable state and outgoing work commit; an arbitrary external write performed by a tool does not.

This gives the long operation its own workflow boundary rather than relying on an ordinary tool call remaining suspended for days. It does not retrofit every tool with internal checkpoints.

## "Memory" is doing too much work in this conversation

Our design reviewer has a conversation. Our controller has an execution history. Those are already two different things.

| State | The question it answers |
| :--- | :--- |
| Workflow execution history | Which durable operations were requested, and which outcomes can the controller use when reconstructing progress? |
| Conversation history | Which messages should the agent or model receive as context for another turn? |
| Session or provider continuation | Which logical conversation are we continuing, and what identity or opaque provider state does it require? |
| Semantic memory | Which facts, summaries, or retrieved knowledge should the application bring into a future prompt? |

These can support one another. They are not interchangeable.

A transcript containing "the design review is finished" is not the controller's durable completion record. A retrieved summary can help the next review, but it is not a receipt for a tool effect. And neither a session handle nor a serialized conversation is a snapshot of the model's hidden inference state.

There is a version specific detail worth understanding here. In the published preview used below, the [agent entity][entity] creates an inner agent session for an operation and supplies retained messages. That does not prove it restores every provider's native opaque session state. Serializing the outer [`DurableAgentSession` handle][session] is not the same operation as restoring all of the underlying agent's continuation state.

We'll return to that distinction in the work in progress section. First, let's use the published integration for our three specialists.

## A preview package, with a concrete workflow

This example uses **`Microsoft.Agents.AI.DurableTask` version `1.16.0-preview.260730.1`**, from the [Agent Framework .NET 1.16.0 release generation][framework-release]. The durable integration is preview. The Azure OpenAI dependency below is also a beta; the stable Agent Framework version does not change either of those statuses.

The package versions follow that generation's [release metadata][released-version] and [dependency definitions][released-deps]:

| Component | Version |
| :--- | :--- |
| Target framework | `net10.0`, with nullable and implicit usings enabled |
| `Microsoft.Agents.AI.DurableTask` | `1.16.0-preview.260730.1` |
| `Microsoft.Agents.AI.OpenAI` | `1.16.0` |
| `Microsoft.DurableTask.Client.AzureManaged` | `1.18.0` |
| `Microsoft.DurableTask.Worker.AzureManaged` | `1.18.0` |
| `Azure.AI.OpenAI` | `2.9.0-beta.1` |
| `Azure.Identity` | `1.21.0` |
| `Microsoft.Extensions.Hosting` | `10.0.1` |

Notice the Durable Task dependency version. I'm not mixing the previous post's SDK 1.26.0 configuration APIs into this example.

The code combines the public [concurrent agent][concurrency-sample] and [human decision][hitl-sample] patterns in a plain C# orchestration. It is a source checked teaching example, not a compiled or executed demonstration. It returns a review and a decision. It does not deploy anything, publish anything, or report a made up successful tool effect.

The application needs an Azure OpenAI **service endpoint**, a compatible chat model deployment, and a DTS task hub. A Foundry project URL is not the service endpoint expected here. All workers and client calls below use the same task hub.

### Configure the agents outside the controller

Start `Program.cs` with these imports and configuration. The configuration keys are application choices. Their environment variable forms are `AzureOpenAI__Endpoint`, `AzureOpenAI__Deployment`, and `DurableTask__ConnectionString`.

```csharp
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.DurableTask;
using Microsoft.DurableTask;
using Microsoft.DurableTask.Client;
using Microsoft.DurableTask.Client.AzureManaged;
using Microsoft.DurableTask.Worker;
using Microsoft.DurableTask.Worker.AzureManaged;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using OpenAI.Chat;

HostApplicationBuilder builder = Host.CreateApplicationBuilder();
string endpoint = Required(builder.Configuration["AzureOpenAI:Endpoint"],
    "AzureOpenAI:Endpoint");
string deployment = Required(builder.Configuration["AzureOpenAI:Deployment"],
    "AzureOpenAI:Deployment");
string connectionString = Required(
    builder.Configuration["DurableTask:ConnectionString"],
    "DurableTask:ConnectionString");
```

The real model client and the three agents are configured here, outside orchestrator code. `DefaultAzureCredential` follows the public samples' development pattern; a deployed application should select its intended identity explicitly.

Continue in `Program.cs`:

```csharp
AzureOpenAIClient modelClient = new(
    new Uri(endpoint), new DefaultAzureCredential());
AIAgent design = modelClient.GetChatClient(deployment).AsAIAgent(
    instructions: "Review the proposed design. State assumptions. Use under 200 words.",
    name: "DesignReviewer");
AIAgent risk = modelClient.GetChatClient(deployment).AsAIAgent(
    instructions: "Review failure and recovery risks. State assumptions. Use under 200 words.",
    name: "RiskReviewer");
AIAgent editor = modelClient.GetChatClient(deployment).AsAIAgent(
    instructions: "Combine the supplied reviews into a review note under 900 characters. Do not approve or execute changes.",
    name: "Editor");

builder.Services.ConfigureDurableAgents(
    options =>
    {
        options.DefaultTimeToLive = TimeSpan.FromDays(7);
        options.AddAIAgent(design).AddAIAgent(risk).AddAIAgent(editor);
    },
    workerBuilder: worker =>
    {
        worker.UseDurableTaskScheduler(connectionString);
        worker.AddTasks(registry =>
            registry.AddOrchestratorFunc<string, ReviewDecision>(
                ProposalReview.Name, ProposalReview.RunAsync));
    },
    clientBuilder: client => client.UseDurableTaskScheduler(connectionString));

using IHost host = builder.Build();
await host.RunAsync();
```

There is one `ConfigureDurableAgents` call, with both the worker and client builders. It registers the three agents and the `ProposalReview` controller defined next. `Build()` creates the host; `RunAsync()` starts it and keeps the worker running.

The explicit global session lifetime is seven days. This is [whole session/entity TTL][released-options], not seven days of guaranteed recoverability for every possible caller. Expiry deletes retained entity state, and the deletion check needs a worker; it is not an exact wall clock deletion promise. A recorded controller result and the entity's live conversation history are separate. A future turn can lose conversational context even though an earlier result remains in the controller's history.

After the top level statements, add the configuration helper:

```csharp
static string Required(string? value, string setting)
    => !string.IsNullOrWhiteSpace(value)
        ? value
        : throw new InvalidOperationException($"Configure {setting}.");
```

### Ask both reviewers, then give the editor their actual results

Add the following declarations after that helper. This is the complete controller and its result types.

```csharp
public sealed record ReviewStatus(string Phase, string Draft);
public sealed record ReviewDecision(bool Approved, string Draft);

public static class ProposalReview
{
    public const string Name = "ProposalReview";
    public const string DecisionEvent = "HumanDecision";
    public const string AwaitingApproval = "AwaitingApproval";

    public static async Task<ReviewDecision> RunAsync(
        TaskOrchestrationContext context, string proposal)
    {
        if (string.IsNullOrWhiteSpace(proposal))
        {
            throw new ArgumentException("A proposal is required.", nameof(proposal));
        }

        DurableAIAgent design = context.GetAgent("DesignReviewer");
        DurableAIAgent risk = context.GetAgent("RiskReviewer");
        AgentSession designSession = await design.CreateSessionAsync();
        AgentSession riskSession = await risk.CreateSessionAsync();

        // Independent sessions allow the two entity operations to overlap.
        Task<AgentResponse> designTask = design.RunAsync(proposal, designSession);
        Task<AgentResponse> riskTask = risk.RunAsync(proposal, riskSession);
        await Task.WhenAll(designTask, riskTask);

        string designText = ReadText(await designTask, maximumLength: 3000);
        string riskText = ReadText(await riskTask, maximumLength: 3000);
        DurableAIAgent editor = context.GetAgent("Editor");
        AgentSession editorSession = await editor.CreateSessionAsync();
        AgentResponse edited = await editor.RunAsync(
            $"Design review:\n{designText}\n\nRisk review:\n{riskText}",
            editorSession);
        string draft = ReadText(edited, maximumLength: 1000);

        context.SetCustomStatus(new ReviewStatus(AwaitingApproval, draft));
        bool approved;
        try
        {
            approved = await context.WaitForExternalEvent<bool>(
                DecisionEvent, timeout: TimeSpan.FromHours(24));
        }
        catch (OperationCanceledException exception)
        {
            throw new TimeoutException("No human decision arrived.", exception);
        }

        context.SetCustomStatus(new ReviewStatus(
            approved ? "Approved" : "Rejected", draft));
        return new ReviewDecision(approved, draft);
    }

    private static string ReadText(AgentResponse response, int maximumLength)
    {
        string? text = response.Text;
        if (string.IsNullOrWhiteSpace(text) || text.Length > maximumLength)
        {
            throw new InvalidOperationException(
                "The agent returned empty or oversized review text.");
        }

        return text;
    }
}
```

Both reviewer calls are started before `Task.WhenAll`. They use **independent durable sessions**: Durable Entities [serialize operations for one entity][entities-doc], so sending two requests to one session would not give us two independently concurrent entity operations.

The [session identity generation][context-extensions] uses the orchestration context's deterministic GUID mechanism. When compatible controller code replays, reconstructing the local session handle does not mean inventing another conversation identity every time.

There is no `Task.Run` around model calls and no direct model I/O in the controller. The durable agent references schedule the work. Normal orchestrator synchronization and replay constraints still apply.

The editor receives the exact reviewer outputs we obtained. It is not being asked to search a chat log and guess which reviews finished. Also, three `RunAsync` calls do not prove there will be exactly three model requests. An agent invocation can contain more than one provider round trip.

The length checks are application limits, not promises that a model follows a word count instruction. An empty or oversized result fails visibly. The small custom status exposes the combined note for inspection; it is not our execution ledger or a general document store.

Finally, the human wait occurs **after** all three agent invocations returned. No model call is being kept active while a person reads the note. The original controller invocation need not remain alive either. That does not make hosting, durable storage, or later processing free.

The 24 hour timeout uses a durable timer. This is not the timer free rewind example from the previous post, and I would not assume the same rewind eligibility.

### Start once, inspect, then send a separate decision

The host above is the worker. To drive it, a separate client process can reuse the configuration and registration code through `builder.Build()`, with the same declarations available. In that client process, **replace** `await host.RunAsync()` with the relevant client operation below; do not start another worker. Code after `await host.RunAsync()` runs when the host shuts down, not while it is serving work.

Resolve the registered client, then schedule a proposal:

```csharp
DurableTaskClient durableClient =
    host.Services.GetRequiredService<DurableTaskClient>();

string instanceId = await durableClient.ScheduleNewOrchestrationInstanceAsync(
    ProposalReview.Name,
    input: "Review a proposal to retry an import when its destination times out.");
Console.WriteLine(instanceId);
```

Keep the returned instance ID. Scheduling is not waiting for the review to finish. In later client invocations, `instanceId` below is that saved ID, and `durableClient` is resolved from the same configuration.

Inspect status and read the note:

```csharp
OrchestrationMetadata state = await durableClient.GetInstanceAsync(
    instanceId, getInputsAndOutputs: true)
    ?? throw new InvalidOperationException("Workflow not found.");
Console.WriteLine(state.RuntimeStatus);
Console.WriteLine(state.SerializedCustomStatus);
if (state.FailureDetails is { } failure)
{
    Console.Error.WriteLine(failure.ErrorMessage);
}
if (state.RuntimeStatus == OrchestrationRuntimeStatus.Completed)
{
    Console.WriteLine(state.SerializedOutput);
}
```

After a human has inspected the note, a decision client can send a Boolean event. In this excerpt, `approved` is the actual human input supplied by that client, not an agent output or a hardcoded automatic approval:

```csharp
OrchestrationMetadata state = await durableClient.GetInstanceAsync(
    instanceId, getInputsAndOutputs: true)
    ?? throw new InvalidOperationException("Workflow not found.");
ReviewStatus? status = state.ReadCustomStatusAs<ReviewStatus>();
if (state.RuntimeStatus != OrchestrationRuntimeStatus.Running
    || status?.Phase != ProposalReview.AwaitingApproval)
{
    throw new InvalidOperationException("Workflow is not awaiting a decision.");
}

await durableClient.RaiseEventAsync(
    instanceId, ProposalReview.DecisionEvent, approved);
```

That status check is useful preflight, not an atomic lock and not authorization. A production decision endpoint must authenticate and authorize the person and correlate their decision to the correct pending review. Accepting the event does not itself prove the workflow has completed; inspect the instance afterward.

If the worker stops, restart the worker. Do not schedule the proposal again and call that recovery. A new workflow request is new work.

## Back to the missing controller

Now return to the failure we started with. The design result has been durably recorded for the controller. The risk reviewer is still working when the controller worker disappears.

A compatible worker can reconstruct the controller's progress. It recreates the durable calls and local handles, and history supplies the recorded design response. The pending risk call remains pending. Controller replay alone is not an instruction to rerun both reviewers.

When the risk response becomes available, the controller can pass both results to the editor. After the editor's result is recorded, the controller reaches the separate human wait.

Read the next sequence as one possible partial completion path, not a required number of physical deliveries. The reviewer columns represent independent agent sessions. The short controller activation bars show separate passes; the human wait has no active agent invocation. Click to enlarge.

[![Sequence showing two independent reviewers starting, a design result being recorded before the controller worker is lost, and a later controller pass using that result while risk remains pending. After risk completes, an editor combines both results. The controller then waits without active agent calls until a human decision event arrives.](/assets/durable-ai-agents/parallel-review-recovery.svg)](/assets/durable-ai-agents/parallel-review-recovery.svg)

*Figure 2. Recover the completed branch, keep the unfinished branch distinct, and wait for a human only after agent work finishes. This conceptual path assumes the risk operation simply remains unfinished; Figure 1 shows the different case where an external call succeeded but durable completion is missing.*

Nothing here asks a model to reconstruct the workflow's status from memory. The model supplies the review. The durable execution protocol supplies the evidence that the invocation completed.

There is a related trap outside orchestrations. The integration's [outside client][outside-client] signals an agent entity and exposes a [handle that polls for its correlated response][run-handle]. Starting another client `RunAsync` with the same prompt is not controller replay, and a repeated prompt is not an idempotency key. When an acknowledgement is uncertain, preserve the operation identity and inspect what happened rather than assuming a new invocation is harmless.

## Work in progress: forgetting context without forgetting completion

This is also where some of my current [public work on the durable extension][delivery-proposal] fits.

**The runtime changes in this section are public, unmerged, and gated. They are not features installed by the published preview used above.** There is a merged schema proposal, but merging a schema does not activate the implementation.

The design problem is straightforward: suppose we stop retaining an old chat message because the conversation has grown. If that message was also the only place a caller could find its result, what does its absence mean?

Did the operation never finish? Did it finish and its response expire? Or are we looking at a different conversation?

In the inspected implementation, outside caller polling [finds correlated responses in retained conversation history][run-handle]. The proposed delivery work separates the **terminal result payload**, which a caller wants to consume, from a **completion receipt**, which establishes that the invocation finished. Neither should depend on where a message sits in the transcript.

That allows a meaningful distinction between "still pending" and "completed, but the result is no longer available." Expiring a payload should not silently convert the latter into permission to run the operation again. The proposed [outcome resolver][outcome-resolver] makes that distinction explicit. The receipts are not immortal: deleting the whole entity removes its entity local completion evidence too.

The related [history and session work][history-proposal] addresses a different question: who owns the conversation, and how does a later invocation continue it? A service owned conversation may need a provider reference and opaque continuation state rather than another copy of its transcript. The proposal uses the underlying agent's session APIs for restoration and serialization; that is more than keeping the outer durable session handle.

Avoiding a mirrored transcript does not mean there is no response content in durable state. Delivery results and conversation ownership are separate concerns, and external provider writes do not become part of the entity's transaction.

Then there is [retention under state pressure][retention-proposal]. The proposed policy can remove eligible transcript content while protecting execution and delivery state. This is not semantic summarization, a retrieval memory system, or a solution for one enormous tool result. If the protected state itself cannot fit, the operation can still fail.

These are different lifetimes: model context, response payload, completion evidence, provider continuation, and the entity itself. Calling all of them "memory" makes a configuration look simpler and the recovery behavior much harder to explain.

**Removing old chat context must not turn completed work into pending work.** That is the design rule connecting these proposals, not a claim that the current preview already implements them.

### Model output is still data

A smaller contribution is already [merged in public source][output-envelope-fix], but is **not included in the July preview package** used in this example.

In the separate Agent Framework workflow graph integration, the dispatcher now wraps agent response text in the executor's output envelope. A response that happens to look like JSON for routed messages, events, or a halt instruction remains result data through that path instead of populating those control fields.

That is a data versus control boundary, not a general prompt injection defense and not tool authorization. Our plain C# example uses the same architectural separation by taking the human decision as an external event, never parsing an approval out of the editor's prose. It does not rely on that later graph dispatcher fix.

## What I want to survive

When one member of an agent workflow finishes before another, I want the coordinator to know which result it has, which work is unfinished, and which external effects may need reconciliation.

I also want to be able to change how much conversation context I retain without accidentally changing the answer to those questions.

Durability does not make a model deterministic. It gives the controller a way to use a recorded outcome instead of requesting another one just because its worker is gone. Where the outcome was not recorded, or a tool already affected the world, we still need to reason about another attempt.

For our review workflow, that means keeping the completed design review, waiting for the risk review, giving the editor the actual results, and leaving approval to the human. Remembering the conversation is useful. Knowing which work completed is what lets the workflow continue.

[first-post]: https://www.tamirdresher.com/blog/2026/09/21/durable-await-replay
[previous-post]: https://github.com/tamirdresher/tamirdresher.github.io/blob/post/durable-task-hidden-capabilities/_posts/2026-09-25-durable-task-hidden-capabilities.md
[squad]: https://github.com/bradygaster/squad
[framework-release]: https://github.com/microsoft/agent-framework/releases/tag/dotnet-1.16.0
[released-version]: https://github.com/microsoft/agent-framework/blob/2aa267e0286b9aab7c491debcca1625752011505/dotnet/nuget/nuget-package.props
[released-deps]: https://github.com/microsoft/agent-framework/blob/2aa267e0286b9aab7c491debcca1625752011505/dotnet/Directory.Packages.props
[released-options]: https://github.com/microsoft/agent-framework/blob/2aa267e0286b9aab7c491debcca1625752011505/dotnet/src/Microsoft.Agents.AI.DurableTask/DurableAgentsOptions.cs
[durable-agent]: https://github.com/microsoft/agent-framework/blob/2aa267e0286b9aab7c491debcca1625752011505/dotnet/src/Microsoft.Agents.AI.DurableTask/DurableAIAgent.cs
[entity]: https://github.com/microsoft/agent-framework/blob/2aa267e0286b9aab7c491debcca1625752011505/dotnet/src/Microsoft.Agents.AI.DurableTask/AgentEntity.cs
[session]: https://github.com/microsoft/agent-framework/blob/2aa267e0286b9aab7c491debcca1625752011505/dotnet/src/Microsoft.Agents.AI.DurableTask/DurableAgentSession.cs
[context-extensions]: https://github.com/microsoft/agent-framework/blob/2aa267e0286b9aab7c491debcca1625752011505/dotnet/src/Microsoft.Agents.AI.DurableTask/TaskOrchestrationContextExtensions.cs
[agent-context]: https://github.com/microsoft/agent-framework-durable-extension/blob/91b540e7b457f8a16a5986b92a49e9b2adbeef47/dotnet/src/Microsoft.Agents.AI.DurableTask/DurableAgentContext.cs
[long-tools]: https://github.com/microsoft/agent-framework-durable-extension/blob/91b540e7b457f8a16a5986b92a49e9b2adbeef47/dotnet/samples/DurableAgents/ConsoleApps/06_LongRunningTools/Program.cs
[entities-doc]: https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-entities
[concurrency-sample]: https://github.com/microsoft/agent-framework-durable-extension/blob/91b540e7b457f8a16a5986b92a49e9b2adbeef47/dotnet/samples/DurableAgents/ConsoleApps/03_AgentOrchestration_Concurrency/Program.cs
[hitl-sample]: https://github.com/microsoft/agent-framework-durable-extension/blob/91b540e7b457f8a16a5986b92a49e9b2adbeef47/dotnet/samples/DurableAgents/ConsoleApps/05_AgentOrchestration_HITL/Program.cs
[outside-client]: https://github.com/microsoft/agent-framework-durable-extension/blob/91b540e7b457f8a16a5986b92a49e9b2adbeef47/dotnet/src/Microsoft.Agents.AI.DurableTask/DefaultDurableAgentClient.cs
[run-handle]: https://github.com/microsoft/agent-framework-durable-extension/blob/91b540e7b457f8a16a5986b92a49e9b2adbeef47/dotnet/src/Microsoft.Agents.AI.DurableTask/AgentRunHandle.cs
[delivery-proposal]: https://github.com/microsoft/agent-framework-durable-extension/pull/94
[outcome-resolver]: https://github.com/microsoft/agent-framework-durable-extension/blob/50832b5a9863f35c06ac2a920e72beacf8afc588/dotnet/src/Microsoft.Agents.AI.DurableTask/State/DurableAgentStateOutcomeResolver.cs
[history-proposal]: https://github.com/microsoft/agent-framework-durable-extension/pull/95
[retention-proposal]: https://github.com/microsoft/agent-framework-durable-extension/pull/97
[output-envelope-fix]: https://github.com/microsoft/agent-framework-durable-extension/pull/101
