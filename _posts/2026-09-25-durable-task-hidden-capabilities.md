---
layout: post
title: "Three Durable Task Capabilities Worth Knowing About"
date: 2026-09-25
tags: [dotnet, durable-task-sdk, durable-task-scheduler, orchestration, workflows]
---

In [the previous post][previous-post], we followed an orchestration through its activity awaits and looked at what actually survives: history, not the original worker's local tasks or suspended method. I ended by promising to explore some of the capabilities people tend to miss in the Durable Task ecosystem.

Let's make good on that.

Once you understand how a workflow can keep going without its original worker, a few practical questions follow. Can different parts run on different kinds of workers? Can a workflow that is already running move to a newer implementation? And when something fails after several successful steps, can we repair it without starting the whole business operation again?

There are useful answers to all three. They are also three different operations, which matters rather more than the fact that all of them can appear in a demo called "make the workflow continue."

I'll use the standalone [Durable Task .NET SDK v1.26.0][sdk-release] with manual registration, without the optional source generator. The code below is based on public API definitions and samples. These are teaching illustrations, not compiled or executed demonstrations. Real activity implementations and connection values are omitted; the shipping example includes host setup and startup. The clients and workers are assumed to be configured for the intended DTS task hub.

## Keep the workflow together, split the workers

Suppose order validation is inexpensive, but shipping needs a large integration SDK, different compute, or its own release schedule. I don't particularly want every validation worker carrying the shipping dependencies just because both activities belong to the same workflow.

The workflow can stay one workflow without making every worker carry every activity.

The distinction is between **coordination** and **where work runs**. There are three pieces to keep separate. The **registry** maps task names and versions to code a worker can run. **Filters** describe the work that worker asks DTS to send it. An optional **worker version policy** adds acceptance checks. They need to agree: a filter neither registers a missing implementation nor translates its payload.

An orchestrator still requests activities by name. [Work item filtering][filter-doc] lets DTS deliver those work items to eligible workers, without putting worker addresses into the workflow.

Here is a small, independently defined orchestration:

```csharp
using System.Threading.Tasks;
using Microsoft.DurableTask;

public sealed class OrderRouting : TaskOrchestrator<string, string>
{
    public override async Task<string> RunAsync(
        TaskOrchestrationContext context, string orderId)
    {
        string validation = await context.CallActivityAsync<string>(
            "ValidateOrder", orderId);
        string shipping = await context.CallActivityAsync<string>(
            "ShipOrder", orderId);
        return $"{validation}; {shipping}";
    }
}
```

The validation activity is assumed to throw if the order is invalid; its returned string is informational, not an approval flag that this code forgot to check. The activity implementations are outside this example. This is also a new teaching orchestration, not a suggestion to replace the call sequence of the existing `OrderFlow` instances from the first post.

Notice what the method does not contain: a shipping worker address, an HTTP client for that worker, or a discovery service. It asks the orchestration context for named work. DTS handles the delivery, and recorded results allow the orchestration to make progress.

### Configure the worker, then start the host

For an ordinary specialist worker, register only its own tasks and let the SDK generate the filters. Here is the shipping host, including startup. `connectionString` is an already configured value supplied by the application, and it must target the same scheduler and task hub as the other participants.

```csharp
using System.Threading;
using System.Threading.Tasks;
using Microsoft.DurableTask;
using Microsoft.DurableTask.Worker;
using Microsoft.DurableTask.Worker.AzureManaged;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

public static class ShippingHost
{
    public static async Task RunAsync(
        string connectionString,
        TaskActivity<string, string> shipOrder,
        CancellationToken cancellation = default)
    {
        HostApplicationBuilder builder = Host.CreateApplicationBuilder();
        builder.Services.AddDurableTaskWorker()
            .AddTasks(registry =>
                registry.AddActivity("ShipOrder", shipOrder))
            .UseWorkItemFilters()
            .UseDurableTaskScheduler(connectionString);

        using IHost host = builder.Build();
        await host.RunAsync(cancellation);
    }
}
```

The registration chain configures a worker; it does not start one. `Build()` creates the host, and `RunAsync` starts it and keeps it running until shutdown.

`shipOrder` is an actual activity implementation supplied by the application. Returning a cheerful string is not a shipping integration, however much easier that would make the example.

The other deployments follow the same setup pattern, with their own registrations inside `AddTasks`:

