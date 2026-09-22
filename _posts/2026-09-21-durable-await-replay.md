---
layout: post
title: "What Actually Happens When a Durable Orchestration Awaits an Activity?"
date: 2026-09-21
tags: [dotnet, durable-task-sdk, durable-task-scheduler, orchestration, workflows]
---

I've written about Durable Task and Durable Task Scheduler (DTS) before, including my [DTS introduction][earlier-post]. I've now joined the Durable Task team under Azure Serverless. It still surprises me how many developers don't really know them, let alone use them. They tackle failure and recovery problems every distributed system has to deal with. Yes, even yours with one microservice and a database.

Plenty of us can quote the fallacies of distributed computing. Quoting them, though, isn't the same as handling the failures they describe in our code. Knowing that the network can fail doesn't tell a workflow halfway through an order what to do when it does. Durable Task helps recover workflow progress. It doesn't solve every problem in a distributed system.

I find the Durable Task Framework fascinating, but I think the apparent "magic" also puts people off. How can an orchestration make progress after its original execution in memory is gone? In this post, I want to go under the hood and show you the secret sauce.

And we can actually look. The [Durable Task Framework/Core][core-source] and [modern .NET SDK][sdk-source] are open source. We'll follow their worker implementation, not the private internals of the managed DTS backend.

I'll follow the **standalone .NET gRPC worker in Durable Task SDK [v1.26.0][sdk-release]**, which [depends on DurableTask.Core 3.9.0][core-pin]. That's the implementation path for this walkthrough, not a claim about every deployed package combination or Azure Functions configuration.

## A small orchestration to follow

Here is the complete orchestration declaration we'll follow, based on the public source. `[DurableTask]` marks the class for the optional generator described below. Activity implementations and registration are omitted; this is a teaching example, not an executed sample.

```csharp
using System.Threading.Tasks;
using Microsoft.DurableTask;

[DurableTask(nameof(OrderFlow))]
public sealed class OrderFlow : TaskOrchestrator<string, string>
{
    public override async Task<string> RunAsync(TaskOrchestrationContext context, string input)
    {
        /* L1 */ string orderId = input;
        /* L2 */ decimal subtotal = await context.CallActivityAsync<decimal>("ReadSubtotal", orderId);
        /* L3 */ decimal total = subtotal + 10m;
        /* L4 */ string receipt = await context.CallActivityAsync<string>("ChargeOrder", new { orderId, total });
        /* L5 */ return receipt;
    }
}
```

If you'd rather avoid strings, the optional [`Microsoft.DurableTask.Generators` package][generator-docs] generates strongly typed helpers for activities and orchestrations defined as classes, including calling sub orchestrations and starting orchestrations. The [SDK's typed example][sdk-source] uses `CallSayHelloTypedAsync` and `ScheduleNewHelloCitiesTypedInstanceAsync`. That example uses Functions, but the generator also supports standalone workers.

