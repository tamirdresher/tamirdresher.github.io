---
layout: post
date: 2026-10-29
title: "Run Forever, Keep History Bounded: Recurring Durable Orchestrations"
tags: [azure, durable-functions, durable-task-sdk, orchestration, workflows, performance, dotnet]
---

A team approached me because the performance of one of their orchestrations had dropped. When I looked into it, I found a simple loop that had been running for months and had accumulated millions of history records.

The code kept doing the same thing: reconcile some work, wait, and repeat. The loop stayed small. Its durable history did not.

That is the problem this post is about. A business process can run indefinitely without keeping every cycle in one orchestration generation. `ContinueAsNew` gives the orchestrator a deliberate boundary so subsequent generations start with bounded history.

But it is prevention, not an external compaction command. It only helps when the orchestrator reaches a compatible boundary. It does not trim an already-large live execution from the client side. So there are really two questions:

1. How should a recurring orchestration be written so its history stays bounded?
2. What can you do when production instances already have giant histories?

My earlier [replay walkthrough](https://www.tamirdresher.com/blog/2026/09/21/durable-await-replay) explains why recorded history lets durable code recover, and the follow-up on [less obvious Durable Task capabilities](https://www.tamirdresher.com/blog/2026/09/25/durable-task-hidden-capabilities) covers related execution boundaries. Here, the focus is what happens when useful history becomes too much history.

This is the [eternal orchestration pattern](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-eternal-orchestrations): let the process continue, but give each generation a bounded past. Eternal process. Not an eternal scrapbook.

---

## The Process Can Be Eternal. The Generation Doesn't Have To Be.

Imagine a recurring reconciliation job. It checks a source, applies the next unit of work, records its progress, waits, and checks again.

In these snippets, `Checkpoint` in C# and `checkpoint` in Python are durable, application-owned progress markers. A checkpoint might be a committed sequence number, timestamp plus tie-breaker, or stable business key. A watermark is the same idea: a durable statement that everything through a known position has been reconciled.

That is deliberately different from a source continuation token. Pagination tokens may expire or be valid only for a particular query snapshot. Persisting an orchestration does not extend their validity. The `ReconcileScan` activity below owns source pagination for one finite scan, recognizes when the source has no next page, commits business results idempotently, and returns the next durable checkpoint. Reaching the end of pagination completes that scan; it does not automatically stop the recurring monitor. `Stopped` is reserved for an actual application or user stop decision.

These are teaching snippets, not complete runnable applications: the `ReconcileScan` activity implementation, worker registration, client startup, connection settings, retries, and production error handling are intentionally omitted.

### Standalone Durable Task .NET SDK: one history that keeps growing

```csharp
using Microsoft.DurableTask;
using System;
using System.Threading;
using System.Threading.Tasks;

public sealed record ReconciliationState(
    string? Checkpoint,
    TimeSpan Interval,
    bool Stopped = false);

public sealed record ReconciliationResult(
    string? NextCheckpoint,
    bool Stopped);

public sealed class UnboundedReconciliation
    : TaskOrchestrator<ReconciliationState, ReconciliationState>
{
    public override async Task<ReconciliationState> RunAsync(
        TaskOrchestrationContext context,
        ReconciliationState state)
    {
        // This one execution repeats, so every activity and timer stays in the same growing history.
        while (!state.Stopped)
        {
            // Application activity: finish one finite source scan, including its transient
            // pagination, and return only a committed application checkpoint.
            ReconciliationResult scan =
                await context.CallActivityAsync<ReconciliationResult>(
                    "ReconcileScan",
                    state.Checkpoint);

            state = state with
            {
                Checkpoint = scan.NextCheckpoint,
                Stopped = scan.Stopped,
            };

            if (!state.Stopped)
            {
                // Use orchestration time to create a replay-safe durable wait.
                DateTime nextCheck =
                    context.CurrentUtcDateTime.Add(state.Interval);
                await context.CreateTimer(
                    nextCheck,
                    CancellationToken.None);
            }
        }

        return state;
    }
}
```

### Standalone Durable Task Python SDK: the same unbounded loop

```python
from collections.abc import Generator
from datetime import timedelta
from typing import Any

from durabletask import task


def unbounded_reconciliation(
    ctx: task.OrchestrationContext,
    state: dict[str, Any],
) -> Generator[task.Task[Any], Any, dict[str, Any]]:
    # This one execution repeats, so every activity and timer stays in the same growing history.
    while not state["stopped"]:
        # Application activity: finish one finite source scan, including its transient
        # pagination, and return only a committed application checkpoint.
        scan = yield ctx.call_activity(
            "ReconcileScan",
            input=state.get("checkpoint"),
        )

        state = {
            "checkpoint": scan["next_checkpoint"],
            "interval_seconds": state["interval_seconds"],
            "stopped": scan["stopped"],
        }

        if not state["stopped"]:
            # Use orchestration time to create a replay-safe durable wait.
            next_check = ctx.current_utc_datetime + timedelta(
                seconds=state["interval_seconds"]
            )
            yield ctx.create_timer(next_check)

    return state
```

The C# example follows the public [`TaskOrchestrationContext` API](https://github.com/microsoft/durabletask-dotnet/blob/2a409da4ac7dcf03c4f25985337eb4623ea6394e/src/Abstractions/TaskOrchestrationContext.cs), and the Python example follows the standalone [`OrchestrationContext` API](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/task.py). Python orchestrators are generators: durable operations are yielded, not awaited with `async`/`await`.

If you want the mechanics behind history and reconstruction, I covered them in [what actually happens at a durable await](https://www.tamirdresher.com/blog/2026/09/21/durable-await-replay). The short version, also described in the [orchestration overview](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-orchestrations#reliability): recorded outcomes let the runtime reconstruct progress without keeping the original method alive.

Here, the question isn't *how* that reconstruction works. It's **how much past work one recurring execution should need to reconstruct**.

Each recurring cycle can add activity scheduling and completion events, timer events, and other durable actions. The [eternal orchestration documentation](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-eternal-orchestrations) warns that an endlessly looping orchestration without continue-as-new accumulates history, eventually causing performance problems and excessive memory use.

[![Illustrative logical history table showing representative activity and timer events accumulating across three recurring cycles while earlier cycles remain recorded.](/assets/recurring-durable-orchestrations/growing-history.svg)](/assets/recurring-durable-orchestrations/growing-history.svg)

*Illustrative logical history, not an actual backend table, dashboard screenshot, complete event sequence, or measured event count. Long idle time by itself does not append rows.*

In the production case that prompted this post, the concrete facts were a performance drop and millions of history records accumulated over months. I don't have a controlled before-and-after measurement that isolates one CPU, latency, or memory number, so I won't invent one. The practical concern is still clear: every recovery or activation may have much more recorded work to reconstruct before the orchestration can make forward progress.

Notice what doesn't fix that: assigning the latest result back to the same local variable. You've replaced the value in your code. You haven't reset the orchestration history.

Also, elapsed time isn't the right proxy. A workflow waiting a long time for one external event is different from a workflow scheduling new durable work repeatedly. Ask **how much history it creates**, not just how old it is.

---

## ContinueAsNew: Same Process, Next Chapter

That's where `ContinueAsNew` comes in.

The [eternal orchestration docs](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-eternal-orchestrations#how-continue-as-new-works) describe a new orchestration generation with new input, the same instance ID, and reset orchestration history. They also describe a new execution ID internally.

For the .NET `Microsoft.DurableTask` API, [`TaskOrchestrationContext.ContinueAsNew`](https://learn.microsoft.com/en-us/dotnet/api/microsoft.durabletask.taskorchestrationcontext.continueasnew?view=durabletask-dotnet-1.x) documents the same essential contract: restart with new input and clear the history used for that execution.

Think of this as a **logical generation boundary**, not "start a random unrelated workflow" and not "reboot the worker."

[![Conceptual comparison showing four cycles accumulating in one execution history without ContinueAsNew and four bounded generations passing compact checkpoints forward with ContinueAsNew.](/assets/recurring-durable-orchestrations/continue-as-new-generations.svg)](/assets/recurring-durable-orchestrations/continue-as-new-generations.svg)

*Illustrative logical generation boundaries. The logical instance ID remains the same; physical storage lifecycle and buffered external-event behavior are separate concerns.*

It's also not a promise about physical deletion, backup retention, or when storage space is reclaimed. A reset of orchestration history is an execution semantic. Storage lifecycle and retention need their own provider-specific documentation and policies.

Here is the same scenario with one completed scan and one completion-relative wait per generation. The activity may use several short-lived source pagination tokens while that scan is active, but the orchestration carries only the committed application checkpoint into the next generation.

The bounded snippets reuse the imports and the `ReconciliationState` and `ReconciliationResult` types defined above.

### Standalone Durable Task .NET SDK: bounded generation

```csharp
public sealed class BoundedReconciliation
    : TaskOrchestrator<ReconciliationState, ReconciliationState>
{
    public override async Task<ReconciliationState> RunAsync(
        TaskOrchestrationContext context,
        ReconciliationState state)
    {
        if (state.Stopped)
        {
            return state;
        }

        // Application activity: complete the finite scan and commit its checkpoint.
        ReconciliationResult scan =
            await context.CallActivityAsync<ReconciliationResult>(
                "ReconcileScan",
                state.Checkpoint);

        // Carry only the application checkpoint, cadence, and stop flag.
        ReconciliationState nextState = state with
        {
            Checkpoint = scan.NextCheckpoint,
            Stopped = scan.Stopped,
        };

        if (nextState.Stopped)
        {
            return nextState;
        }

        // Use orchestration time to create a replay-safe durable wait.
        DateTime nextCheck =
            context.CurrentUtcDateTime.Add(nextState.Interval);
        await context.CreateTimer(nextCheck, CancellationToken.None);

        // Request the next generation only after this scan and wait complete.
        context.ContinueAsNew(nextState);
        // Complete this method immediately after requesting the boundary.
        return nextState;
    }
}
```

### Standalone Durable Task Python SDK: bounded generation

```python
def bounded_reconciliation(
    ctx: task.OrchestrationContext,
    state: dict[str, Any],
) -> Generator[task.Task[Any], Any, dict[str, Any]]:
    if state["stopped"]:
        return state

    # Application activity: complete the finite scan and commit its checkpoint.
    scan = yield ctx.call_activity(
        "ReconcileScan",
        input=state.get("checkpoint"),
    )

    # Carry only the application checkpoint, cadence, and stop flag.
    next_state = {
        "checkpoint": scan["next_checkpoint"],
        "interval_seconds": state["interval_seconds"],
        "stopped": scan["stopped"],
    }

    if next_state["stopped"]:
        return next_state

    # Use orchestration time to create a replay-safe durable wait.
    next_check = ctx.current_utc_datetime + timedelta(
        seconds=next_state["interval_seconds"]
    )
    yield ctx.create_timer(next_check)

    # Request the next generation only after this scan and wait complete.
    ctx.continue_as_new(next_state)
    # End this generator immediately after requesting the boundary.
    return next_state
```

Both versions wait for the activity and timer before rolling over, carry only the state needed by the next generation, and return immediately after continue-as-new. The activity and timer APIs come from the same public SDK surfaces linked above. The .NET repository's [ContinueAsNew integration test](https://github.com/microsoft/durabletask-dotnet/blob/2a409da4ac7dcf03c4f25985337eb4623ea6394e/test/Grpc.IntegrationTests/OrchestrationPatterns.cs#L567-L592) and the Python [`continue_as_new` contract](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/task.py#L391-L411) both show the immediate-return requirement. Registration is omitted; the Python worker exposes [`add_orchestrator` and `add_activity`](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/worker.py#L637-L715), while the .NET worker registers tasks through `AddDurableTaskWorker(...).AddTasks(...)`.

External events need an explicit rollover policy too. In the pinned .NET SDK, [`ContinueAsNewOptions.PreserveUnprocessedEvents`](https://github.com/microsoft/durabletask-dotnet/blob/2a409da4ac7dcf03c4f25985337eb4623ea6394e/src/Abstractions/ContinueAsNewOptions.cs#L11-L27) defaults to `true`; in the pinned Python SDK, [`continue_as_new(..., save_events=False)`](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/task.py#L391-L411) does not carry unprocessed events unless requested. That applies to buffered, unprocessed events, not every signal or task that might be in flight. Do not roll over while required activity results or event-handling work are unresolved. These examples do not wait for a stop event, so `Stopped` changes only when the application activity returns that decision; it does not react automatically to an external signal.

The important bit is the handoff: the next generation starts from the state you've explicitly chosen to preserve. It doesn't need to replay every previous reconciliation cycle to discover that state.

Don't schedule another bit of work afterward and hope it belongs to the next chapter.

I've also covered [using that execution boundary to change workflow versions](https://www.tamirdresher.com/blog/2026/09/25/durable-task-hidden-capabilities). That's a separate capability, with its own backend and compatibility requirements. Here, we need the boundary even when the implementation never changes.

---

## A Fresh Start Doesn't Make Your Input Smaller

In the examples above, the activity completes a finite scan and returns an application-owned checkpoint. The checkpoint says what business progress has been committed. It is not assumed to be a source continuation token.

Inside that activity, a data source may return a continuation token for the next page. The activity follows those tokens until the source reports the end of the scan, then commits a durable checkpoint or watermark. If a token expires or is tied to a query snapshot, the activity follows that source's documented restart and reconciliation policy. Durable orchestration persistence cannot make an expired source token valid again.

A compact next-generation input might look conceptually like this:

```json
{
  "checkpoint": "last-committed-business-position",
  "interval_seconds": 300,
  "stopped": false
}
```

The interval here is only illustrative, not a recommended cadence.

Now imagine that after every scan, the orchestration also appends every processed record and result to a `processed_results` list, then passes that whole object to continue-as-new:

```json
{
  "checkpoint": "last-committed-business-position",
  "interval_seconds": 300,
  "stopped": false,
  "processed_results": [
    "every result from scan 1",
    "every result from scan 2",
    "and so on"
  ]
}
```

`ContinueAsNew` gives the orchestration a fresh execution history. But the object you pass to it becomes the next generation's input. It doesn't remove items from that object or make an ever-growing list smaller.

A better split is to have the activity save detailed results in the application's database or object store, then return only the durable checkpoint and genuinely small state needed for the next cycle. If the orchestration needs to refer to saved details later, it can carry a stable reference rather than the details themselves.

The end of source pagination means "this scan is complete." The recurring monitor can wait and begin another scan according to its application policy. It should not silently treat a null token as both "start over immediately" and "stop forever." Those are different decisions. Likewise, the examples' `Stopped` value is a business stop condition, not a synonym for reaching the last page.

That external data still needs a lifecycle. A referenced object must remain available for as long as the workflow may need it, and the activity writing it still needs the application's usual idempotency and retry design.

Also watch the shape of your "small" state object. Three properties are not small if one of them is a list that grows forever. Resetting history and keeping input bounded are related but separate jobs.

For the Azure Storage provider specifically, the [large-payload guidance](https://learn.microsoft.com/en-us/azure/durable-task/durable-functions/durable-functions-azure-storage-provider#performance-considerations) recommends storing large payloads externally and passing references to avoid repeatedly loading them. Its [history-table documentation](https://learn.microsoft.com/en-us/azure/durable-task/durable-functions/durable-functions-azure-storage-provider#history-table-for-orchestration-events) also explains that this provider loads an instance's history into memory. Those are provider-specific details; the broader design lesson is simply to bound both the history and the next generation's input.

---

## Children Help. They Don't Make the Parent Forget.

Sub-orchestrations are another useful boundary.

The [.NET sub-orchestration API documentation](https://learn.microsoft.com/en-us/dotnet/api/microsoft.durabletask.taskorchestrationcontext.callsuborchestratorasync?view=durabletask-dotnet-1.x) explicitly says a child has its own instance ID, history, and status. It also identifies smaller parent history as a way to reduce memory usage and CPU overhead.

So you can put a multi-step reconciliation cycle inside a child. The parent awaits its result rather than hosting all the child's internal steps in its own history. The [sub-orchestration guide](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-sub-orchestrations) describes the child as behaving like an activity from the caller's perspective: it returns a value or surfaces a failure.

But there's a catch worth saying out loud:

**A parent that calls a new child forever still performs durable work forever.**

The child-call lifecycle and returned result aren't free of parent-side history. Moving the detailed work into children makes that parent history smaller; it doesn't introduce a reset boundary for the parent.

For a recurring controller, a useful composition is bounded child work, a compact result, and a parent that rolls into a new generation at a deliberate boundary. If the child itself recurs indefinitely, it needs its own history-growth analysis.

And keep child outputs small. Returning the entire detailed report to the parent defeats part of the separation. The Azure Storage provider docs explicitly include sub-orchestrator outputs among the payloads stored in orchestration history.

---

## "Recurring" Isn't a Scheduling Requirement

Before deciding how to repeat the workflow, decide what repetition actually means.

The periodic example in the eternal orchestration docs does the work, then waits an interval, then continues as new. That's **completion-relative scheduling**. If the work takes longer, the next start moves later. It naturally serializes the cycles within that orchestration.

That's different from "run at the top of every hour."

For a wall-clock schedule, a timer-triggered starter that launches a finite orchestration may be a better fit. Each scheduled run can have its own instance and bounded history. But you must decide what happens if the previous workflow hasn't finished: overlap, skip, coalesce, or catch up?

There's an important Azure Functions detail here. The [timer trigger reference](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer#scale-out) says the timer won't trigger again while an invocation is still running. That is a guarantee about the **timer-triggered function invocation**.

If that invocation starts an orchestration and returns, the orchestration can still be running when the starter fires again. Preventing overlap between those workflow instances is a separate design problem.

So I wouldn't reduce this decision to "CRON overlaps; durable loops don't." The lifetime of the starter and the lifetime of the work it starts are different things.

Choose a completion-relative durable loop when that cadence and continuity are what you need. Choose separately scheduled finite workflows when those better match the business schedule. Neither choice excuses unexamined history growth inside the workflow.

For a business-cycle example, the [subscription-payment section of my real-world Durable Task post](https://www.tamirdresher.com/blog/2026/09/28/durable-task-real-world#3-a-payment-timeout-is-not-a-decline) advances only after the current cycle is resolved. The useful boundary is a business decision, not just another tick of the clock.

---

## Not Every Record Is "Just Logging"

It's tempting to look at a busy orchestration and say, "Why are we calling an activity just to write a log? Let's remove it." Sometimes that's exactly the right question. But first, what is that activity actually recording?

Take a reconciliation workflow that processes records a page at a time. A message saying "finished processing this page" helps someone diagnose a problem later. Recording that the page was accepted or committed, so the application knows which records still need reconciliation, is doing something else. If business behavior depends on that write, it remains real activity work, even if the activity happens to be named "LogProgress."

Give that write a stable operation or business key, and make the destination idempotent or able to deduplicate writes using that key. The [programming model documentation](https://learn.microsoft.com/en-us/azure/durable-task/common/programming-model-overview#activities) explains why this matters: activity execution is at least once. An external write may succeed before the activity's completion is recorded. If the outcome is uncertain, reconcile it against the destination before retrying the write. For example, check whether that page's acceptance record already exists under the same key rather than assuming a missing completion means nothing was written.

If the output is only diagnostic, an extra durable activity per iteration may be unnecessary. Use documented replay-safe logging where supported instead. The [Durable Functions diagnostics guide](https://learn.microsoft.com/en-us/azure/durable-task/durable-functions/durable-functions-diagnostics#replay-safe-logging-in-orchestrator-functions) covers this, including `CreateReplaySafeLogger` specifically for .NET isolated Durable Functions orchestrators, not standalone SDKs generally.

That replay-safe filtering prevents replay-generated duplicate log messages. It doesn't guarantee delivery or make logs exactly-once business records. Application Insights sampling can lose tracking information too, as the same diagnostics guide warns. That's fine to account for when choosing diagnostic telemetry, but not a reason to replace a required acceptance record with a log message.

Remove unnecessary work, not records your application depends on.

---

## But Mine Already Has a Giant History. Now What?

The bounded design prevents the next instance or generation from repeating the same mistake. It does not compact the production histories that already exist. That second problem needs containment first, then a compatible handoff, drain, retirement, or replacement plan.

### First, contain the load

Before we worked out the long-term repair, we suspended an explicit reviewed list of affected orchestrations and resumed selected groups gradually.

This was temporary containment, not a history fix. Suspension can reduce how many of these orchestrations are actively processing, but it doesn't truncate their histories. Resuming them can bring the same replay cost and any accumulated work back. New starts may need separate gating; suspending existing instances doesn't stop another starter from creating more.

#### Start with the dashboard for a small reviewed set

For a few known instances, the simplest option is the [Durable Task Scheduler dashboard](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler-dashboard). Open the Orchestrations pane, find the instance, select its instance ID, and choose Suspend. After checking containment and business progress, return to each explicitly approved instance and choose Resume.

The dashboard documents these actions for an individual orchestration. Use the reviewed IDs one at a time and verify each resulting status before moving on.

#### You don't need a whole application for an admin task

The standalone Durable Task JavaScript/TypeScript SDK is currently in preview. A short local Node.js script can connect to Azure-managed DTS without deploying a Durable Functions app. The essential control path is small:

```javascript
const state = await client.getOrchestrationState(instanceId, false);

if (action === "suspend") {
    await client.suspendOrchestration(instanceId, "Temporary containment");
} else {
    await client.resumeOrchestration(instanceId, "Approved staged resume");
}
```

The complete companion [`admin-instance.mjs`](https://github.com/tamirdresher/tamirdresher.github.io/blob/tamirdresher-microsoft-recurring-orchestration-draft/assets/recurring-durable-orchestrations/admin-instance.mjs) validates one explicit instance ID and one `suspend` or `resume` action per invocation, checks the current state without fetching payloads, and closes the client. It reads connection configuration from `DURABLE_TASK_SCHEDULER_CONNECTION_STRING`; do not commit or print that value. A control request still needs a separate status readback before the next operational step.

One provenance note for this recovery section: the incident record establishes that supported client operations were applied programmatically to an approved instance list, but it does not preserve the original wrapper or language. The companion scripts are public teaching examples, not reconstructed incident code. They follow the pinned [Azure-managed client creation](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js-azuremanaged/src/client-builder.ts), [client methods](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js/src/client/client.ts), and [plain ESM sample](https://github.com/Azure-Samples/Durable-Task-Scheduler/blob/7152d82c656576b9cda47d33ac2de4f61aacff66/samples/durable-task-sdks/javascript/function-chaining/client.mjs).

For a larger reviewed workload, use the SDK query APIs to build a candidate list before changing anything. In .NET, `GetAllInstancesAsync` with `OrchestrationQuery` can filter by runtime status, creation window, and instance ID prefix, with paged results. Keep `FetchInputsAndOutputs` false when you only need IDs and status. The Python SDK also exposes filtered orchestration queries, although its result and pagination behavior differs, so follow the examples for the client you use. The public [filtered-query guide](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-instance-management#query-orchestration-instances-with-filters) shows the supported filters.

Treat that query as discovery, not authorization. Review the candidates, freeze an explicit approved ID list, and recheck each instance's current status before mutation. Build each resume batch from a separately approved subset. Instances can change while pages are being read, so do not pipe an open-ended query directly into mutation.

#### How do I find the instances with large histories?

The public dashboard and query documentation doesn't expose a largest-history filter. Narrow the candidates metadata-first: use orchestration name or tags in the [Durable Task Scheduler dashboard](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler-dashboard), and runtime status, creation-time window, or instance ID prefix with the JavaScript client's [`getAllInstances`](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js/src/client/client.ts#L810-L1002) query. Keep inputs and outputs disabled during discovery. Age is only a hint, not a measure of history size.

After a human reviews that metadata and freezes a small approved ID list, the read-only call is straightforward:

```javascript
const state = await client.getOrchestrationState(instanceId, false);
const history = state
    ? await client.getOrchestrationHistory(instanceId)
    : null;

console.log({
    InstanceId: instanceId,
    ReturnedHistoryEntries: history?.length ?? null,
});
```

The complete [`history-report.mjs`](https://github.com/tamirdresher/tamirdresher.github.io/blob/tamirdresher-microsoft-recurring-orchestration-draft/assets/recurring-durable-orchestrations/history-report.mjs) handles missing instances and per-ID errors, sorts successful counts, and closes the client. [`getOrchestrationHistory`](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js/src/client/client.ts#L1069-L1163) returns history event objects and returns an empty array when an instance isn't found, which is why the companion checks state first. `ReturnedHistoryEntries` is the number of entries in that returned snapshot, not stored bytes, provider storage size, or a direct replay-work measurement. History may contain sensitive input or output payloads, so keep the list small and reviewed. The dashboard History tab, [.NET `GetOrchestrationHistoryAsync`](https://github.com/microsoft/durabletask-dotnet/blob/2a409da4ac7dcf03c4f25985337eb4623ea6394e/src/Client/Core/DurableTaskClient.cs#L500-L517), and [Python `get_orchestration_history`](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/client.py#L675-L686) are alternatives for the same bounded inspection.

Whatever client you use, recheck status immediately before an action and read it back afterward. Stop on missing or unexpected results. Resume only separately approved subsets, with workload health and business progress checks between them.

### Then, fix the history growth

The code change I want is the bounded C# or Python implementation shown earlier. New instances should start on that implementation and call `ContinueAsNew` after a bounded amount of work. Deploy it with the SDK and backend's supported [orchestration versioning](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-orchestration-versioning) or a drain strategy so workers serving older histories preserve the durable-action sequence those histories expect.

That deployment doesn't rewrite an existing history or move a live execution onto the new loop. `ContinueAsNew` isn't an external "compact this instance" button. The orchestrator has to reach the call itself; a client can't force it from outside, and restarting a worker doesn't erase persisted history.

There is no universal safe retrofit for arbitrary running instances. Adding, removing, or reordering activities, timers, sub-orchestrations, external-event waits, or continuation calls can change replay decisions. A specifically reviewed and tested code change may be replay-compatible with a particular history shape, and an existing compatible control path may provide a safe handoff. This article isn't claiming or test-proving such a migration for every old history. `IsReplaying`, durable time, or a version check alone doesn't make a changed durable-action sequence compatible.

So the practical split is:

* **New instances:** run the bounded C# or Python implementation.
* **Running instances with a verified compatible handoff:** let the old implementation reach that handoff and roll over under the versioning contract you tested.
* **Running instances without one:** keep their compatible old code available while you contain, drain, retire, or replace them deliberately.

#### The actual source change for new executions

The change is small, but it changes the lifecycle. These focused methods reuse the imports, `ReconciliationState`, `ReconciliationResult`, and `ReconcileScan` activity contract from the first half of the post.

In C#, remove the unbounded `while` and make one scan plus one durable wait the complete generation:

```csharp
public override async Task<ReconciliationState> RunAsync(
    TaskOrchestrationContext context,
    ReconciliationState state)
{
    if (state.Stopped)
    {
        return state;
    }

    ReconciliationResult scan =
        await context.CallActivityAsync<ReconciliationResult>(
            "ReconcileScan",
            state.Checkpoint);

    ReconciliationState nextState = state with
    {
        Checkpoint = scan.NextCheckpoint,
        Stopped = scan.Stopped,
    };

    if (nextState.Stopped)
    {
        return nextState;
    }

    DateTime nextCheck =
        context.CurrentUtcDateTime.Add(nextState.Interval);
    await context.CreateTimer(nextCheck, CancellationToken.None);

    // Start a fresh generation with compact, committed state.
    context.ContinueAsNew(nextState);
    return nextState;
}
```

The Python change is the same shape: remove the unbounded `while`, yield one scan and one durable timer, then continue as new and return immediately.

```python
def bounded_reconciliation(
    ctx: task.OrchestrationContext,
    state: dict[str, Any],
) -> Generator[task.Task[Any], Any, dict[str, Any]]:
    if state["stopped"]:
        return state

    scan = yield ctx.call_activity(
        "ReconcileScan",
        input=state.get("checkpoint"),
    )

    next_state = {
        "checkpoint": scan["next_checkpoint"],
        "interval_seconds": state["interval_seconds"],
        "stopped": scan["stopped"],
    }

    if next_state["stopped"]:
        return next_state

    next_check = ctx.current_utc_datetime + timedelta(
        seconds=next_state["interval_seconds"]
    )
    yield ctx.create_timer(next_check)

    # Start a fresh generation with compact, committed state.
    ctx.continue_as_new(next_state)
    return next_state
```

Those are the implementations to register for new executions. They do not make an arbitrary old history replay-compatible.

#### Moving versions requires an already safe boundary

If an existing version can already replay to a verified compatible boundary, and the SDK plus backend are configured for version routing, that boundary can request the next version while continuing as new. The standalone .NET API uses [`ContinueAsNewOptions.NewVersion`](https://github.com/microsoft/durabletask-dotnet/blob/2a409da4ac7dcf03c4f25985337eb4623ea6394e/src/Abstractions/ContinueAsNewOptions.cs#L28-L36):

```csharp
private static ReconciliationState ContinueWithVersion(
    TaskOrchestrationContext context,
    ReconciliationState nextState)
{
    context.ContinueAsNew(new ContinueAsNewOptions
    {
        NewInput = nextState,
        NewVersion = "2.0",
    });
    return nextState;
}
```

The standalone Python API exposes the equivalent [`new_version` argument](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/task.py#L391-L411):

```python
def continue_with_version(
    ctx: task.OrchestrationContext,
    next_state: dict[str, Any],
) -> dict[str, Any]:
    ctx.continue_as_new(next_state, new_version="2.0")
    return next_state
```

That is a transition made **at** a safe boundary, not a way to create one retroactively. Inserting either call into an arbitrary point that old instances must replay is not a universal in-place migration.

### Replacement is a new instance, not a move

If an old instance can't safely reach the bounded implementation, a replacement means scheduling a **different** bounded orchestration from authoritative application progress. It doesn't transfer the old execution, trim its history, or upgrade it in place.

Only do that when external state can establish the last confirmed checkpoint and reconcile uncertain effects. Use stable business keys and idempotent writes, prevent the old and new owners from both committing new work, and use an explicit replacement instance ID so an ambiguous scheduling result can be looked up instead of blindly retried. If you can't establish progress without guessing a cursor or overlooking in-flight effects, stop and reconcile manually rather than starting from invented state. Terminating the old orchestration doesn't roll back effects already in flight.

Purging history is a separate retention and cleanup decision after an instance is safely retired. The [purge documentation](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-instance-management#purge-orchestration-instance-history) describes removing stored instance data; it does not make a running orchestration replay with less history or reconstruct a missing checkpoint.

If there is no reliable external checkpoint and no trustworthy way to reconstruct completed business effects, the remaining work may require manual reconciliation and platform support. Guessing a checkpoint and starting over can be worse than keeping the large instance while you investigate.

---

## Long-Lived Doesn't Have to Mean Ever-Growing

The useful distinction isn't "short workflows good, long workflows bad."

It's this:

**Let the business process live as long as it needs to. Give each orchestration generation a bounded amount of history to recover from.**

Use continue-as-new where the Durable Functions or Durable Task SDK contract supports it. Carry compact state. Give children meaningful boundaries without assuming they erase their parent's history. Choose recurrence semantics deliberately. Keep business durability separate from diagnostic convenience.

That's a design for this replay-based orchestration model, not a claim about every workflow engine.

The next cycle needs to know where to continue. It doesn't necessarily need the autobiography.

🖖