| Worker deployment | Its registration |
| :--- | :--- |
| Coordination | `registry.AddOrchestrator<OrderRouting>("OrderRouting")` |
| Validation | `registry.AddActivity("ValidateOrder", validateOrder)` |
| Shipping | `registry.AddActivity("ShipOrder", shipOrder)` |

Here, both activity implementations are `TaskActivity<string, string>`. **Every participating worker explicitly calls `.UseWorkItemFilters()`**, connects to the same scheduler and task hub, and starts its host. For this SDK configuration, that [explicit builder call][filter-builder] is the filtering setup I rely on, not an assumed default.

The parameterless call generates filters from the completed registry and worker options for that worker when its options are resolved. It does not freeze a list of whichever registrations happen to appear above the call in the file. Finish configuring the host before building and starting it.

### What can you select?

The [custom configuration type][filter-model] is `DurableTaskWorkerWorkItemFilters`, in `Microsoft.DurableTask.Worker`. Its three collection properties separate the kinds of work. The filter item types in the table are nested inside that class.

| Control | Public shape | What it means |
| :--- | :--- | :--- |
| `Orchestrations` | `IReadOnlyList<OrchestrationFilter>` | Orchestration names, each with a `Versions` list. |
| `Activities` | `IReadOnlyList<ActivityFilter>` | Activity names, each with a `Versions` list. |
| `Entities` | `IReadOnlyList<EntityFilter>` | Entity names only, not individual entity keys or operations. |
| `UseWorkItemFilters()` | No argument | Generate the selections from the completed registry and worker options. |
| `UseWorkItemFilters(filters)` | A `DurableTaskWorkerWorkItemFilters` object | Use the supplied selections instead of generating them. This configures whole collections, not an incremental filter addition. |
| `UseWorkItemFilters(null)` | A null method argument | Disable filtering. This does not pause the worker or mean "receive nothing." |

You can select multiple names and concrete versions for orchestration and activity work. An entity filter has no version property. This is not a predicate engine for payloads, tenants, instance IDs, hardware, or priorities. There is no documented name glob, regex, or prefix syntax here: use the actual registered name, not `Ship*`.

Also, do not treat a custom object with all three lists empty as a "receive nothing" setting. If the intention is to stop processing, stop the worker.

### Optionally advertise less than you register

Sometimes the code a worker contains and the work it should receive are intentionally different. Here, the registry contains `ShipOrder` and `CancelShipment`, both at version `"1"`, but the filter advertises only `ShipOrder` version `"1"`.

This is an **alternative** to the registration chain in `ShippingHost`, not another chain to append to it. Supply both real activity objects to your host setup and call `ShippingSubset.Configure(builder.Services, connectionString, shipOrder, cancelShipment)` before `Build()`, in place of the earlier worker registration chain. Keep the same `Build()` and `RunAsync` lifetime.

```csharp
using Microsoft.DurableTask;
using Microsoft.DurableTask.Worker;
using Microsoft.DurableTask.Worker.AzureManaged;
using Microsoft.Extensions.DependencyInjection;

public static class ShippingSubset
{
    public static void Configure(
        IServiceCollection services,
        string connectionString,
        TaskActivity<string, string> shipOrder,
        TaskActivity<string, string> cancelShipment)
    {
        var filters = new DurableTaskWorkerWorkItemFilters
        {
            Activities = new[]
            {
                new DurableTaskWorkerWorkItemFilters.ActivityFilter(
                    "ShipOrder", new[] { "1" }),
            },
        };

        services.AddDurableTaskWorker()
            .AddTasks(registry =>
            {
                registry.AddActivity(
                    "ShipOrder", new TaskVersion("1"), () => shipOrder);
                registry.AddActivity(
                    "CancelShipment", new TaskVersion("1"),
                    () => cancelShipment);
            })
            .UseWorkItemFilters(filters)
            .UseDurableTaskScheduler(connectionString);
    }
}
```

The [versioned registrations][activity-registry] supply implementations; the `ActivityFilter` supplies a name and version selection. This worker can instantiate both activities, but asks to receive only the advertised one. If the workflow needs `CancelShipment`, an eligible worker elsewhere must serve it.

The caller also needs to request the version you advertised. For this optional example, use this separate orchestration rather than assuming the earlier unversioned `OrderRouting` call selects version 1:

```csharp
using System.Threading.Tasks;
using Microsoft.DurableTask;

public sealed class ShippingRequest : TaskOrchestrator<string, string>
{
    public override Task<string> RunAsync(
        TaskOrchestrationContext context, string orderId)
        => context.CallActivityAsync<string>(
            "ShipOrder", orderId,
            options: new TaskOptions
            {
                Version = new TaskVersion("1"),
            });
}
```

