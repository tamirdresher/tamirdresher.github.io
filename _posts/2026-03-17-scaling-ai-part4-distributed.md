---
layout: post
title: "Temporal for AI Teams — Multi-Agent Transactions That Roll Back"
date: 2026-03-17
tags: [ai-agents, squad, github-copilot, distributed-systems, saga-pattern, temporal, star-trek, borg]
series: "Scaling AI-Native Software Engineering"
series_part: 4
---

> *"The line must be drawn here! This far, no further!"*
> — Captain Picard, Star Trek: First Contact

In [Part 3](/blog/2026/03/18/scaling-ai-part3-distributed), I showed you how Squad became a distributed system — multiple machines, git-based task queues, heartbeat-driven failure detection. We solved the **coordination** problem: how do multiple AI agents on different machines avoid doing the same work twice?

But coordination is only half the story. There's a harder question lurking underneath everything we've built so far — and it bit me on a Tuesday afternoon.

---

## The Tuesday Everything Went Sideways

Here's what happened. I filed an issue: "Research distributed systems patterns and write a blog post about it." Simple enough. Picard decomposed it into three steps:

```
🎖️ Picard: Decomposing distributed-systems task...

   Step 1 → Seven: Write comprehensive research report
   Step 2 → Data: Implement the reconciliation loop pattern in Ralph
   Step 3 → Troi: Write the blog post based on Seven's research + Data's implementation

   Dependencies: Step 2 depends on Step 1. Step 3 depends on Steps 1 + 2.
```

Seven knocked out the research in about twenty minutes — a 28-page report mapping 22 distributed systems patterns to Squad. Thorough, well-sourced, exactly what I needed. She committed it to `.squad/research/distributed-systems-patterns-for-ai-teams.md`. Step 1: done.

Data picked it up, read Seven's research, and started implementing the reconciliation loop pattern in `ralph-watch.ps1`. He created a branch, wrote the code, pushed a PR. Step 2: in progress.

Then I reviewed Data's PR.

The implementation was **wrong**. Not slightly wrong — architecturally wrong. Data had treated the reconciliation loop as a polling enhancement when it should have been an idempotent state reconciler. The code would have introduced race conditions in the very system designed to prevent them. I rejected the PR.

And here's where it got interesting: **Seven's research report was still sitting there, committed and merged, referencing an implementation that no longer existed.** The report said "see the reconciliation loop implementation in `ralph-watch.ps1` lines 312–378" — but those lines had been reverted. Troi was waiting to write a blog post based on research that now pointed at a ghost.

Three agents. Three artifacts. One rejection cascading into **orphaned state** across the whole pipeline.

I'd just experienced — firsthand, painfully — the problem that Hector Garcia-Molina and Kenneth Salem described in their 1987 paper. The problem that Uber built Cadence to solve. The problem that Temporal.io has turned into a $1.7 billion business.

**I needed the Saga pattern.**

---

## What's a Saga, and Why Should You Care?

If you've built microservices, you've probably heard the term. If you haven't — here's the two-minute version.

In a monolithic application, you can wrap multiple operations in a database transaction. Reserve inventory, charge the credit card, schedule shipping — all inside `BEGIN TRANSACTION ... COMMIT`. If the credit card gets declined, everything rolls back. Clean. Atomic. Beautiful.

In a distributed system, you can't do that. Each service owns its own database. There's no global transaction coordinator that can just "undo" what happened across three services. You're stuck with **partial completion** — inventory reserved, payment failed, nothing shipped. Your customer sees a charge that never delivers.

The Saga pattern solves this by replacing the single atomic transaction with **a sequence of local transactions, each paired with a compensating action**. If step 3 fails, you run compensation for step 2, then compensation for step 1. The system doesn't roll back to a clean state — it **rolls forward through compensating operations** until consistency is restored.

Two flavors:
- **Orchestration Saga:** A central coordinator tells each service what to do and manages rollback. Think: Temporal, where a durable Workflow calls Activities and handles failures.
- **Choreography Saga:** Each service listens to events and decides what to do. No central brain. Think: Kafka event streams where services react independently.

Squad uses the orchestration model — Picard (or the human in the CLI) is the coordinator. Agents are the services. And right now, **we have zero compensation logic**.

---

## What Squad Has Today: Hope-Based Transaction Management

Let me be brutally honest about what happens when a multi-agent workflow fails in Squad today.

**The happy path works great.** Picard decomposes. Agents execute in parallel or in sequence. Results get committed. PRs get opened. Humans review. Everything merges. High fives all around.

**The unhappy path is chaos.**

Here's what our Saga support looks like today — pulled directly from the research Seven did for issue #678:

| Temporal Feature | Squad Equivalent | Gap |
|-----------------|------------------|-----|
| Durable Workflow state | None | Agent crashes lose all context |
| Compensating Activities | None | Failed steps leave orphaned artifacts |
| Saga state machine | None | No tracking of multi-step progress |
| Deterministic replay | Git history (partial) | Can't replay a task execution |
| Visual workflow UI | None | No visibility into multi-agent progress |

That's a lot of "None."

When Data's reconciliation PR got rejected, here's what **should** have happened:

1. ❌ Data's PR rejected → compensate: delete the branch, close the PR
2. 🔄 Seven's report referenced the rejected code → compensate: flag the report as stale, update references
3. ⏸️ Troi's blog post depended on both → compensate: pause, don't start writing based on stale inputs

Here's what **actually** happened:

1. ❌ Data's PR rejected → branch left orphaned, PR sits in "Changes Requested" limbo
2. 😐 Seven's report sits there, confidently referencing code that doesn't exist
3. 🤦 Troi starts writing a blog post based on research that points at reverted code

I caught it because I was paying attention. But what about the work Ralph does at 2 AM while I'm asleep? What about the cross-machine tasks where my DevBox finishes step 2 but my laptop doesn't know step 1 was already rolled back?

**Hope is not a compensation strategy.**

---

## Mapping Temporal to Squad

If you squint at Temporal's architecture, the mapping to Squad is almost eerie.

