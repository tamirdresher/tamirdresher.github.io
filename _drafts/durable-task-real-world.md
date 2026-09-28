---
layout: post
title: "Durable Task in the Real World: What Problems Does It Actually Solve?"
tags: [dotnet, durable-task-sdk, durable-task-scheduler, orchestration, workflows, ai-agents]
---

*Five practical examples of when durable execution makes sense, when it doesn't, and what it means for AI agents.*

After my last couple of posts about Durable Task, I got a comment that made me realize I had skipped an important question:

*This all looks interesting, but what are the actual use cases?*

Not how Durable Task works. Not what happens during replay or how the scheduler persists state. But the more practical question: what problems does it actually solve?

When should I reach for durable execution instead of regular C#, a queue, a database, or a background worker? And when would adding it just make things more complicated?

Those are fair questions. Rather than walk through another hello world orchestration, I want to look at real situations where things get messy, especially when work takes a long time, depends on external systems, or gets interrupted halfway through. I also want to be clear about what Durable Task does not solve for you.

Imagine a background worker creating a customer's Azure environment. It provisions a network, starts a database deployment, creates storage, and deploys an application. Then the worker disappears. Azure might still be working, but your local variables and continuations are gone. Restarting the method is easy. Figuring out which operations completed and which are safe to repeat is the hard part.

Of course, you could build your own solution with a database, a queue, an outbox, scheduled jobs, and reconciliation logic. Sometimes that's exactly what you should do. But once you find yourself building a whole system just to remember what happens next and how to resume it, durable orchestration starts to get interesting.