Register `ShippingRequest` on an orchestration worker with `registry.AddOrchestrator<ShippingRequest>("ShippingRequest")`, that worker's own parameterless filters, and the same task hub and host startup pattern. [`TaskOptions.Version`][task-options] here requests activity version `"1"`; it does not register the activity on the caller.

Keep the exact name and version values aligned across the call, filter, and implementation. The SDK's [custom filter validator][filter-validator] checks that the selected names are registered in the corresponding work kind. It does **not** check that every advertised version has an implementation. If you also configure `UseVersioning(...)`, its acceptance policy must agree with those selections. A broader advertisement cannot supply missing code.

For most specialist services, the first pattern is simpler: register only what the role needs and generate its filters. Use the custom subset when that separation is actually useful, not just because another configuration object exists.

### What happens between this worker and DTS?

The public SDK and documented service contract give us the useful sequence without needing to know the scheduler's internal implementation:

1. **Configure the host.** Register the local implementations and choose generated or custom filters. The [worker resolves its filter options when it is constructed][filter-worker].
2. **Request work.** The SDK [includes the configured eligibility in its work request][filter-request]. Names and versions are part of the [public request contract][filter-protocol]. This is the worker asking DTS for work, not the orchestrator calling the shipping host.
3. **Receive matching work.** DTS delivers work according to the [documented matching contract][filter-doc]. If no eligible worker is available, that work item stays pending.
4. **Run the registered implementation.** The [local factory][filter-factory] selects code by the received task name and requested version. Configured worker version checks still apply. The activity runs, and the worker reports its result through the normal protocol.

Configure the registry and filters before starting the host. For a change, rebuild or restart the worker with the new configuration; mutating a running worker's filter object is not a documented hot update mechanism. Set the intended filters on every worker in a mixed pool. Enabling them only on the shipper does not restrict an unfiltered worker beside it.

The diagram follows the simpler setup, with only each role's own tasks registered.

Read the next diagram as a deployment view, not a network trace. The boxes are separately deployable worker roles. Workers establish outbound connections to DTS; the delivery arrows show which registered work they can receive over those connections. The orchestration worker requests named activities through DTS, not by calling the shipping host directly. Click the diagram to enlarge it.

[![Deployment view of one DTS task hub and three specialist worker roles. The orchestration worker registers OrderRouting, the validation worker registers ValidateOrder, and the shipping worker registers ShipOrder. All enable filters and connect outward to DTS. Without an eligible shipping worker, ShipOrder remains pending rather than falling back to another specialist.](/assets/durable-task-hidden-capabilities/specialist-worker-routing.svg)](/assets/durable-task-hidden-capabilities/specialist-worker-routing.svg)

*Figure 1. One workflow, three worker roles. Work eligibility follows the configured registrations and filters. Results are recorded for later orchestration progress; the diagram does not describe the scheduler's internal queues or transactions.*

What happens if the shipping deployment is missing?

With this filtered setup, the shipping work stays pending. The orchestration can still be `Running`, waiting for that result. There is no fallback that asks the validation worker to improvise a shipping implementation.

That makes deployment order important: deploy the handler before callers begin requesting it, keep task names and versions compatible, and monitor the backlog. Worker specialization gives you independent deployment and scaling choices. It does not configure an autoscaler for you.

One more boundary worth stating: filtering is **routing, not authorization or tenant isolation**. Worker identities and access controls still matter, as does access to whatever external systems the activities use. Sharing a task hub is not permission to skip those checks.

## Keep the instance, change the next execution

Now suppose the workflow lives longer than a release cycle. We have a better implementation, but waiting for every existing instance to finish would be a fairly optimistic deployment plan.

Do we need to create a different workflow instance and somehow transfer the business identity to it?

Not necessarily. First, separate two terms. The **instance** is the logical workflow addressed by its instance ID. An **execution** is one generation of that instance. We can keep the instance while deliberately beginning another execution with a new version and a fresh execution history.

The API for that boundary is [`ContinueAsNew` with `ContinueAsNewOptions.NewVersion`][continue-options]. It is not an assignment to `context.Version`, and it is not permission to change arbitrary code halfway through replay.