The [generated methods][generator-calls] still delegate to `CallActivityAsync`, `CallSubOrchestratorAsync`, or `ScheduleNewOrchestrationInstanceAsync`. They add convenience and type safety at compile time, not a different replay or history model. The generator is [versioned separately and marked as preview in the code we're following][generator-version]; that is not a claim about tested package compatibility or the latest release. I'm keeping the strings here so we can see the scheduling identities.

For the walkthrough, the input is `"order-42"`, `ReadSubtotal` produces `100m`, and `ChargeOrder` produces `"receipt-7"` after receiving a total of `110m`. Those values are illustrative, not measured results.

The extra `10m` gives us a local calculation to track. When a later invocation reaches L3, does it recover a saved `total` variable, or calculate the value again?

It calculates it again. Let's see why.

## Who calls RunAsync, and what happens at await?

Before following the calls, keep **decisions** and **events** separate. A decision, called an action in Core, asks for something next: run `ReadSubtotal` for `"order-42"`. A history event is a stored record of what happened. When that new activity is scheduled, a history event records it. Another records the successful result, `100`. Creating the local action does not itself durably record the request. These are runtime records, not C# events we subscribe to.

Also, our `RunAsync` returns a receipt, not a list of decisions. The worker's runner executes or reconstructs the method against the available history and collects actions through the orchestration context. It returns a result object containing the remaining decisions. During replay, matching recorded schedules removes candidate actions rather than sending them again.

Before L1 can run, some application code has to request an orchestration instance. Here, `client` is an already configured `DurableTaskClient`, connected to the same DTS task hub as a running worker. That worker has `OrderFlow`, `ReadSubtotal`, and `ChargeOrder` registered.

```csharp
string instanceId = await client.ScheduleNewOrchestrationInstanceAsync(
    nameof(OrderFlow), input: "order-42");
```

The [`await` in this starter waits for successful scheduling][client-start] and returns the instance ID. It does not wait for the order to finish, and it does not call `RunAsync` on the starter's call stack. The `[DurableTask]` attribute on our class is a generator marker, not something that starts the method.

**DTS schedules the work. Your worker runs the C#.** The worker receives orchestration work and the available history from DTS. It [looks up the registered orchestrator][worker-execute] to find the code for `OrderFlow`. The starter and worker can be hosted in the same process; these are different roles, not a requirement for separate machines.

Inside the worker, a library runner reads the available history and drives the orchestration forward. Its .NET name is `TaskOrchestrationExecutor`. This is library code inside the worker, not DTS itself or a class you have to write. When it processes the starting `ExecutionStarted` event, [the SDK adapter deserializes the input and calls `RunAsync`][orchestration-invocation] with the context and `"order-42"`. Now L1 runs.

At L2, `CallActivityAsync` [creates a scheduling instruction and a local result task][schedule-task]. The instruction, called an action, says: ask DTS to run `ReadSubtotal` with `"order-42"` as input. The ordinary .NET task is what L2 awaits to get the subtotal. Both exist in worker memory. Creating them does not mean the activity has been dispatched or that DTS has durably recorded the request.

If that result task is incomplete, [ordinary C# `await` yields without blocking its thread][csharp-await]. This pauses the method, not the runner's history processing. An already completed task need not make the method pause.

The runner keeps reading any available history. A completion event later in this same pass can supply a result and let the method continue. A previously recorded schedule can be [matched to the reconstructed instruction][match-schedule] instead of sent again.

After processing the pass's available history, the runner [returns the decisions still outstanding][executor-pass], and the worker [sends them to DTS][worker-response]. For new activity work, those decisions request scheduling. Finishing this response is not finishing the order workflow. One pass can return several decisions; an `await` is not itself a durable checkpoint.

Here is the actual return statement from Durable Task Core's [`TaskOrchestrationExecutor.ExecuteCore`][executor-pass], with the surrounding method omitted. `Actions` holds the remaining decisions collected in its orchestration context:

```csharp
return new OrchestratorExecutionResult
{
    Actions = this.context.OrchestratorActions,
    CustomStatus = this.taskOrchestration.GetStatus(),
};
```

Once a new activity is scheduled, [a separate activity handler in a worker runs it][activity-worker] and [reports its outcome][activity-response]. A recorded outcome can then be supplied as history for another orchestration pass. In the reconstruction path below, `RunAsync` starts again and history resolves the new local task at L2. The activity is not calling back into the old suspended method.

Here's the same flow as a conventional sequence diagram, read from top to bottom. The client gets an instance ID, the first worker pass asks for `ReadSubtotal`, and its recorded result lets a later pass recompute `110m` and ask for `ChargeOrder`.

The columns are roles, not necessarily separate processes. Activation bars on the orchestration worker's lifeline mark separate passes; a later pass may use the same worker process or a different one. Solid arrows show messages or calls, and dashed arrows show replies. This is a conceptual sequence for the reconstruction path, not a network capture or timing trace. The result reaches the later pass through history, not through a callback to the original waiting task.

![Sequence diagram with client, DTS, orchestration worker, and activity handler lifelines. The client receives an instance ID; two orchestration activations schedule ReadSubtotal, use its recorded result 100, recompute 110, and request ChargeOrder.](/assets/durable-await-replay/durable-await-sequence.svg)

*Figure 1. A conceptual sequence from scheduling `OrderFlow` to the next decision for `ChargeOrder`. The two activation bars on the orchestration worker mark separate history passes, not the lifetime of a process. Arrows show causal flow, not measured timing. The DTS lifeline shows its public history and scheduling contract, not an unpublished storage, transaction, or acknowledgement design. Activity results become history; they do not resume the original CLR task.*

## What survives is history, not the suspended method

[DTS keeps each instance's history as part of the task hub's managed state][dts-docs], and a worker receives those records to reconstruct execution. We are describing that contract, not the service's database or storage layout.

For `ReadSubtotal`, two records in our example say:

1. Activity **0**, named `ReadSubtotal`, was scheduled with input `"order-42"`.
2. Activity **0** completed successfully with result **100**.

These are conceptual descriptions, not an exact data format or the whole history. Starting and housekeeping records are omitted. The **0** identifies the activity, not the record's position in history.

The first record tells the runner that this activity was already scheduled. During replay, L2 creates a candidate action again. The runner [matches the record against that action and removes the candidate from its outgoing decisions][match-schedule], rather than scheduling `ReadSubtotal` anew. This record does **not** say the activity finished, and matching it does **not** complete the await. Core represents this scheduling record with the .NET class [`TaskScheduledEvent`][scheduled-event].

The second record supplies the successful outcome. [Processing it provides the result to the reconstructed local task][complete-task], so `RunAsync` can continue. Core represents this completion record with [`TaskCompletedEvent`][completed-event]. Its `TaskScheduledId` is **0** here, connecting the result **100** to the activity that was scheduled.

For this call, the action **requests** `ReadSubtotal`, the history events **record** its scheduling and result, and the `Task` is the local object L2 awaits. Those event classes belong to the runtime's bookkeeping. Application code calls the orchestration and activity APIs; it normally does not construct history objects or raise C# events. DTS preserves history data, while the worker interprets it using local .NET objects.

On reconstruction, L2 assigns the recorded result to a fresh `subtotal` variable as `100m`. L3 calculates `110m` again. The old variable slots and `Task` objects are not restored. That does not mean `110m` can never appear in history: L4 sends it as part of `ChargeOrder`'s input. It can be recorded there as serialized input data, not as a snapshot of every local variable or the suspended CLR stack.

No orchestration thread is parked waiting for the activity. The worker process doesn't have to stop at every await either. Ending a pass through history isn't the same as ending a process.

## Replay, line by line

Let's walk the five lines through three **logical activations**. Here, an activation means one pass in which the worker processes orchestration history and produces decisions.

This simplified trace follows the public source. It is not three measured deliveries or a promise about physical service batches, and housekeeping events are omitted. With no other durable operations in this example, the inspected Core counter assigns activity IDs **0** and **1**. Those IDs correlate actions with scheduled tasks; they are not positions in the event history.

Read each strip from top to bottom: code position on the left, history cursor on the right, and pending decisions, open result tasks, and locals below. A `TaskCompletionSource` is the helper supplying the awaited task's result. These are settled teaching checkpoints based on the public source, not a live debugger recording. Click any strip to open the full SVG and enlarge it.

### A: ask for the subtotal

The starting event supplies the input. L1 reads `"order-42"`. L2 calls `ReadSubtotal`, creating action **0** and an open local task. There is no result yet, so the method yields at L2. L3 through L5 have not executed.

The executor returns the new decision to schedule `ReadSubtotal` with ID 0. Once that decision is accepted, scheduling history records the operation. The activity runs separately and reports its outcome.

Notice what is missing: no durable record of a local variable called `subtotal` with an instruction pointer beside it.

[![Three snapshots: before ExecutionStarted, waiting at L2 with candidate 0 and a pending result task, then returning the new ReadSubtotal schedule.](/assets/durable-await-replay/durable-replay-state-a.svg)](/assets/durable-await-replay/durable-replay-state-a.svg)

*Figure 2A. Activation A. ExecutionStarted reaches L2 and creates candidate 0 plus a pending local result task. The runner returns Schedule 0 after processing available history. The task is not persisted.*

### B: use the subtotal, then ask for the charge

Now the available history includes the scheduled operation and a completion representing `100m`.

The orchestration starts at L1 again. At L2, its code creates a candidate action **0** and another local task. Replay is not simply “look in a dictionary and instantly return a completed task.”

Core's [`HandleTaskScheduledEvent`][match-schedule] matches the recorded scheduling event against the reconstructed action using the sequence ID, action kind, and activity name. It then removes that candidate from the outbound action map.

**Matching the schedule prevents a new scheduling decision; it does not, on its own, supply the result.**

The completion handler uses the recorded activity ID to find its open local task, supplies the serialized result, and then removes the entry. This excerpt from Durable Task Core's [`TaskOrchestrationContext.HandleTaskCompletedEvent`][complete-task] keeps the existence check; the method wrapper and duplicate event branch are omitted:

```csharp
int taskId = completedEvent.TaskScheduledId;
if (this.openTasks.ContainsKey(taskId))
{
    OpenTaskInfo info = this.openTasks[taskId];
    info.Result.SetResult(completedEvent.Result);

    this.openTasks.Remove(taskId);
}
```

The order matters: `SetResult` runs before removal, and the continuation can run inside that call. The snapshots show the settled state afterward.

When the executor processes the completion for ID 0, [`HandleTaskCompletedEvent` sets the reconstructed completion source's result][complete-task]. The async chain can then continue within this same activation, deserialize the value, and assign `subtotal = 100m`. Core's [orchestration synchronization context][sync-context] and [synchronous task scheduler][sync-scheduler] keep those continuations inside this pass through history.

> **Why the context matters.** When an ordinary `await` needs to suspend, a captured `SynchronizationContext` controls how its continuation, the code after that `await`, is scheduled. The runtime [installs its own context][sync-context] and uses [its scheduler][sync-scheduler] to keep that code in the runner's controlled history processing. [`ConfigureAwait(false)` opts out of that capture][constraints-docs] and can escape that path, so don't add it inside orchestrator code. It does not necessarily switch threads on every await.
>
> Keeping this context does not promise the same OS thread or process across activations. Each reconstruction has its own objects and context. Neither normal capture nor `ConfigureAwait(true)` makes `Task.Delay` or HTTP I/O durable. Activities follow ordinary .NET async guidance separately.

L3 calculates `100m + 10m`, producing `110m`. L4 calls `ChargeOrder`, creating the **new** action 1 with `{ orderId, total }`. Its result is not available yet, so the method yields again.

The outstanding decision is now **Schedule 1: `ChargeOrder`**. There is no new Schedule 0 merely because L2 executed again.

[![Four snapshots: replay recreates activity 0, history matches its schedule, the new result 100 recomputes 110 and opens activity 1 at L4, then Schedule 1 is returned.](/assets/durable-await-replay/durable-replay-state-b.svg)](/assets/durable-await-replay/durable-replay-state-b.svg)

*Figure 2B. Activation B. Matching old Schedule 0 removes the candidate, not the task. With IsReplaying already false, completion 0 advances L2, L3 and L4 and computes 110. The runner returns only the new Schedule 1.*

### C: use both recorded operations, then return

With the second activity's result available, the method again starts at L1.

L2 reconstructs action 0; history matches its schedule and supplies `100m`. L3 calculates `110m` again. That is a fresh calculation, not a saved local restored from a checkpoint.

L4 reconstructs action 1. Its recorded scheduling event removes the candidate from the outbound map, and its completion supplies `"receipt-7"`. L5 returns that receipt. The executor can now [emit orchestration completion][finish-orchestration], rather than a new activity schedule.

In this pass, result 0 is replayed past history, while result 1 can be newly arrived history. Neither activity is newly scheduled just because both call sites ran again.

[![Six snapshots: replay rebuilds both awaits, matches their schedules, and recomputes 110. IsReplaying becomes false while L4 still waits. Completion 1 supplies receipt-7; L5 returns and the runner completes the orchestration.](/assets/durable-await-replay/durable-replay-state-c.svg)](/assets/durable-await-replay/durable-replay-state-c.svg)

*Figure 2C. Activation C. Both schedules are matched, and recorded result 100 drives a fresh calculation of 110. Past history ends with L4 still waiting. New completion 1 supplies receipt-7, and the runner emits orchestration completion without scheduling either activity again.*

Zoom in on C. Picture the old history as a row of cards, read oldest first. The **read cursor** moves; the cards stay. [Matching a schedule][match-schedule] removes a candidate action, while [processing its completion][complete-task] resolves the open task. One completion can advance several source lines, and an await can span several events.

![Event cards read oldest first for activation C: the read cursor advances through past positions 1 through 4 while visited cards remain and the unvisited remainder shrinks to zero. IsReplaying then switches to false with activity task 1 still open, before new completion 5 resolves L4 and lets L5 return receipt-7.](/assets/durable-await-replay/durable-replay-history-drain.svg)

*Figure 3. The unvisited PAST remainder shrinks as the cursor advances; visited history stays. Positions 1 through 5 are walkthrough order, not `EventId` or activity IDs. The new completion waits until the past loop finishes. Housekeeping events are omitted.*

Only after the last old card (`TaskScheduled` for activity 1) has been processed does the [executor set `IsReplaying` to `false`, before processing new events][executor-pass]. L4 is still waiting on task 1. The new completion then resolves it, and L5 returns the receipt.

Exhausting past history does not mean every task has finished or every incoming event has been processed. It isn't a general signal of workflow completion, and another activation can replay again.

Now suppose history contains `TaskScheduled(0)` but no completion or failure for it. Replay still matches and removes the candidate scheduling action, but the reconstructed task stays incomplete. **Pending does not mean “schedule it again because we replayed.”** Redelivery of an outstanding activity is a separate delivery concern.

No crash is needed for any of this. In the reconstruction path, normal activity results drive the same processing of history. Replay is part of normal progress, not just recovery.

## Can the runtime keep the local execution around?

Yes. A host can keep useful execution state, depending on its hosting path and configuration.

The standalone gRPC path used above [constructs a new `TaskOrchestrationExecutor`][worker-execute]. A [separate runner used primarily by Azure Functions isolated hosting][functions-runner] has an [extended sessions path that can reuse an executor and process new events][extended-sessions]. Functions also documents [instance caching that varies by provider][caching-docs].

That tells us what those paths can do, not which options a particular deployment enables. The diagrams show reconstruction, not a promise that every host unloads after every await or replays everything for each notification.

Nonblocking also doesn't guarantee immediate garbage collection, process shutdown, scaling to zero, or free waiting. Worker lifetime, caching, and billing are not properties of the C# keyword.

## The code restrictions stop looking arbitrary

These mechanics explain why orchestrator code has to be deterministic.

For a given recorded history, the orchestration must reconstruct compatible durable operations in the required order. If a read of the wall clock, an unseeded random value, or an external response changes which operation comes next, the old history may no longer fit the new execution. Core performs useful matching checks, but that doesn't guarantee it will detect every possible nondeterministic change for you.

For time, use [`context.CurrentUtcDateTime`][context-time] rather than reading the wall clock directly. For a GUID that is safe to replay, use [`context.NewGuid()`][context-guid-log]. Replay safety is the point: `NewGuid()` is not a source of fresh, unpredictable randomness on every replay. If you need an external or independently random value, obtain it through an activity so its result can participate in the recorded history.

The same distinction applies to I/O. Awaiting `HttpClient` directly inside an orchestrator does not turn the HTTP request into a durable activity or record its response for replay. Put that I/O inside an activity. An `HttpClient` used *by the activity implementation* is a different case from an orchestrator awaiting it directly.

For a durable wait, the modern API here is [`context.CreateTimer(...)`][timer-api], with `TimeSpan` or `DateTime` overloads and a cancellation token. Ordinary `Task.Delay` is normally nonblocking, but it is not a durable timer. The [orchestrator code constraints][constraints-docs] follow from this boundary: ordinary async work does not become durable simply because it appears inside an orchestration method.

And then there are logs. L3 can execute more than once, so an ordinary log beside it can appear more than once. [`context.CreateReplaySafeLogger("OrderFlow")`][context-guid-log] returns a logger that [suppresses writes while `IsReplaying` is true][logger-implementation]. That cuts replay noise. It doesn't guarantee that each audit event is recorded exactly once.

Do not “fix” repeated execution by placing durable decisions inside `if (!context.IsReplaying)`. Replay needs to reconstruct those decisions to match the history. Suppressing the log is useful. Suppressing the operation changes the program.

## Replay is not retry

There are three mechanisms worth keeping separate:

1. **Replay of a recorded outcome:** orchestration code executes again and history resolves its reconstructed task. That does not itself request another execution of a successfully recorded activity.
2. **A configured retry after failure:** a recorded failure [faults the reconstructed task][fail-task]. An explicitly configured retry policy or handler can deliberately arrange another attempt; the SDK's [retry branches are explicit][activity-wrapper].
3. **Redelivery of unacknowledged activity work:** the activity execution contract is [at least once][activity-contract]. An activity may execute again when its completion was not durably recorded, even if some external work already happened.

The boundary to watch is inside `ChargeOrder`.

Suppose the payment system accepts the charge for `110m`. Before the activity's completion is durably recorded, its worker fails. The payment system has done something real. The orchestration history does not yet contain a successful result it can replay.

When the activity runs again, it can reach that payment system again. History can recover orchestration progress; it cannot close the gap between **the external effect succeeding** and **the activity outcome being durably recorded**. Using a durable framework doesn't put the payment system and the scheduler in one atomic transaction.

The charge operation still needs idempotency or deduplication at the business level. For example, use a stable key for this particular operation, honored by an integration that supports it. The key must distinguish a duplicate attempt from another legitimate charge.

Now move the failure to after the successful completion has been durably recorded. If worker memory is lost then, replay can supply `"receipt-7"` and advance to L5 without a new scheduling decision for that completed logical activity. That recovers a recorded outcome. It doesn't promise every external effect happened exactly once.

## Back to the debugger

The `await` is still ordinary C#. The framework call creates a decision to perform a durable operation and a local task. History can later match that operation and complete a reconstructed task, letting compatible code calculate its locals and continue.

So when you see L2 or L3 execute again, ask two separate questions: **which source lines are being replayed, and which decisions are actually being emitted?**

That is the secret sauce: the method can keep making progress without keeping its original stack alive. Its activities still have to handle external effects correctly.

[earlier-post]: https://www.tamirdresher.com/blog/2026/04/07/durable-task-scheduler
[core-source]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/README.md
[sdk-source]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/README.md
[generator-docs]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Generators/README.md
[generator-version]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Generators/Generators.csproj#L20-L25
[generator-calls]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Generators/DurableTaskSourceGenerator.cs#L870-L1038
[sdk-release]: https://github.com/microsoft/durabletask-dotnet/releases/tag/v1.26.0
[core-pin]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/Directory.Packages.props#L40-L44
[client-start]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Client/Core/DurableTaskClient.cs
[csharp-await]: https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/await
[activity-wrapper]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Core/Shims/TaskOrchestrationContextWrapper.cs#L127-L203
[schedule-task]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/TaskOrchestrationContext.cs#L126-L148
[executor-pass]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/TaskOrchestrationExecutor.cs#L138-L215
[worker-response]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcDurableTaskWorker.Processor.cs#L892-L902
[dts-docs]: https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler
[scheduled-event]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/History/TaskScheduledEvent.cs#L65-L81
[completed-event]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/History/TaskCompletedEvent.cs#L25-L52
[activity-worker]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcDurableTaskWorker.Processor.cs#L997-L1038
[activity-response]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcDurableTaskWorker.Processor.cs#L1104-L1119
[match-schedule]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/TaskOrchestrationContext.cs#L327-L358
[complete-task]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/TaskOrchestrationContext.cs#L476-L484
[sync-context]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/TaskOrchestrationExecutor.cs#L284-L305
[sync-scheduler]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/SynchronousTaskScheduler.cs#L20-L33
[finish-orchestration]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/TaskOrchestrationContext.cs#L714-L745
[worker-execute]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcDurableTaskWorker.Processor.cs#L840-L869
[orchestration-invocation]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Core/Shims/TaskOrchestrationShim.cs#L59-L85
[functions-runner]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcOrchestrationRunner.cs#L14-L23
[extended-sessions]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcOrchestrationRunner.cs#L145-L206
[caching-docs]: https://learn.microsoft.com/en-us/azure/durable-task/durable-functions/durable-functions-perf-and-scale#instance-caching
[context-time]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/TaskOrchestrationContext.cs#L33-L60
[context-guid-log]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/TaskOrchestrationContext.cs#L444-L472
[timer-api]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/TaskOrchestrationContext.cs#L172-L207
[constraints-docs]: https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-code-constraints
[logger-implementation]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/TaskOrchestrationContext.cs#L536-L546
[fail-task]: https://github.com/Azure/durabletask/blob/af8078ff7073facf5bb6ec8b7ba3beeb7efcf2d8/src/DurableTask.Core/TaskOrchestrationContext.cs#L492-L520
[activity-contract]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/TaskActivity.cs#L41-L52
