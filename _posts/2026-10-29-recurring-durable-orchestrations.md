---
layout: post
date: 2026-10-29
title: "Run Forever, Keep History Bounded: Recurring Durable Orchestrations"
tags: [azure, durable-functions, durable-task-sdk, orchestration, workflows, performance, dotnet]
---

In my [replay walkthrough](https://www.tamirdresher.com/blog/2026/09/21/durable-await-replay), we followed what lets an orchestration continue after its worker disappears: recorded history, not a method kept alive in memory. Then we looked at [less obvious Durable Task capabilities](https://www.tamirdresher.com/blog/2026/09/25/durable-task-hidden-capabilities) and [where durable execution fits real applications](https://www.tamirdresher.com/blog/2026/09/28/durable-task-real-world).

Now I want to turn that recovery story around: **what happens when the workflow keeps going, and so does its history?**

Think of a reconciliation job that checks for changes, does some work, waits, and repeats. There isn't necessarily a final step. Finishing today's cycle just means waiting for the next one.

The loop can stay five lines long while the history behind it keeps growing. Reassigning a local variable doesn't make the runtime forget the activities and timers that got you there.

That's the distinction this post is about: **a business process can run indefinitely without keeping every cycle in the same orchestration generation.** Long-lived isn't the problem. Unbounded history is.

We'll look at how `ContinueAsNew` creates that boundary in Durable Functions and the Durable Task SDKs, what state should cross it, and why neither child orchestrations nor a timer automatically solve the lifecycle problem. We call this the [eternal orchestration pattern](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-eternal-orchestrations). Eternal process. Not an eternal scrapbook.

---

## The Process Can Be Eternal. The Generation Doesn't Have To Be.

Imagine a recurring reconciliation job. It checks a source, applies the next unit of work, records its progress, waits, and checks again.

In these snippets, `ContinuationToken` in C# and `continuation_token` in Python hold the data source's small next-page marker: the value that tells the next request which page to fetch. An absent token represents the initial request.

Here's the tempting shape in both standalone SDKs. These are teaching snippets, not complete runnable applications: the `ReconcileNextPage` activity implementation, worker registration, client startup, connection settings, retries, and production error handling are intentionally omitted.

### Standalone Durable Task .NET SDK: one history that keeps growing

```csharp
using Microsoft.DurableTask;
using System;
using System.Threading;
using System.Threading.Tasks;

public sealed record ReconciliationState(
    string? ContinuationToken,
    TimeSpan Interval,
    bool Stopped = false);

public sealed record ReconciliationResult(
    string? NextContinuationToken,
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
            // The activity processes one page outside the orchestrator. The token tells the data source which page comes next.
            ReconciliationResult page =
                await context.CallActivityAsync<ReconciliationResult>(
                    "ReconcileNextPage",
                    state.ContinuationToken);

            state = state with
            {
                ContinuationToken = page.NextContinuationToken,
                Stopped = page.Stopped,
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
        # The activity processes one page outside the orchestrator. The token tells the data source which page comes next.
        page = yield ctx.call_activity(
            "ReconcileNextPage",
            input=state.get("continuation_token"),
        )

        state = {
            "continuation_token": page["next_continuation_token"],
            "interval_seconds": state["interval_seconds"],
            "stopped": page["stopped"],
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

Notice what doesn't fix that: assigning the latest result back to the same local variable. You've replaced the value in your code. You haven't reset the orchestration history.

Also, elapsed time isn't the right proxy. A workflow waiting a long time for one external event is different from a workflow scheduling new durable work repeatedly. Ask **how much history it creates**, not just how old it is.

---

## ContinueAsNew: Same Process, Next Chapter

That's where `ContinueAsNew` comes in.

The [eternal orchestration docs](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-eternal-orchestrations#how-continue-as-new-works) describe a new orchestration generation with new input, the same instance ID, and reset orchestration history. They also describe a new execution ID internally.

For the .NET `Microsoft.DurableTask` API, [`TaskOrchestrationContext.ContinueAsNew`](https://learn.microsoft.com/en-us/dotnet/api/microsoft.durabletask.taskorchestrationcontext.continueasnew?view=durabletask-dotnet-1.x) documents the same essential contract: restart with new input and clear the history used for that execution.

Think of this as a **logical generation boundary**, not "start a random unrelated workflow" and not "reboot the worker."

It's also not a promise about physical deletion, backup retention, or when storage space is reclaimed. A reset of orchestration history is an execution semantic. Storage lifecycle and retention need their own provider-specific documentation and policies.

Here is the same scenario with one completed page and one completion-relative wait per generation. That page-sized boundary keeps the example easy to compare; it is not a universal recommendation for production generation size.

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

        // The activity processes one page outside the orchestrator. The token tells the data source which page comes next.
        ReconciliationResult page =
            await context.CallActivityAsync<ReconciliationResult>(
                "ReconcileNextPage",
                state.ContinuationToken);

        // Carry only the next-page token, cadence, and stop flag into the next generation.
        ReconciliationState nextState = state with
        {
            ContinuationToken = page.NextContinuationToken,
            Stopped = page.Stopped,
        };

        if (nextState.Stopped)
        {
            return nextState;
        }

        // Use orchestration time to create a replay-safe durable wait.
        DateTime nextCheck =
            context.CurrentUtcDateTime.Add(nextState.Interval);
        await context.CreateTimer(nextCheck, CancellationToken.None);

        // Request the next generation only after this page and wait complete.
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

    # The activity processes one page outside the orchestrator. The token tells the data source which page comes next.
    page = yield ctx.call_activity(
        "ReconcileNextPage",
        input=state.get("continuation_token"),
    )

    # Carry only the next-page token, cadence, and stop flag into the next generation.
    next_state = {
        "continuation_token": page["next_continuation_token"],
        "interval_seconds": state["interval_seconds"],
        "stopped": page["stopped"],
    }

    if next_state["stopped"]:
        return next_state

    # Use orchestration time to create a replay-safe durable wait.
    next_check = ctx.current_utc_datetime + timedelta(
        seconds=next_state["interval_seconds"]
    )
    yield ctx.create_timer(next_check)

    # Request the next generation only after this page and wait complete.
    ctx.continue_as_new(next_state)
    # End this generator immediately after requesting the boundary.
    return next_state
```

Both versions wait for the activity and timer before rolling over, carry only the state needed by the next generation, and return immediately after continue-as-new. The activity and timer APIs come from the same public SDK surfaces linked above. The .NET repository's [ContinueAsNew integration test](https://github.com/microsoft/durabletask-dotnet/blob/2a409da4ac7dcf03c4f25985337eb4623ea6394e/test/Grpc.IntegrationTests/OrchestrationPatterns.cs#L567-L592) and the Python [`continue_as_new` contract](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/task.py#L391-L411) both show the immediate-return requirement. Registration is omitted; the Python worker exposes [`add_orchestrator` and `add_activity`](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/worker.py#L637-L715), while the .NET worker registers tasks through `AddDurableTaskWorker(...).AddTasks(...)`.

The important bit is the handoff: the next generation starts from the state you've explicitly chosen to preserve. It doesn't need to replay every previous reconciliation cycle to discover that state.

Don't schedule another bit of work afterward and hope it belongs to the next chapter.

I've also covered [using that execution boundary to change workflow versions](https://www.tamirdresher.com/blog/2026/09/25/durable-task-hidden-capabilities). That's a separate capability, with its own backend and compatibility requirements. Here, we need the boundary even when the implementation never changes.

---

## A Fresh Start Doesn't Make Your Input Smaller

In the examples above, the activity processes one page of records. The data source returns a **continuation token**: a small value that tells the next request which page comes next. That token is the progress marker the next orchestration generation needs.

A compact next-generation input might look conceptually like this:

```json
{
  "continuation_token": "next-page-token",
  "interval_seconds": 300,
  "stopped": false
}
```

The interval here is only illustrative, not a recommended cadence.

Now imagine that after every page, the orchestration also appends every processed record and result to a `processed_results` list, then passes that whole object to continue-as-new:

```json
{
  "continuation_token": "next-page-token",
  "interval_seconds": 300,
  "stopped": false,
  "processed_results": [
    "every result from page 1",
    "every result from page 2",
    "and so on"
  ]
}
```

`ContinueAsNew` gives the orchestration a fresh execution history. But the object you pass to it becomes the next generation's input. It doesn't remove items from that object or make an ever-growing list smaller.

A better split is to have the activity save detailed results in the application's database or object store, then return only the source's next-page token and the genuinely small state needed for the next cycle. If the orchestration needs to refer to saved details later, it can carry a stable reference rather than the details themselves.

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

This is actually what made me write this post. A team approached me about some strange behavior: their orchestration's performance had suddenly dropped.

When I looked into the details, I found an orchestration that had been running in an endless loop for months. Over that time, it had accumulated millions of history records.

Explaining how to avoid that in a new workflow is one thing. But this one was already running, with all that history behind it. **What do we do now?**

### First, contain the load

Before we worked out the long-term repair, we suspended the affected orchestrations and then resumed selected groups gradually. By "affected," I mean an explicit, reviewed list for this workload, not every orchestration in the task hub.

In that case, the available evidence indicates that the control action used the supported client operations programmatically. An approved list of instance IDs was suspended, then selected batches were resumed later. The exact wrapper, language, or command harness was not captured, so the examples below show public ways to implement the same pattern, not the original incident script.

This was temporary containment, not a history fix. Suspension can reduce how many of these orchestrations are actively processing, but it doesn't truncate their histories. Resuming them can bring the same replay cost and any accumulated work back. New starts may need separate gating; suspending existing instances doesn't stop another starter from creating more.

#### Start with the dashboard for a small reviewed set

For a few known instances, the simplest option is the [Durable Task Scheduler dashboard](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler-dashboard). Open the Orchestrations pane, find the instance, select its instance ID, and choose Suspend. After checking containment and business progress, return to each explicitly approved instance and choose Resume.

The public dashboard documentation describes these actions on an individual orchestration. It does not document a bulk-select suspend or resume action, so I would not assume that filtering a list and clicking once controls every result. Verify each instance's status before moving on.

#### You don't need a whole application for an admin task

The current standalone Durable Task JavaScript/TypeScript SDK is in preview. A short local Node.js `.mjs` script can connect directly to Azure-managed DTS and [suspend or resume an instance](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-instance-management?tabs=javascript&pivots=durable-task-sdks#suspend-and-resume-orchestration-instances) without deploying a Durable Functions app or keeping a long-running application alive. Read connection configuration from a protected environment variable; never commit, print, or log its value. This is a public alternative implementing the same containment pattern, not the recovered historical incident script.

```javascript
import { OrchestrationStatus } from "@microsoft/durabletask-js";
import { createAzureManagedClient } from "@microsoft/durabletask-js-azuremanaged";

const connectionString = process.env.DURABLE_TASK_SCHEDULER_CONNECTION_STRING;
const [action, instanceId] = process.argv.slice(2);

if (!connectionString) {
    throw new Error("DURABLE_TASK_SCHEDULER_CONNECTION_STRING is required");
}

if (!instanceId || (action !== "suspend" && action !== "resume")) {
    throw new Error("Use: node admin.mjs <suspend|resume> <approved-instance-id>");
}

const client = createAzureManagedClient(connectionString);

try {
    const state = await client.getOrchestrationState(instanceId, false);
    if (!state) {
        throw new Error(`Instance not found: ${instanceId}`);
    }

    if (action === "suspend") {
        if (state.runtimeStatus !== OrchestrationStatus.RUNNING) {
            throw new Error(`Expected Running, observed ${state.runtimeStatus}`);
        }

        await client.suspendOrchestration(
            instanceId,
            "Temporary containment while history growth is investigated",
        );
        console.log("Suspend request sent. Verify Suspended before continuing.");
    } else {
        if (state.runtimeStatus !== OrchestrationStatus.SUSPENDED) {
            throw new Error(`Expected Suspended, observed ${state.runtimeStatus}`);
        }

        await client.resumeOrchestration(instanceId, "Approved staged resume");
        console.log("Resume request sent. Verify the resulting status before continuing.");
    }
} finally {
    await client.stop();
}
```

Suspend and resume are separate script invocations against one explicitly approved instance ID. The action argument selects exactly one branch, with no fall-through and no bulk mutation. The state query passes `false` to omit payloads. Each control request still needs a separate status readback before the next operational step; the pre-action check is not that confirmation. `client.stop()` releases the gRPC client. No real endpoint, task hub, credential, instance ID, or connection string is shown.

The public sources show [Azure-managed client creation](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js-azuremanaged/src/client-builder.ts), the [client methods](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js/src/client/client.ts), and a [plain ESM `.mjs` sample](https://github.com/Azure-Samples/Durable-Task-Scheduler/blob/7152d82c656576b9cda47d33ac2de4f61aacff66/samples/durable-task-sdks/javascript/function-chaining/client.mjs).

For a larger reviewed workload, use the SDK query APIs to build a candidate list before changing anything. In .NET, `GetAllInstancesAsync` with `OrchestrationQuery` can filter by runtime status, creation window, and instance ID prefix, with paged results. Keep `FetchInputsAndOutputs` false when you only need IDs and status. The Python SDK also exposes filtered orchestration queries, although its result and pagination behavior differs, so follow the examples for the client you use. The public [filtered-query guide](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-instance-management#query-orchestration-instances-with-filters) shows the supported filters.

Treat that query as discovery, not authorization. Review the candidates, freeze an explicit approved ID list, and recheck each instance's current status before mutation. Build each resume batch from a separately approved subset. Instances can change while pages are being read, so do not pipe an open-ended query directly into mutation.

#### How do I find the instances with large histories?

The public dashboard and query documentation doesn't expose a largest-history filter. Narrow the candidates metadata-first: use orchestration name or tags in the [Durable Task Scheduler dashboard](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler-dashboard), and runtime status, creation-time window, or instance ID prefix with the JavaScript client's [`getAllInstances`](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js/src/client/client.ts#L810-L1002) query. Keep inputs and outputs disabled during discovery. Age is only a hint, not a measure of history size.

After a human reviews that metadata and freezes a small approved ID list, the same local Node.js client can retrieve each history:

```javascript
import { createAzureManagedClient } from "@microsoft/durabletask-js-azuremanaged";

const connectionString = process.env.DURABLE_TASK_SCHEDULER_CONNECTION_STRING;
const approvedInstanceIds = [
    "reviewed-instance-id-1",
    "reviewed-instance-id-2",
];

if (!connectionString) {
    throw new Error("DURABLE_TASK_SCHEDULER_CONNECTION_STRING is required");
}

const client = createAzureManagedClient(connectionString);
const results = [];

try {
    for (const instanceId of approvedInstanceIds) {
        try {
            // Verify the reviewed instance still exists without requesting state payloads.
            const state = await client.getOrchestrationState(instanceId, false);
            if (!state) {
                results.push({
                    InstanceId: instanceId,
                    RuntimeStatus: "Missing",
                    ReturnedHistoryEntries: null,
                    Result: "Instance was not found",
                });
                continue;
            }

            // Durable Task API: retrieve the returned history-event snapshot.
            const history = await client.getOrchestrationHistory(instanceId);
            results.push({
                InstanceId: instanceId,
                RuntimeStatus: state.runtimeStatus,
                ReturnedHistoryEntries: history.length,
                Result: "OK",
            });
        } catch (error) {
            results.push({
                InstanceId: instanceId,
                RuntimeStatus: "Unknown",
                ReturnedHistoryEntries: null,
                Result: error instanceof Error ? error.message : "Unknown error",
            });
        }
    }
} finally {
    await client.stop();
}

results.sort(
    (left, right) =>
        (right.ReturnedHistoryEntries ?? -1) -
        (left.ReturnedHistoryEntries ?? -1),
);
console.table(results);
```

[`getOrchestrationHistory`](https://github.com/microsoft/durabletask-js/blob/84c8df1b0f8b5e45fa2c54624a818f085ce8df2a/packages/durabletask-js/src/client/client.ts#L1069-L1163) returns history event objects and returns an empty array when an instance isn't found. That is why the example checks state first and reports missing and error results separately. `ReturnedHistoryEntries` is only the number of entries in that returned snapshot. It is not stored bytes, provider storage size, or a direct measurement of replay work. History events may include sensitive inputs or results, so don't turn this into a broad crawl. The dashboard History tab, [.NET `GetOrchestrationHistoryAsync`](https://github.com/microsoft/durabletask-dotnet/blob/2a409da4ac7dcf03c4f25985337eb4623ea6394e/src/Client/Core/DurableTaskClient.cs#L500-L517), and [Python `get_orchestration_history`](https://github.com/microsoft/durabletask-python/blob/6a56be2f406e7f787f5925f48ea7d3715928e6ff/durabletask/client.py#L675-L686) are alternatives for the same bounded inspection.

Whatever client you use, operate only on an explicit approved ID list, recheck each current status immediately before the action, and read the status back afterward. Stop on missing, unexpected, or partially applied results. Resume only separately approved subsets, with workload health and business progress checks between them.

### Then, fix the history growth

The code change I want is the bounded C# or Python implementation shown earlier. New instances should start on that implementation and call `ContinueAsNew` after a bounded amount of work. Deploy it with the SDK and backend's supported [orchestration versioning](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-orchestration-versioning) or a drain strategy so workers serving older histories preserve the durable-action sequence those histories expect.

That deployment doesn't rewrite an existing history or move a live execution onto the new loop. `ContinueAsNew` isn't an external "compact this instance" button. The orchestrator has to reach the call itself; a client can't force it from outside, and restarting a worker doesn't erase persisted history.

There is no universal safe retrofit for arbitrary running instances. Adding, removing, or reordering activities, timers, sub-orchestrations, external-event waits, or continuation calls can change replay decisions. A specifically reviewed and tested code change may be replay-compatible with a particular history shape, and an existing compatible control path may provide a safe handoff. This article isn't claiming or test-proving such a migration for every old history. `IsReplaying`, durable time, or a version check alone doesn't make a changed durable-action sequence compatible.

So the practical split is:

* **New instances:** run the bounded C# or Python implementation.
* **Running instances with a verified compatible handoff:** let the old implementation reach that handoff and roll over under the versioning contract you tested.
* **Running instances without one:** keep their compatible old code available while you contain, drain, retire, or replace them deliberately.

### Replacement is a new instance, not a move

If an old instance can't safely reach the bounded implementation, a replacement means scheduling a **different** bounded orchestration from authoritative application progress. It doesn't transfer the old execution, trim its history, or upgrade it in place.

Only do that when external state can establish the last confirmed checkpoint and reconcile uncertain effects. Use stable business keys and idempotent writes, prevent the old and new owners from both committing new work, and use an explicit replacement instance ID so an ambiguous scheduling result can be looked up instead of blindly retried. If you can't establish progress without guessing a cursor or overlooking in-flight effects, stop and reconcile manually rather than starting from invented state. Terminating the old orchestration doesn't roll back effects already in flight.

Purging history is a separate retention and cleanup decision after an instance is safely retired. The [purge documentation](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-instance-management#purge-orchestration-instance-history) describes removing stored instance data; it does not make a running orchestration replay with less history or reconstruct a missing checkpoint.

If there is no reliable external checkpoint and no trustworthy way to reconstruct completed business effects, say so plainly. The remaining work may require manual reconciliation and platform support. Guessing a continuation token and starting over can be worse than keeping the large instance while you investigate.

---

## Long-Lived Doesn't Have to Mean Ever-Growing

The useful distinction isn't "short workflows good, long workflows bad."

It's this:

**Let the business process live as long as it needs to. Give each orchestration generation a bounded amount of history to recover from.**

Use continue-as-new where the Durable Functions or Durable Task SDK contract supports it. Carry compact state. Give children meaningful boundaries without assuming they erase their parent's history. Choose recurrence semantics deliberately. Keep business durability separate from diagnostic convenience.

That's a design for this replay-based orchestration model, not a claim about every workflow engine.

The next cycle needs to know where to continue. It doesn't necessarily need the autobiography.

🖖