> **Version and backend scope.** The released .NET v1.26.0 SDK exposes this API, and the [public standalone migration sample][migration-readme] shows the intended routing model. A compatible backend must support the version change, and the standalone worker must forward it. That is not a claim that every backend or every managed DTS deployment has the same feature rollout. Verify support in the environment you intend to use.

Let's keep the data small: a checkpoint containing a count and a marker that says migration was requested. The count is supplied as input; this example does not claim to have processed that many real jobs.

```csharp
using System;
using System.Threading.Tasks;
using Microsoft.DurableTask;

public sealed record BatchCheckpoint(
    int ProcessedCount, bool MigrationRequested = false);

public sealed class BatchLoopV1
    : TaskOrchestrator<BatchCheckpoint, string>
{
    public override Task<string> RunAsync(
        TaskOrchestrationContext context, BatchCheckpoint checkpoint)
    {
        if (checkpoint.MigrationRequested)
        {
            throw new NotSupportedException(
                "Continuation returned to v1; investigate version propagation.");
        }

        context.ContinueAsNew(new ContinueAsNewOptions
        {
            NewInput = checkpoint with { MigrationRequested = true },
            NewVersion = "2",
            PreserveUnprocessedEvents = true,
        });
        return Task.FromResult(string.Empty);
    }
}

public sealed class BatchLoopV2
    : TaskOrchestrator<BatchCheckpoint, string>
{
    public override Task<string> RunAsync(
        TaskOrchestrationContext context, BatchCheckpoint checkpoint)
        => Task.FromResult(
            $"v2 received checkpoint {checkpoint.ProcessedCount}");
}
```

The important payload is `NewInput`. It carries what the next implementation needs. The next execution does not inherit the old local variables, `Task` objects, or CLR continuation.

The guard in v1 is intentional. If the continuation comes back to v1 with the migration marker already set, the example fails visibly rather than quietly continuing forever or presenting a fallback as successful migration. The [public migration example][migration-program] highlights that version propagation depends on backend support. A guard is useful; it is not a substitute for verifying that support.

### Accepting a version is not the same as implementing it

We need both the worker's version acceptance policy and the right registered implementation. A worker accepting older work does not magically contain the older code.

Here is the configuration inside an existing Generic Host setup, where `builder` is the host builder and `connectionString` identifies the intended task hub:

```csharp
using Microsoft.DurableTask;
using Microsoft.DurableTask.Client;
using Microsoft.DurableTask.Client.AzureManaged;
using Microsoft.DurableTask.Worker;
using Microsoft.DurableTask.Worker.AzureManaged;
using Microsoft.Extensions.DependencyInjection;

builder.Services.AddDurableTaskWorker(worker =>
{
    worker.AddTasks(registry =>
    {
        registry.AddOrchestrator("BatchLoop", new TaskVersion("1"),
            () => new BatchLoopV1());
        registry.AddOrchestrator("BatchLoop", new TaskVersion("2"),
            () => new BatchLoopV2());
    });
    worker.UseVersioning(new DurableTaskWorkerOptions.VersioningOptions
    {
        Version = "2",
        DefaultVersion = "2",
        MatchStrategy =
            DurableTaskWorkerOptions.VersionMatchStrategy.CurrentOrOlder,
        FailureStrategy =
            DurableTaskWorkerOptions.VersionFailureStrategy.Reject,
    });
    worker.UseWorkItemFilters();
    worker.UseDurableTaskScheduler(connectionString);
});
builder.Services.AddDurableTaskClient(
    clientBuilder => clientBuilder.UseDurableTaskScheduler(connectionString));
```

Both classes use the same logical name, `BatchLoop`, with [separate version registrations][orchestrator-registry]. This worker's explicit `CurrentOrOlder` policy permits version 1 work alongside version 2, and the registry supplies both implementations. Those are two separate requirements.

[`Reject`][worker-options] sends mismatched work back for another attempt. It does not upgrade the work or guarantee that an eligible worker exists. Keep support for version 1 while executions still need it.

After starting the host, an already resolved `DurableTaskClient client` can schedule the illustrative version 1 instance:

```csharp
string instanceId = await client.ScheduleNewOrchestrationInstanceAsync(
    "BatchLoop",
    input: new BatchCheckpoint(42),
    options: new StartOrchestrationOptions
    {
        Version = new TaskVersion("1"),
    });
```

The starter's `await` returns the instance ID after scheduling, not after the workflow finishes. `42` is our illustrative checkpoint value. The next execution receives that count and `MigrationRequested = true`, but a new execution ID and version 2.