| Temporal Concept | Squad Equivalent |
|-----------------|-----------------|
| **Workflow** | A multi-step task decomposition by Picard |
| **Activity** | An individual agent's work (Seven writes research, Data writes code) |
| **Worker** | An agent instance (Data, Seven, Troi, B'Elanna) |
| **Task Queue** | `.squad/cross-machine/tasks/` or GitHub issues with `squad:copilot` label |
| **Workflow State** | Currently: nothing. Proposed: `.squad/sagas/` |
| **Signal** | Human review (approve/reject a PR, comment on an issue) |
| **Compensation** | Currently: nothing. Proposed: per-step `compensate` actions |

The key insight from Temporal is the separation of **Workflows** (durable, deterministic orchestration) from **Activities** (the actual side-effect-causing work). The Workflow engine manages state, retries, and compensation automatically. Activities can fail, time out, or need human approval — the Workflow handles all of it.

Squad already has this separation — we just don't formalize it. Picard **is** the Workflow engine. He decomposes, assigns, tracks dependencies. The agents **are** Activities — they do the actual work, produce artifacts, create PRs. What's missing is the **durable state** that tracks where we are in the transaction and the **compensation definitions** that tell us what to do when something fails.

---

## The Squad Saga Protocol

Here's what I'm building. A lightweight saga tracker — not Temporal-the-product, but Temporal-the-pattern, implemented in the way Squad does everything: files in a git repo.

```json
// .squad/sagas/saga-678-distributed-systems.json
{
  "sagaId": "678-distributed-systems",
  "issue": 678,
  "startedAt": "2026-03-16T10:00:00Z",
  "status": "compensating",
  "failurePolicy": "compensate-completed",
  "steps": [
    {
      "step": 1,
      "agent": "seven",
      "action": "write-research-report",
      "status": "completed",
      "output": ".squad/research/distributed-systems-deep-dive.md",
      "completedAt": "2026-03-16T10:22:00Z",
      "compensate": {
        "action": "flag-stale",
        "target": ".squad/research/distributed-systems-deep-dive.md",
        "description": "Add stale warning banner to report"
      }
    },
    {
      "step": 2,
      "agent": "data",
      "action": "implement-reconciliation-loop",
      "status": "failed",
      "branch": "squad/678-reconciliation",
      "failedAt": "2026-03-16T11:45:00Z",
      "failureReason": "PR rejected — architectural mismatch",
      "compensate": {
        "action": "cleanup-branch",
        "target": "squad/678-reconciliation",
        "description": "Delete branch and close PR"
      }
    },
    {
      "step": 3,
      "agent": "troi",
      "action": "write-blog-post",
      "status": "blocked",
      "dependsOn": [1, 2],
      "compensate": {
        "action": "no-op",
        "description": "Never started — nothing to compensate"
      }
    }
  ]
}
```

When step 2 fails and the `failurePolicy` is `"compensate-completed"`, Ralph walks **backward** through the completed steps:

1. Step 3 was `blocked` → nothing to do
2. Step 2 `failed` → execute compensate: delete branch `squad/678-reconciliation`, close the PR
3. Step 1 was `completed` → execute compensate: add a `⚠️ STALE` banner to Seven's research report

After compensation, the saga status moves to `"compensated"`. The entire transaction has been unwound. No orphaned branches. No stale research reports pointing at reverted code. No blog post written against phantom implementations.

---

## Three Flavors of Failure (and How Sagas Handle Each)

Not all failures are the same. Through running Squad for months, I've seen three distinct failure modes — and each needs a different compensation strategy.

### 1. The Hard Rejection

**What happens:** A human reviews a PR and explicitly rejects it. "This approach is wrong. Start over."

**Compensation:** Full rollback. Delete the branch, close the PR, flag downstream artifacts as stale. This is the classic saga compensation path.

**Real example:** Data's reconciliation loop implementation. Rejected for architectural reasons. Seven's research report flagged as "references reverted code." Troi's blog post never started — `blocked` status prevented wasted work.

### 2. The Silent Timeout

**What happens:** An agent starts work, creates a branch, maybe commits some code — then Ralph's heartbeat goes stale. The agent session died. The work is half-done.

**Compensation:** Partial cleanup. The branch exists with incomplete code. You can't just delete it — maybe there's salvageable work. Instead: mark the saga step as `"timed-out"`, move the branch to a `dead-letter/` prefix (`dead-letter/squad/678-reconciliation`), and reclaim the task for retry.

This is Squad's version of a **Dead Letter Queue** — failed work doesn't vanish silently, it moves to a known location where a human (or another agent) can inspect it later.

```powershell
# ralph-watch.ps1 — stale work reclamation (partial saga today)
# Lines 426-457 already handle this case, but without formal
# compensation:
if ($staleMinutes -gt $StaleThresholdMinutes) {
    # Reclaim the issue, but don't clean up artifacts
    gh issue edit $IssueNumber --remove-assignee $staleOwner
    gh issue comment $IssueNumber --body "⚠️ Reclaimed from $staleMachine (stale $staleMinutes min)"
}
```

Today Ralph reclaims but doesn't compensate. With the saga protocol, Ralph would also execute the step's `compensate` action — archiving the branch, notifying downstream agents, updating the saga state.

### 3. The Cascade Failure

**What happens:** An upstream dependency changes after your agent already consumed it. Seven updates her research report with new findings. Data already implemented based on the old version. The implementation is now inconsistent with the research.

**Compensation:** This is the hardest case. It's not a failure in the traditional sense — nobody's PR got rejected, no agent crashed. The ground shifted under a completed step.

This maps to what distributed systems call **semantic compensation** — the compensating action isn't "delete the file" but "re-execute with new inputs." In Temporal terms, this would be a **Signal** sent to a running Workflow: "input changed, re-evaluate."

**My current approach:** For now, we don't try to auto-compensate cascades. Instead, the saga tracker flags the inconsistency:

```json
{
  "step": 2,
  "status": "completed",
  "inputHash": "sha256:abc123",
  "warnings": [
    {
      "type": "input-drift",
      "message": "Input file modified after consumption",
      "inputFile": ".squad/research/distributed-systems-deep-dive.md",
      "consumedHash": "sha256:abc123",
      "currentHash": "sha256:def456",
      "detectedAt": "2026-03-16T14:00:00Z"
    }
  ]
}
```

The saga doesn't auto-rollback — it raises a flag. A human decides whether the drift matters or not. Sometimes Seven adds a typo fix to her report and it doesn't affect Data's implementation at all. Sometimes she restructures the entire findings section and Data's code is now based on outdated premises. The saga gives you **visibility** into the drift. The decision remains human.

---

## Why Not Just Use Temporal?

Fair question. If Temporal solves this problem, why am I building a bespoke saga tracker in JSON files?

**Three reasons:**

**1. No new infrastructure.** Squad's constraint — the thing that makes it actually usable — is that it runs on git, files, and shell scripts. No databases. No message brokers. No servers to maintain. Adding Temporal would be adding a production service dependency for what is, fundamentally, an AI agent coordination tool. That's a mismatch.

**2. Git IS the durable state store.** Temporal's killer feature is durable Workflow state that survives process crashes. You know what else survives process crashes? Files committed to git. When Ralph crashes after completing step 1 of a saga, the `saga-678.json` file is already committed. When Ralph restarts, he reads the saga file and picks up where he left off. Git gives us durability for free — we just need to be disciplined about committing state before acting.

**3. The compensation actions are simple.** In a microservices system, compensation might mean "reverse a bank transfer" or "cancel a shipping label" — complex domain-specific operations. In Squad, compensation is: delete a branch, close a PR, flag a file as stale, or move work to a dead-letter directory. These are git and GitHub CLI operations. We don't need a workflow engine for `git branch -d`.

That said — if Squad ever manages workflows with real-money consequences (deploying infrastructure, modifying production configs), I'd absolutely bring in Temporal. The JSON saga tracker is for **coordination correctness**, not for **business transaction safety**. Know the difference.

---

## What This Actually Looks Like in Practice

Let me walk you through a real workflow with the saga protocol in place. Same scenario as before: research → implement → blog.

**Happy path:**

```
📋 Saga 678 created
   Step 1: Seven → write-research          [pending]
   Step 2: Data → implement-pattern         [pending, depends: 1]
   Step 3: Troi → write-blog-post           [pending, depends: 1, 2]

✅ Step 1 completed (Seven wrote the report)
   Step 2: Data → implement-pattern         [in-progress]
   
✅ Step 2 completed (Data's PR merged)
   Step 3: Troi → write-blog-post           [in-progress]

✅ Step 3 completed (Troi wrote the post)
📋 Saga 678: COMPLETED ✅
```

**Failure path (Data's PR rejected):**

```
📋 Saga 678 created
   Step 1: Seven → write-research          [pending]
   Step 2: Data → implement-pattern         [pending, depends: 1]
   Step 3: Troi → write-blog-post           [pending, depends: 1, 2]

✅ Step 1 completed (Seven wrote the report)
   Step 2: Data → implement-pattern         [in-progress]

❌ Step 2 FAILED (PR rejected)
   → Trigger: compensate-completed policy

🔄 Compensating Step 2: delete branch squad/678-reconciliation, close PR
🔄 Compensating Step 1: add STALE banner to research report
   Step 3 was [blocked] — no compensation needed

📋 Saga 678: COMPENSATED 🔄
   Reason: "Step 2 failed — PR rejected, architectural mismatch"
```

The beauty is that you can read the saga file months later and understand **exactly** what happened. It's an audit trail — the same kind of audit trail that `decisions.md` provides for team decisions, but for multi-step workflows.

---

## The Borg Connection

In Star Trek, the Borg have something called **interlink nodes** — specialized drones that coordinate the actions of other drones in a local group. If an interlink node detects that a group of drones failed a task, it doesn't just abandon them. It routes compensating instructions: "Disengage from the target, return to the cube, regenerate, reassign."

The Borg Collective doesn't tolerate orphaned state. If an assimilation attempt fails on a species, the Collective doesn't leave half-assimilated drones wandering around the Alpha Quadrant. They compensate. They roll back. They try a different approach.

That's what the saga protocol gives Squad. Not just the ability to **do** multi-step work, but the ability to **undo** it gracefully when something goes wrong. The compensation logic is the interlink node — it makes sure that a failure in step 5 doesn't leave steps 1 through 4 in an inconsistent state.

---

## Honest Reflection

I'll tell you what I haven't built yet: **automatic compensation execution.** The saga JSON files exist. Ralph can read them. But today, compensation is still manual — I read the saga file, see what needs to be undone, and do it myself or tell an agent to do it.

The reason is trust. Automatic compensation means an AI agent decides to delete branches, close PRs, and modify files **without human approval**. For a personal repo, I'm comfortable with that. For a work repo with production code? Not yet.

Here's my current trust ladder:

1. ✅ **Saga tracking** — automatic. Every multi-step workflow gets a saga file.
2. ✅ **Failure detection** — automatic. Ralph updates saga status when steps fail or time out.
3. ✅ **Compensation planning** — automatic. The saga file lists exactly what compensation actions are needed.
4. ⏸️ **Compensation execution** — manual for now. Ralph surfaces the plan; a human approves it.
5. 🔮 **Full auto-compensation** — future. When trust is established through a track record of correct plans.

This is the same trajectory we followed with PR merging: start manual, automate when confidence is high. The saga protocol gives us the structure to **build that confidence** — because every compensation plan is logged, auditable, and reviewable before execution.

---

## What's Next

We've covered the three foundational distributed systems patterns so far:

- **Part 3:** Coordination — how agents on different machines avoid duplicate work (reconciliation loops, heartbeats, claim protocols)
- **Part 4:** Transactions — how multi-step agent workflows handle failure gracefully (the saga pattern, compensation actions)

Next up in [Part 5](/blog/2026/03/19/scaling-ai-part5-circuit-breakers), we tackle **resilience** — what happens when the infrastructure your agents depend on goes down. Circuit breakers, model fallback chains, and the art of failing fast instead of failing expensive.

Because here's the thing about distributed systems: solving coordination and transactions doesn't help if your agents keep hammering a dead API endpoint for twenty minutes before anyone notices. 🟩⬛

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [From Personal Repo to Work Team — Scaling Squad to Production](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — When Your AI Squad Becomes a Distributed System](/blog/2026/03/18/scaling-ai-part3-distributed)
> - **Part 4**: Temporal for AI Teams — Multi-Agent Transactions That Roll Back ← You are here
> - **Part 5**: Circuit Breakers for AI Agents — coming soon
> - **Part 6**: CRDTs and Conflict-Free State — coming soon
> - **Part 7**: The Agent Mesh — coming soon
> - **Part 8**: Event Sourcing Your Team's Decisions — coming soon