I'll walk through five examples: invoice approvals, Azure tenant provisioning, subscription payments, breaking news articles arriving through out of order webhooks, and an AI agent investigating an incident. We'll use the standalone [Durable Task .NET SDK v1.26.0](https://github.com/microsoft/durabletask-dotnet/releases/tag/v1.26.0) with DTS, and I'll show both the useful parts and the responsibilities that still belong to our application.

If you want the background first, I covered [what happens at a durable await](https://www.tamirdresher.com/blog/2026/09/21/durable-await-replay) and [three less obvious Durable Task capabilities](https://www.tamirdresher.com/blog/2026/09/25/durable-task-hidden-capabilities) in the previous two posts.

**A note on the examples:** The snippets below are deliberately focused on orchestration boundaries. Application adapters, DTO definitions, registrations, and some helper implementations are omitted. They illustrate the design rather than constituting a compiled, tested sample. In particular, do not infer exactly-once external effects from durable history.

## 1. An invoice needs approval. Why should the worker remember the wait?

Consider an invoice-processing service. It extracts a document, validates the result, and either posts the invoice, rejects it, or asks a human to review it. A batch may contain eight invoices, only one of which needs approval. The other seven shouldn't wait for it.

Here's an ordinary C# implementation of the individual processing path:

```csharp
public static async Task<InvoiceResult> ProcessAsync(
    InvoiceJob invoice, IInvoiceApplication app, CancellationToken ct)
{
    InvoiceCandidate candidate = await app.ExtractInvoiceAsync(invoice, ct);
    InvoiceAssessment assessment = await app.ValidateInvoiceAsync(candidate, ct);

    if (assessment.Check == InvoiceCheck.NeedsReview)
    {
        await app.OpenInvoiceReviewAsync(
            new InvoiceReview(invoice, assessment.PayloadReference), ct);
        return new(invoice.InvoiceKey, "AwaitingReview");
    }

    if (assessment.Check == InvoiceCheck.Rejected)
        return new(invoice.InvoiceKey, "Rejected");

    if (assessment.Check != InvoiceCheck.Valid)
        throw new InvalidOperationException("Unrecognized invoice assessment.");

    AccountingReceipt receipt = await app.SubmitApprovedInvoiceAsync(
        new InvoiceCandidate(invoice, assessment.PayloadReference), ct);
    return new(invoice.InvoiceKey, "Posted", receipt.EntryReference);
}
```

There's nothing inherently unreliable about this method. `OpenInvoiceReviewAsync` can persist a review ticket and notification outbox. But when someone approves the invoice tomorrow, *another* handler must load the right document generation, check the deadline, recover the approved payload, and continue. If the worker dies between extraction and validation, the application must decide whether to extract again or retrieve the saved result.

That continuation protocol is what Durable Task can express directly.

### Give each invoice its own durable history

A bounded batch can start independent child orchestrations:

```csharp
public override async Task<InvoiceResult[]> RunAsync(
    TaskOrchestrationContext context, InvoiceBatch batch)
{
    if (batch.Invoices is null || batch.Invoices.Length is < 1 or > 8
        || batch.Invoices.Select(x => x.InvoiceKey).Distinct().Count()
           != batch.Invoices.Length)
        throw new ArgumentException("Supply 1 to 8 distinct invoices.");

    return await Task.WhenAll(batch.Invoices.Select(invoice =>
        context.CallSubOrchestratorAsync<InvoiceResult>(
            nameof(ProcessInvoice), invoice)));
}
```

Eight is an application admission limit, not a DTS quota. Larger batches can be paged and subject to tenant/global concurrency limits. A child that completes can post its invoice while another child remains suspended awaiting review. `Task.WhenAll` waits for every child; it does not undo a sibling's accounting entry if another child fails.

Inside the invoice child, extraction and validation are activities. Once their successful results are recorded in orchestration history, a compatible replay follows the same code path using those recorded results instead of repeating the activities. This is **re-execution of orchestrator code against history**, not restoration of a suspended CLR stack.

When validation requires review, the child can express the wait:

```csharp
var review = new InvoiceReview(invoice, assessment.PayloadReference);
await context.CallActivityAsync("OpenInvoiceReview", review);

TimeSpan remaining =
    invoice.ReviewDeadlineUtc - context.CurrentUtcDateTime;

if (remaining > TimeSpan.Zero)
{
    try
    {
        InvoiceReviewHint hint =
            await context.WaitForExternalEvent<InvoiceReviewHint>(
                $"invoice-review:{invoice.ReviewId}", remaining);

        if (hint.ProcessingId != invoice.ProcessingId
            || hint.ReviewId != invoice.ReviewId)
            throw new InvalidOperationException("Review identity mismatch.");
    }
    catch (OperationCanceledException)
    {
        // The durable wait timed out. Read the committed decision below.
    }
}

InvoiceDecision decision =
    await context.CallActivityAsync<InvoiceDecision>(
        "ResolveInvoiceReview", review);
```

The timer is durable. No thread is occupied while the invoice waits, and a replacement worker can replay the child to the same pending wait. But the event is **only a hint**. An authenticated endpoint must atomically commit a single terminal review decision to the application's review store before signaling the child. `ResolveInvoiceReview` reads or closes that authoritative ticket, including when the timer fires. If approval was committed just before the deadline but the hint arrived just after it, the stored decision, not notification timing, determines the outcome.

Only a valid automatic assessment or a committed human approval may proceed to the accounting activity. That activity uses a stable posting key and immutable request fingerprint. If the accounting system accepted the post but the activity's acknowledgement vanished, the integration must reconcile the same posting identity. Durable history cannot promise exactly-once accounting.

This is the part I like. Instead of building separate handlers to remember extraction, validation, the review wait, and posting, I can describe the whole process in one place and let Durable Task remember where it got to. I still need to authorize reviewers, persist their decisions, and make accounting submissions safe to repeat. If my existing continuation handlers already do all of that cleanly, I might not need another runtime.

## 2. Tenant provisioning: the cloud already has a deployment engine

Now consider onboarding a SaaS tenant. A `TenantCreated` event means the tenant record was accepted, not that its environment is ready. This design provisions a dedicated network, PostgreSQL server, storage with private access, and Container App; then it configures DNS, checks readiness, and activates the tenant.

The ordinary C# method is easy to read:

```csharp
public async Task<ProvisionedEnvironment> ProvisionAsync(
    EnvironmentRequest request,
    CancellationToken cancellationToken = default)
{
    NetworkResources network = await azure.CreateVirtualNetworkAsync(
        request, cancellationToken);

    Task<PostgreSqlServerReference> databaseTask =
        azure.CreatePostgreSqlServerAsync(
            request, network.PostgreSqlSubnet, cancellationToken);
    Task<StorageAccountReference> storageTask =
        azure.CreateStorageAccountAsync(
            request, network.StoragePrivateEndpointSubnet,
            cancellationToken);

    await Task.WhenAll(databaseTask, storageTask);

    ContainerAppReference application = await azure.DeployContainerAppAsync(
        request, network.ContainerAppsSubnet,
        await databaseTask, await storageTask, cancellationToken);

    await azure.CreateDnsRecordAsync(
        request, application.Endpoint, cancellationToken);
    await azure.WaitForApplicationReadyAsync(
        application.Endpoint, cancellationToken);

    return new ProvisionedEnvironment(
        request.EnvironmentId, application.Endpoint);
}
```

The helpers above wrap Bicep/ARM operations and wait for terminal completion or readiness. They're application abstractions, not Azure SDK methods. The parallel modules own disjoint resources and don't compete over subnet updates.

Before adding DTS, ask an uncomfortable question: **does ARM already solve this?** For a single well-defined deployment, it may. ARM/Bicep already supports dependency ordering, parallel deployment, idempotent reapplication with stable identities, and server-side deployment state. A worker crash doesn't erase an ARM deployment. Querying it and reapplying the same desired state may be sufficient.

The wider onboarding process is different. The application must acknowledge the tenant request, report progress, coordinate readiness with activation, survive external approval steps if any, and decide what to do with a partly provisioned environment. That's where a business-level workflow can add value.

### Separate resource readiness from tenant activation

First, the API authorizes and durably admits an immutable onboarding request, then returns `202 Accepted`, a request ID, and a status URL. Accepted does not mean ready. The application records the tenant, environment, immutable specification, and ownership generation. Reusing the same idempotency key with the same specification returns the existing request; changing the specification is rejected.

The scheduler handoff is not magically atomic with the application's database. Save the intent to start in an outbox alongside admission; dispatch it and reconcile the workflow identity. Repeatedly scheduling a new instance is not the same as resuming an existing one.

The outer orchestration can then express the business dependency:

```csharp
public override async Task<TenantActivation> RunAsync(
    TaskOrchestrationContext context, EnvironmentPlan plan)
{
    EnvironmentResult resources =
        await context.CallSubOrchestratorAsync<EnvironmentResult>(
            nameof(ProvisionEnvironment), plan);

    return await context.CallActivityAsync<TenantActivation>(
        "ActivateTenant", new TenantActivationRequest(plan, resources));
}
```

The child finishes at **resource readiness**. Activation is a separate, idempotent application activity that revalidates tenant ownership and actual resource readiness. If activation fails, the outer workflow fails visibly without automatically deleting the resources the child provisioned. Repairing activation is a different problem from rolling back provisioning.

Inside the child, stage dependencies form waves: network; database and storage in parallel; application; DNS; readiness. Each stage activity records an intent and starts or reconciles a provider operation. A separate read activity performs one bounded provider status query; the orchestrator schedules a durable timer between polls using `context.CurrentUtcDateTime` and `context.CreateTimer`.

```csharp
DateTime now = context.CurrentUtcDateTime;
if (now >= deadline)
    return Failed("PollingDeadlineExceeded");

TimeSpan delay = TimeSpan.FromSeconds(progress.PollAfterSeconds);
DateTime wakeAt = delay >= deadline - now
    ? deadline
    : now.Add(delay);

await context.CreateTimer(wakeAt, CancellationToken.None);
```

No HTTP request or `Task.Delay` runs inside the orchestrator. The activity does the I/O; the orchestration history records the activity result and timer decision. A 45-minute polling budget limits additional polling. It **does not cancel an Azure operation** that was already accepted.

### Follow one failure all the way through

Imagine the database deployment was accepted by Azure, but the worker died before the activity completion reached DTS:

1. DTS does not have a recorded successful activity result, so activity redelivery is possible.
2. The redelivered adapter consults the application's operation journal and the stable Azure deployment/resource identity.
3. If the deployment is still running, it resumes inquiry rather than starting an unrelated database.
4. Once the provider returns terminal completion, the activity records the result and the child continues toward application deployment.
5. The tenant is activated only after the resource child returns validated readiness evidence.

Contrast that with a different failure: the activity completion *was* recorded, and only then the worker crashed. On compatible replay, the orchestrator consumes that result from history without invoking the completed activity again. These are different failure windows; durable execution history solves one, and your adapter's reconciliation protocol solves the other.

### Compensation isn't an undo button

A failed workflow doesn't mean Azure stopped working. Imagine that we've started creating a database and a storage account in parallel. Storage provisioning fails, but Azure is still creating the database. If we immediately delete everything we can see, that database might finish provisioning *after* cleanup has already checked for it. We've now reported failure and cleanup while an orphaned database continues generating charges.

Before cleaning up, the application needs to:

1. Prevent this failed onboarding attempt from submitting any new provisioning operations.
2. Check previously submitted operations, including requests whose responses were lost, and reconcile their actual state. Don't assume a timeout or a failed worker stopped Azure.
3. Delete only resources created exclusively for this attempt, and only after establishing that outstanding operations cannot create them again after deletion.

Automatic cleanup also has a strict boundary: this must be a failed **initial** onboarding attempt, before tenant activation or customer-data admission. Existing shared resources and active customer data are never cleanup targets. Recheck current ownership and provider identity before each deletion, and delete eligible new resources in reverse dependency order: DNS, application, database/storage, then network.

If we cannot establish what is still running or what we safely own, retain the resources and surface `NeedsIntervention` for reconciliation rather than guessing. Record both the original provisioning failure and any cleanup failures. Durable Task can coordinate this recovery process, but it cannot decide which Azure resources are safe to delete.

> **Going deeper: fencing and draining in-flight operations**  
> Two related ideas explain why cleanup is harder than reversing completed steps:
>
> - **[Fencing](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html#making-the-lock-safe-with-fencing)** prevents outdated attempts from making new changes, provided the system receiving those changes enforces the restriction. For example, our application can reject submissions from an older provisioning generation. This does **not** revoke requests Azure already accepted.
> - **Draining and reconciling in-flight operations** means accounting for previously submitted work, including requests whose acknowledgements were lost, before declaring cleanup safe. Some distributed-systems discussions call reaching a state with no relevant outstanding work **quiescence** (from *quiescent*, meaning quiet or inactive). Here we're describing a practical cleanup requirement, **not** the formal concurrency property *quiescent consistency* and not a guarantee Azure provides automatically.
>
> For background, see [Martin Kleppmann's explanation of fencing tokens](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) and [Microsoft's ARM deployment cancellation API](https://learn.microsoft.com/en-us/rest/api/resources/deployments/cancel?view=rest-resources-2025-04-01). Even cancellation may leave resources partially deployed. If we cannot establish that earlier requests can no longer create resources, we retain the environment for reconciliation rather than declaring cleanup complete.

There is one thing to keep in mind here. `Task.WhenAll` waits for the whole provisioning wave, but if one of those activities throws, execution will not continue to the code that checks the results. In this example I treat expected failures as results and let unexpected failures fail the orchestration normally.

This also matters for cleanup. Waiting for all the provisioning tasks to finish tells me what succeeded and what failed, so I know what needs to be cleaned up. It does not automatically perform that cleanup. I still need to explicitly run the compensation steps for the resources that were already created.

Here, Durable Task is useful for connecting resource provisioning, the long waits, and tenant activation without writing my own continuation state machine. ARM still provisions the resources. My application still needs an outbox, operation identities, safe cleanup, and a way to repair uncertain outcomes. I would not add Durable Task just to rebuild the dependency graph ARM already gives me.

## 3. A payment timeout is not a decline

Suppose a subscription charge times out. The provider may have accepted the payment before the response disappeared. A naive retry risks charging twice; a naive decline path risks sending a misleading reminder.

A conventional implementation can persist `NextCheckUtc`, finish its handler, and let a scheduled job inquire later. That's a reasonable architecture. A durable orchestration becomes interesting when the recovery policy also includes due dates, callbacks, bounded reminders, a fixed grace deadline, and transition to the next billing cycle.

Before going further, **a billing cycle means one billing period and its associated payment obligation**, not one charge attempt or the entire subscription. For a €20 monthly subscription, September and October are separate cycles. Each has its own `CycleId`, due date, and initial `PaymentKey`; both belong to the same `SubscriptionId`. `GraceUntilUtc` sets the deadline for this cycle’s automated recovery. If a payment times out, the cycle remains the same while the service investigates whether that attempt actually succeeded.

| Billing cycle | Due date | Amount | Example state |
| --- | --- | ---: | --- |
| September 2026 | Sep 1 | €20 | Paid |
| October 2026 | Oct 1 | €20 | Pending |
| November 2026 | Nov 1 | €20 | Not started |

The distinction matters for `ContinueAsNew`. Once a paid receipt is confirmed and the billing service authoritatively plans the next cycle, the orchestrator can continue with **new cycle input** while retaining its instance ID and starting a fresh execution history:

[![Paid billing cycles advance with new cycle input; uncertain payments remain in reconciliation.](/assets/durable-task-real-world/billing-cycles.svg)](/assets/durable-task-real-world/billing-cycles.svg)

*Each confirmed paid cycle closes before ContinueAsNew receives the next cycle.*

This is a conceptual lifecycle, not a promise that each month will be charged successfully. An unresolved cycle does **not** automatically advance, and the billing service, not the orchestrator, decides whether a next cycle is permitted.

Here the billing ledger, not DTS, is authoritative. The billing store binds a cycle ID and stable payment key to the amount and currency. Payment state distinguishes `Unknown`, `Pending`, `Declined`, `Paid`, and `NotCharged`, with cancellation and receipt information. The workflow coordinates inquiries and reminders. A separate payment service owns any newly authorized charge after card correction.

The orchestration waits until the cycle's due date with a durable timer, then calls an activity that either initiates the initial payment **only when authorized and definitively not submitted**, or reconciles an existing paid, pending, or unknown attempt. Its recovery loop checks state and waits for a callback hint or the next six-hour check, whichever comes first:

```csharp
DateTime now = context.CurrentUtcDateTime;
if (now >= cycle.GraceUntilUtc || check == 15)
    break;

if (!reminderSent && !payment.SubscriptionCancelled
    && payment.State == PaymentState.Declined
    && now >= cycle.DueUtc.AddHours(6))
{
    await context.CallActivityAsync(
        "SendPaymentReminder",
        new PaymentReminder(cycle, $"{cycle.CycleId}:reminder-1"));
    reminderSent = true;
}

now = context.CurrentUtcDateTime;
if (now >= cycle.GraceUntilUtc)
    break;

DateTime wakeAt = now.AddHours(6);
if (wakeAt > cycle.GraceUntilUtc)
    wakeAt = cycle.GraceUntilUtc;

try
{
    BillingHint hint = await context.WaitForExternalEvent<BillingHint>(
        $"billing:{cycle.CycleId}:v{cycle.EventSchema}", wakeAt - now);

    if (hint.CycleId != cycle.CycleId
        || hint.EventSchema != cycle.EventSchema
        || string.IsNullOrWhiteSpace(hint.EventId))
        throw new InvalidOperationException("Billing event identity mismatch.");
}
catch (OperationCanceledException)
{
    // Timer elapsed. Query the billing ledger.
}

payment = await context.CallActivityAsync<PaymentSnapshot>(
    "ReadCyclePayment", cycle);
```

This excerpt assumes the surrounding orchestrator has validated the cycle, UTC deadlines, grace interval, snapshot identity, and terminal paid/cancellation branches. It also bounds the loop to at most 16 inspected snapshots. Callback handlers authenticate, deduplicate, and persist events in the billing inbox/ledger before sending a hint. Neither a callback nor a payment-method update proves that a charge succeeded.

When a paid receipt is validated, an idempotent activity closes the paid cycle and obtains the authoritative next cycle. Only then does the orchestrator call `context.ContinueAsNew(next, preserveUnprocessedEvents: false)` with that next-cycle input. That preserves the instance identity while starting a fresh execution history. Here we deliberately discard buffered old hints because the billing facts were persisted before notification; old settlements remain tied to their original billing cycle.

If the grace or check budget expires with an unresolved payment, the application outcome is `NeedsReconciliation`, tracked by a durable recovery queue. Runtime completion isn't proof of payment. Cancellation stops future collection when recorded but doesn't erase an already accepted charge.

I like being able to read the payment recovery policy as one flow, with its due date, callbacks, reminders, and transition to the next cycle. But the billing ledger still decides whether a payment actually happened. The workflow does not get to guess, charge again, or replace the existing payment safeguards. And if one scheduled job already handles this without much ceremony, I would keep that instead.

## 4. Webhook bursts: an example where durable state may not be enough

Imagine a breaking-news publisher. Editors keep updating a developing story as new information arrives, and readers expect the publisher's search results to show the latest published version. Every time an editor publishes a change, the content-management system (CMS) emits a webhook. Our service receives it and updates a separate search index.

For example, an article titled *Major storm hits the coast* has three published revisions:

- **Revision 11:** the initial report.
- **Revision 12:** updated casualty figures and evacuation information.
- **Revision 13:** a corrected headline and the latest official statement.

The webhook for revision 12 arrives before the delayed notification for 11; another webhook for 12 arrives twice. While our search index is still processing revision 12, revision 13 is published. Worse, two indexing operations can finish in the opposite order from when they started. Without protection, a slow revision-12 update could overwrite revision 13, leaving readers with stale breaking-news results.

Here's the flow. The arrows show *possible* timing, not a promise of ordering:

[![Multiple controllers use activities to read CMS snapshots and write the search index; the index rejects a stale revision.](/assets/durable-task-real-world/news-multiple-controllers.svg)](/assets/durable-task-real-world/news-multiple-controllers.svg)

*Entity counters do not serialize index writes. The destination rejects the late revision-12 update.*

**The key distinction:** the durable entity remembers the newest revision we've *heard about*. It does not lock the search index or guarantee that only one indexing activity runs. The search destination must atomically reject an older revision if a newer one has already been committed. In the diagram, the delayed revision-12 operation is rejected rather than overwriting revision 13. A separate reliable inbox and follow-up dispatcher ensure that newly published revisions aren't lost between checks.

For this example, assume the CMS supplies strictly increasing positive revision numbers per article generation, immutable content for each published revision, and versioned tombstones for deletion. A recreated article gets a new generation. If the CMS supplies only opaque ETags or webhook arrival timestamps, this particular revision-ordering algorithm does not apply.

A conventional handler can already be correct:

```csharp
public static async Task HandleAsync(
    DocumentNotice notice, IDocumentProjection projection,
    IProjectionCheckpointStore checkpoints, CancellationToken ct)
{
    long applied = await checkpoints.ReadAppliedAsync(
        notice.DocumentKey, ct);
    if (notice.Revision <= applied)
        return;

    DocumentSnapshot snapshot =
        await projection.ReadDocumentSnapshotAsync(
            new DocumentRead(notice.DocumentKey, notice.Revision), ct);

    ProjectionReceipt receipt =
        await projection.ApplyDocumentRevisionAsync(snapshot, ct);

    await checkpoints.AdvanceAppliedAsync(receipt, ct);
}
```

This assumes the destination atomically rejects stale revisions and handles duplicates idempotently, while the checkpoint advances monotonically. A lost acknowledgement can be reconciled against the destination. Add a reliable inbox/dispatcher and periodic source reconciliation, and you may already have everything you need.

What does a durable entity change? It can persist the highest observed and applied revisions and serialize **updates to those counters**:

```csharp
public sealed class DocumentRevision : TaskEntity<DocumentRevisionState>
{
    public void Observe(long revision)
    {
        if (revision <= 0)
            throw new ArgumentOutOfRangeException(nameof(revision));
        State.LastObserved = Math.Max(State.LastObserved, revision);
    }

    public RevisionProgress Read() =>
        new(State.LastObserved, State.LastApplied);

    public void ConfirmApplied(ProjectionReceipt receipt)
    {
        if (receipt.DocumentKey != Context.Id.Key
            || receipt.ConfirmedRevision <= 0
            || string.IsNullOrWhiteSpace(receipt.ReceiptReference))
            throw new InvalidOperationException("Invalid projection receipt.");

        State.LastApplied = Math.Max(
            State.LastApplied, receipt.ConfirmedRevision);
    }
}
```

A separate `SynchronizeDocument` orchestration calls `Observe`, waits two seconds with a durable timer, reads the entity, fetches an authoritative immutable snapshot through a read activity, applies it through a write activity, and calls `ConfirmApplied` only after obtaining a valid external receipt. It can make up to four passes, then request follow-up if work remains.

> **Two different identities, two different guarantees.** A durable entity is addressed by its **entity name and key**. In this example, `DocumentRevision` plus the article's generation-qualified key identifies one entity. Durable Task processes operations for that *same entity instance* serially, so simultaneous `Observe` and `ConfirmApplied` calls cannot corrupt its counters. This does **not** mean Durable Task automatically runs only one `SynchronizeDocument` orchestration per article: by default, separately scheduled orchestrations have separate instance IDs. See [Microsoft: Durable entities](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-entities) and [orchestration instance identity](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-orchestrations).

If we want **one active synchronization controller per article**, we can deliberately adopt the [singleton orchestrator pattern](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-singletons): assign a stable orchestration instance ID derived from the article's generation-qualified key, rather than creating a new instance for each webhook. The inbox records every notice; the entity keeps the highest observed revision; the dispatcher starts the controller if needed or signals the existing controller to check again. The inbox must also cover the race between a controller's final read and its completion. A check-then-start request can itself race, so the dispatcher must handle duplicate-start outcomes and reconcile admission rather than assume both callers' success responses mean two controllers started.

[![A dispatcher reconciles stable controller admission while activities read the CMS and write to a revision-protected search index.](/assets/durable-task-real-world/news-singleton.svg)](/assets/durable-task-real-world/news-singleton.svg)

*A singleton controller still needs reliable admission, follow-up dispatch and the destination's atomic revision check.*

A singleton controller avoids *concurrent controllers* for the same article when admission is implemented correctly, but it is **not** an exactly-once guarantee for external effects. A timed-out or redelivered activity may have left an indexing request running, and an earlier execution may have submitted work before it stopped. Keep the destination's atomic revision check and reconcile uncertain writes even with a singleton controller. The sequence diagram above intentionally depicts the **multiple-controller variant**, to show the race that the entity's serialization alone does not prevent.

But here's the catch: **serializing entity operations does not serialize the external index writes**. Two orchestrations can both read `LastObserved = 13` and `LastApplied = 12`, then fetch and attempt revision 13 concurrently. The two-second pause may even align them. This design does not establish fewer fetches, fewer writes, or true debounce behavior.

Its correctness still depends on a destination-enforced atomic generation/revision fence. A delayed revision-12 write cannot overwrite an already committed revision 13. If the destination cannot enforce that rule, introduce a separately enforced single writer or fenced-writer protocol instead. The entity alone is insufficient.

A final read also races with a newly arriving revision. The application inbox/outbox must durably admit every validated notice and dispatch follow-up work; periodic reconciliation handles missing webhooks. Resetting an entity cannot reset the destination's revision protection.

The entity gives us a durable place to remember the latest article revision, and its operations are serialized for that entity key. That is useful, but it does not magically serialize the external indexing requests. If our existing checkpoint store and dispatcher already coordinate revisions reliably, adding an entity might not buy us much. I would measure actual indexing calls before claiming this approach reduces work.

## 5. An AI-assisted incident workflow: preserving the exact decision across a crash

I have written before about [this kind of AI workflow and why deterministic orchestration matters](https://www.tamirdresher.com/blog/2026/05/21/deterministic-meets-squads) when models and tools are involved. In that post, I focused mostly on making the workflow predictable. I did not spend nearly enough time on what happens when the process disappears halfway through. That is what I want to explore here.

Consider a production incident assistant: it gathers telemetry, asks a model to propose a remediation, waits for an engineer to approve the *specific* proposal, runs the approved operation, and verifies the result. The investigation might take minutes; approval might arrive hours later. During that time, the process hosting the assistant may be recycled or deployed.

We need parallel work, durable waits, replay, and external-operation reconciliation. We also face a new problem: an LLM response is not a deterministic function we should casually recompute after recovery. The next response might recommend a different action, use different tool arguments, or refer to different evidence.

### Before: an ordinary asynchronous agent pipeline

Suppose the application already has services for telemetry, model inference, approval, remediation, and verification. A simplified ordinary implementation might look like this:

```csharp
public static async Task<IncidentReport> InvestigateAsync(
    IncidentRequest incident,
    IIncidentApplication app,
    CancellationToken ct)
{
    Task<EvidenceRef> logs = app.CollectLogsAsync(incident, ct);
    Task<EvidenceRef> metrics = app.CollectMetricsAsync(incident, ct);
    await Task.WhenAll(logs, metrics);
    EvidenceBundle evidence = new(await logs, await metrics);

    ProposedRemediation proposal =
        await app.GenerateRemediationAsync(incident, evidence, ct);
    await app.OpenApprovalAsync(proposal, ct);

    // A separate callback must resume the right proposal after approval.
    return new IncidentReport(incident.IncidentId, "AwaitingApproval");
}
```

This method is not inherently wrong. The application could save a state machine in SQL and continue from an approval callback. But that continuation handler must retrieve the exact evidence and proposal version, check authorization and expiry, and decide whether remediation was already submitted. If the worker crashes after the model generates its proposal but before saving it, generating again is a *new* decision, not recovery of the same one.

The crucial design decision is to separate the **nondeterministic generation step** from the **deterministic coordination step**. The model call belongs inside an activity. The orchestrator receives a stable reference to an immutable proposal, not a mutable chat transcript or a promise that the model will answer identically next time.

### After: durable coordination around an agent

For this example, assume the application defines `IncidentPlan` with a stable incident ID, immutable request generation, approval ID and UTC deadline. `EvidenceBundle` contains references to saved telemetry, not raw logs. `ProposedRemediation` contains an immutable proposal ID, evidence references, canonical action parameters, a content fingerprint and policy version. `ApprovalDecision` names the approved proposal ID and fingerprint. These are **application contracts**, not types supplied by Durable Task.

The request records below name the payloads passed to activities. `ApprovalKind` distinguishes `Pending`, `Approved`, `Rejected`, and `Expired`; only approval can lead to remediation. The activities and remaining DTOs are application code, not a complete executable sample:

```csharp
public sealed record GenerateProposalRequest(
    IncidentPlan Plan, EvidenceBundle Evidence);
public sealed record RemediationApprovalRequest(
    IncidentPlan Plan, ProposedRemediation Proposal);
public sealed record VerifyRemediationRequest(
    IncidentPlan Plan, RemediationReceipt Receipt);

public sealed class InvestigateIncident
    : TaskOrchestrator<IncidentPlan, IncidentOutcome>
{
    public override async Task<IncidentOutcome> RunAsync(
        TaskOrchestrationContext context, IncidentPlan plan)
    {
        Task<EvidenceRef> logs = context.CallActivityAsync<EvidenceRef>(
            "CollectLogs", plan);
        Task<EvidenceRef> metrics = context.CallActivityAsync<EvidenceRef>(
            "CollectMetrics", plan);

        await Task.WhenAll(logs, metrics);
        EvidenceBundle evidence = new(await logs, await metrics);
        ProposedRemediation proposal =
            await context.CallActivityAsync<ProposedRemediation>(
                "GenerateAndSaveProposal",
                new GenerateProposalRequest(plan, evidence));

        await context.CallActivityAsync(
            "OpenRemediationApproval",
            new RemediationApprovalRequest(plan, proposal));

        TimeSpan remaining =
            plan.ApprovalDeadlineUtc - context.CurrentUtcDateTime;
        if (remaining > TimeSpan.Zero)
        {
            try
            {
                // This event is only a wake-up hint, not authorization.
                ApprovalHint hint =
                    await context.WaitForExternalEvent<ApprovalHint>(
                        $"incident-approval:{plan.ApprovalId}", remaining);
                if (hint.IncidentId != plan.IncidentId ||
                    hint.ApprovalId != plan.ApprovalId)
                    throw new InvalidOperationException(
                        "Approval identity mismatch.");
            }
            catch (OperationCanceledException)
            {
                // Deadline elapsed. Resolve authoritative approval state.
            }
        }

        ApprovalDecision decision =
            await context.CallActivityAsync<ApprovalDecision>(
                "ResolveApproval",
                new RemediationApprovalRequest(plan, proposal));
        if (decision.Kind is ApprovalKind.Rejected or ApprovalKind.Expired)
            return new(plan.IncidentId, decision.Kind.ToString());
        if (decision.Kind != ApprovalKind.Approved)
            throw new InvalidOperationException(
                "Approval is unresolved or unrecognized; reconcile the ticket.");

        // The activity must independently revalidate authorization,
        // proposal fingerprint, current policy and execution eligibility.
        RemediationReceipt receipt =
            await context.CallActivityAsync<RemediationReceipt>(
                "ExecuteApprovedRemediation",
                new ApprovedRemediation(plan, proposal, decision));

        VerificationResult verification =
            await context.CallActivityAsync<VerificationResult>(
                "VerifyRemediation",
                new VerifyRemediationRequest(plan, receipt));
        return new(plan.IncidentId, verification.Status,
            receipt.ReceiptReference);
    }
}
```

The snippet expresses dependencies, not a security boundary. The authenticated approval endpoint must atomically commit one terminal decision against the immutable proposal ID, fingerprint and deadline *before* sending its event hint. `ResolveApproval` reads that committed record or atomically expires a still-pending ticket at its deadline. An unresolved or unrecognized result fails visibly for reconciliation. A hint cannot authorize a tool call, and a late or duplicate hint cannot overwrite a terminal decision. The remediation activity checks the stored decision again and applies any current safety policy before acting. An approved plan that is no longer safe should stop for fresh review, not be executed merely because it appears in orchestration history.

Notice that `GenerateAndSaveProposal` must use a stable generation identity and reconcile its own saved result if the model responded but the activity acknowledgement was lost. Durable Task will reuse the activity result **only after that result was recorded in orchestration history**. It cannot guarantee a model is called exactly once in every failure window. Likewise, `ExecuteApprovedRemediation` needs a stable execution key, an operation journal and a provider-specific read/reconciliation path; blindly retrying a potentially destructive tool is unacceptable.

### Follow the failure, not just the happy path

Consider four points at which the worker might disappear:

| Interruption | Safe recovery behavior |
|---|---|
| After telemetry collection was recorded | Replay consumes recorded activity results; it does not collect those results again merely because the worker restarted. |
| After model generation but before its activity result was recorded | The activity uses the stable generation identity to retrieve the saved proposal or reconcile an uncertain generation; it must not silently substitute a new plan for one already presented. |
| While waiting for an engineer | The durable wait resumes after restart. Approval authority remains in the application approval store, and the fixed deadline does not move. |
| After remediation succeeded but before its activity completion was recorded | Redelivery reconciles the same execution key and external receipt. It does not assume the action failed or execute it a second time without evidence. |

A useful test deliberately kills the worker at each of those points. Then inspect orchestration history, the proposal and approval records, and the remediation operation journal. The invariant is not “the orchestrator completed.” It is “only the specifically authorized proposal was executed, and uncertain side effects were reconciled before further action.”

### So what did we gain?

We now have a workflow that can collect evidence, generate a proposal, wait for approval, execute the approved action, and continue after a worker restart. That is already pretty useful. But notice the boundary: we made the workflow around the AI durable. We did not make the model deterministic, and we did not make every bit of state inside an agent durable. The proposal and approval still need stable identities, and an uncertain tool execution still needs reconciliation.

This is really the foundation of what I want from durable AI systems. It is also why we went further and built **Durable Agents and Durable Workflows as extensions to Microsoft Agent Framework (MAF)**. Instead of having every application build this coordination around its agents, we wanted durability to be part of the way agents and their workflows run.

That deserves its own article. In the next part, I will use this same scenario to show what changes when durability moves from the outer orchestration into the agent and workflow programming model itself.

## A final thought

The common thread across these examples is simple. Durable Task can remember what completed, what we are waiting for, and where execution should continue. It cannot tell us whether an external payment really happened, whether an Azure operation is still running, or whether an AI generated action is still safe to execute. Our applications still need to answer those questions.

I would use Durable Task when the code for remembering and resuming a business process starts becoming a system of its own. Not just because I have a few `await` calls.

## Further reading

These are established patterns, and there is useful prior work if you want to dig deeper.

* [Microsoft Learn: Human interaction pattern](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-human-interaction)
* [Microsoft: Building durable and deterministic multi agent orchestrations](https://techcommunity.microsoft.com/blog/appsonazureblog/building-durable-and-deterministic-multi-agent-orchestrations-with-durable-execu/4408842)
* [Microsoft: Durable Task extension for Microsoft Agent Framework](https://techcommunity.microsoft.com/blog/appsonazureblog/bulletproof-agents-with-the-durable-task-extension-for-microsoft-agent-framework/4467122)
* [Elastic: Human approval in incident response automation](https://www.elastic.co/observability-labs/blog/incident-response-automation-human-approval-gate)