Follow the next sequence from top to bottom. The instance ID stays the same across the boundary. The two worker activations represent different executions, not a suspended v1 method being resumed as v2. The same eligible process can handle both, or different compatible workers can do so. Click to enlarge.

[![Sequence showing one BatchLoop instance scheduled at version 1, whose first execution returns a ContinueAsNew action carrying its checkpoint and requesting version 2. DTS creates a new execution of the same instance with fresh history, and an eligible worker invokes the registered version 2 implementation. Old CLR state and completed execution history do not cross the boundary.](/assets/durable-task-hidden-capabilities/continue-as-new-version.svg)](/assets/durable-task-hidden-capabilities/continue-as-new-version.svg)

*Figure 2. The supported migration path: same instance, new execution, explicit checkpoint. The worker shown has both versions registered. Keep compatible old and new implementations available while existing work still needs them. Arrows show logical order, not measured delivery timing.*

### Put the boundary where the workflow already has one

The tiny v1 above does nothing before continuing. For an existing eternal workflow, the useful migration technique is to update its **existing final continuation call** to request the new version, while keeping the earlier durable calls and data contracts compatible with its history. It is not a license to insert a new activity wherever the old execution happens to be waiting.

Finish and await work whose results matter before continuing. Outstanding operation results can be discarded at the boundary. That does not mean an activity already affecting an external system has been cancelled or rolled back.

`PreserveUnprocessedEvents = true` is explicit here and is also the default for this .NET option. It preserves unprocessed external events for the next execution; `false` discards them. The new code must understand both the carried input and any preserved event payloads. Fresh history does not mean an empty workflow with no starting records, and it does not promise that the service purges every diagnostic record.

Finally, return immediately after requesting `ContinueAsNew`. This is an action from a running orchestration, not an operator command for reviving a failed one. Putting it in `finally` is not a reliable plan for recovering an uncaught failure.

Which brings us to the third capability.

## Repair a failed instance without rerunning every successful step

Consider an import workflow: extract a batch, transform it, then load it into a destination. Extraction and transformation succeed and their results are recorded. Loading then fails because of a configuration problem.

You fix the configuration. Do you have to request the whole import again?

For an eligible failed instance, [rewind][management-doc] provides a more targeted recovery path. It is an explicit operator request after a failure, not ordinary replay, not a retry policy, and not a version migration.

Here is the workflow we'll follow. The activity results are references to the extracted and transformed data, not large datasets carried through the example:

```csharp
using System.Threading.Tasks;
using Microsoft.DurableTask;

public sealed record LoadRequest(string BatchId, string ManifestReference);

public sealed class ImportBatch : TaskOrchestrator<string, string>
{
    public override async Task<string> RunAsync(
        TaskOrchestrationContext context, string batchId)
    {
        string extracted = await context.CallActivityAsync<string>(
            "ExtractBatch", batchId);
        string transformed = await context.CallActivityAsync<string>(
            "TransformBatch", extracted);
        return await context.CallActivityAsync<string>(
            "LoadBatch", new LoadRequest(batchId, transformed));
    }
}
```

Register `ImportBatch` and the named activity implementations on compatible workers in the same hub. Their actual I/O is omitted. This illustration uses **no durable timers and no retry policy that creates durable timers**: the current management documentation excludes orchestrations that use durable timers from rewind.

Suppose the loading failure makes this instance `Failed`. Before requesting recovery, fix the cause **and reconcile any partial writes**. The loader may have changed the destination before reporting failure. The destination has not agreed to forget that just because we found a useful SDK method.

The operator can then use this helper:

```csharp
using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.DurableTask.Client;

public static class ImportRecovery
{
    public static async Task RequestRewindAsync(
        DurableTaskClient client,
        string instanceId,
        string reason,
        CancellationToken cancellation = default)
    {
        OrchestrationMetadata? instance = await client.GetInstanceAsync(
            instanceId, getInputsAndOutputs: false,
            cancellation: cancellation);

        if (instance?.RuntimeStatus != OrchestrationRuntimeStatus.Failed)
        {
            throw new InvalidOperationException(
                "Rewind requires an existing Failed instance.");
        }

        await client.RewindInstanceAsync(
            instanceId, reason, cancellation);
    }
}
```

`reason` should describe the repair or reconciliation that actually happened. The state check is a useful preflight, not an atomic lock: another operator can act between the read and the request. The backend still validates eligibility. Rewind is for `Failed` instances, not `Running`, `Pending`, `Terminated`, or `Completed` ones.

The [.NET client contract][client-api] describes a new execution ID for the same instance, with usable history that excludes the failed work so it can be attempted again. The orchestration code can reconstruct the recorded extraction and transformation results without executing those successful activity bodies again. It can then request another load attempt.

That does not restore a saved instruction pointer, and it does not automatically change the workflow's version. Keep the earlier action sequence replay compatible, and keep the referenced data and serialization contracts available.

The next diagram separates the failed execution from the operator's repair and rewind request. The initial orchestration passes are condensed; the recorded successes are shown so it is clear what the later execution can reuse. There is no arrow that undoes the destination's writes. Click to enlarge.

[![Conceptual recovery sequence for an ImportBatch workflow without durable timers. ExtractBatch and TransformBatch outcomes are recorded, LoadBatch fails, and the instance becomes Failed. An operator repairs the cause and reconciles external writes before requesting rewind. A new execution reuses successful recorded results and requests LoadBatch again. Accepting the rewind request is not proof of completion, and it does not roll back external effects.](/assets/durable-task-hidden-capabilities/failed-instance-rewind.svg)](/assets/durable-task-hidden-capabilities/failed-instance-rewind.svg)

*Figure 3. Repair first, then request rewind. Successful recorded results support reconstruction; failed loading work may run again. This is a conceptual successful scheduling path for an eligible instance, not an executed failure test or a guarantee that the next load attempt succeeds.*

The important operational detail is what the management `await` means. [`RewindInstanceAsync`][client-api] completes when the request is enqueued, not when the import is finished. Query the instance afterward. Cancelling that call cancels enqueueing; it does not undo a rewind that was already accepted. If the request's outcome is uncertain, inspect the instance rather than blindly repeating the operator action.

This example is scoped to the public .NET API and a backend that supports rewind. Other clients, hosts, or providers should not be assumed to have identical support just because they share a backend name. An unsupported backend can reject the operation.

And please keep a business key for the loading operation. `BatchId` gives the destination something stable to deduplicate on, **if the integration actually implements that contract**. Merely passing the field does not create idempotency. An execution ID is a poor replacement here because rewind creates another execution.

Fix what broke, reconcile what may already have happened, then ask the failed instance to continue. Rewind is not external rollback, and a new attempt still has to handle its effects correctly.

## The workflow is not the deployment

These capabilities solve different problems. Filtering chooses which workers can execute work. A continuation boundary deliberately moves the same instance into another execution and implementation. Rewind lets an operator request recovery after fixing an eligible failure, using the successful history that is still useful.

None of them removes the need for compatible code and data contracts, or careful handling of external effects. They give us better ways to manage those boundaries without building another workflow coordinator around the workflow coordinator.

That is what I meant by hidden gems. Once history and actions stop looking like magic, the interesting part is what they let us change safely around a running system.

[previous-post]: https://www.tamirdresher.com/blog/2026/09/21/durable-await-replay
[sdk-release]: https://github.com/microsoft/durabletask-dotnet/releases/tag/v1.26.0
[filter-doc]: https://learn.microsoft.com/en-us/azure/durable-task/scheduler/work-item-filtering
[filter-builder]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Core/DependencyInjection/DurableTaskWorkerBuilderExtensions.cs
[continue-options]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/ContinueAsNewOptions.cs
[migration-readme]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/samples/EternalOrchestrationVersionMigrationSample/README.md
[migration-program]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/samples/EternalOrchestrationVersionMigrationSample/Program.cs
[orchestrator-registry]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/DurableTaskRegistry.Orchestrators.cs
[worker-options]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Core/DurableTaskWorkerOptions.cs
[management-doc]: https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-instance-management#rewind-orchestration-instances
[client-api]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Client/Core/DurableTaskClient.cs
[filter-model]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Core/DurableTaskWorkerWorkItemFilters.cs
[activity-registry]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/DurableTaskRegistry.Activities.cs
[task-options]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Abstractions/TaskOptions.cs
[filter-validator]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Core/DependencyInjection/DurableTaskWorkerWorkItemFiltersValidator.cs
[filter-worker]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcDurableTaskWorker.cs
[filter-request]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Grpc/GrpcDurableTaskWorker.Processor.cs
[filter-protocol]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Grpc/orchestrator_service.proto
[filter-factory]: https://github.com/microsoft/durabletask-dotnet/blob/92474e9e35c66d64de36cabd0a17652376d37873/src/Worker/Core/DurableTaskFactory.cs
