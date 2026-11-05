---
layout: post
date: 2026-11-05
title: "LangGraph After the Crash: Checkpoints, Pending Writes and Recovery"
tags: [langgraph, langchain, ai-agents, python, durable-execution, internals]
---

*What LangGraph remembers about completed tool calls, what runs again, and who gets the agent moving.*

## What survives when the process dies?

In [the previous post](https://www.tamirdresher.com/blog/2026/10/10/what-langgraph-actually-builds), I talked about how LangGraph is actually structured and how it works. We looked at what happens when you build an agent, give it tools and let LangGraph run the loop between the model and those tools.

But there's a question we haven't completely answered: what happens if the agent is interrupted in the middle of its work? What if the process it runs in suddenly crashes? Can another process, perhaps on another machine, just continue from the same point?

And what about the tools it was running? Do we have any record that they were called? Can we tell whether they finished, or whether they changed something before the process died? When we resume the agent, which calls run again?

## What happens halfway through booking a vacation?

Suppose you're building an agent to book a vacation. It needs three tools: one to book the flight, one to reserve a hotel and one to book a rental car. The model asks for all three, the flight and hotel finish, and then the Python process crashes while the car tool is still running.

You want the replacement worker process to leave the flight and hotel alone and finish booking the car. With the normal agent factory, LangGraph can already do that, provided those completed tool results reached its persistent storage before the crash. The interesting questions are what it saved, how it matches those results to the work, and who actually starts the continuation.

Here's the factory-built agent I used. The complete [offline companion](https://github.com/tamirdresher/langgraph-internals-samples/blob/45d28f66ae1a91ad00011fd725537d7e41e67fc7/crash-recovery/vacation.py) supplies `OfflineVacationModel`, `make_tools`, and the two database paths. This is the setup excerpt, not a standalone script:

```python
from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver

config = {
    "configurable": {"thread_id": "vacation-001", "checkpoint_ns": ""},
}
with SqliteSaver.from_conn_string(str(data_dir / "checkpoints.sqlite")) as saver:
    agent = create_agent(
        model=OfflineVacationModel(),
        tools=make_tools(booking_db),
        checkpointer=saver,
    )
    result = agent.invoke({"messages": [("user", "Book my vacation.")]}, config)
```

There's no concurrency override here. `OfflineVacationModel` implements the chat-model interface, including `bind_tools`. Its first response is an `AIMessage` requesting flight, hotel and car; its next response, after all three tool results arrive, says the vacation is booked. No live model or API key is involved.

The three tools are ordinary booking functions:

```python
from langchain_core.tools import tool

def make_tools(booking_db):
    @tool
    def book_flight() -> str:
        """Reserve the flight for this simulated vacation."""
        return record_booking(booking_db, "flight")

    @tool
    def book_hotel() -> str:
        """Reserve a hotel room for this simulated vacation."""
        return record_booking(booking_db, "hotel")

    @tool
    def book_car() -> str:
        """Reserve a rental car for this simulated vacation."""
        return record_booking(booking_db, "car")

    return [book_flight, book_hotel, book_car]
```

The companion's `record_booking` commits a row to a separate `bookings.sqlite` and returns a confirmation such as `flight-confirmed`. It deliberately doesn't deduplicate requests. Calling it twice makes two booking records, so a repeated external effect can't hide behind a friendly mock.

With the [pinned dependencies](https://github.com/tamirdresher/langgraph-internals-samples/blob/45d28f66ae1a91ad00011fd725537d7e41e67fc7/crash-recovery/requirements.txt) installed, run these from the companion's directory:

```powershell
python .\vacation.py start --data-dir .\vacation-data
python .\vacation.py resume --data-dir .\vacation-data
```

`start` requires a new directory. `resume` reopens the existing databases and explicitly invokes `None` on the same thread. Resuming the completed example adds no bookings. The companion demonstrates the real factory and continuation call; the crash study uses instrumented fake booking services to hold execution at selected points.

---

## One tools node does not mean one tools task

Look at `agent.get_graph()` and you'll see one node registered as `tools`, alongside `model`, start and end. That static picture doesn't tell you how many executable tasks exist when the model asks for three bookings.

In the installed `langchain.agents.create_agent`, the model-to-tools routing produces a separate `Send("tools", [tool_call])` for each pending tool call. All three target the same registered node, but LangGraph creates three executable tasks with different task IDs. Each task receives one call.

That distinction changes the crash story. In the default-factory tests, I held car before its booking commit and waited until flight and hotel results were actually present in SQLite. Then I killed the Python process and opened the saved run in a different process.

Here's that selected window:

[![Three separately scheduled tool tasks share one tools node. Flight and hotel results are saved before the worker process is killed during car. A caller explicitly resumes the saved run in a replacement worker process.]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/factory-hard-kill.png)]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/factory-hard-kill.svg)

[Open the full-size diagram]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/factory-hard-kill.svg) | [Mermaid source]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/factory-hard-kill.mmd)

*The three boxes are runtime task instances, not three static graph nodes. Flight and hotel are green because their results were persisted before this kill, not merely because the booking functions returned. Both databases survive outside the worker. A replacement worker process still needs an explicit continuation invocation.*

For the parallel cases, I checked the saved writes while car was blocked. A booking row or a "function is about to return" marker wouldn't establish the same thing. These are controlled completed-sibling windows, not evidence that every result survives every possible crash timing.

> **Test setup:** LangChain 1.3.14, LangGraph 1.2.10, `langchain-core` 1.5.3, `langgraph-checkpoint` 4.3.0, `langgraph-checkpoint-sqlite` 3.1.2, Python 3.12.3 and Windows 11. Default `async` durability, with no durability override.
>
> Each reported case has three hard-process-kill trials. The factory default omits `max_concurrency`; the serialized variant sets it to `1`. These are process-crash tests with persistent SQLite, not disk-failure, power-loss or cross-machine tests.

---

## What does the replacement worker process actually see?

Before invoking recovery, I rebuilt the same agent with the persistent saver and original thread configuration, then inspected it. Keep the saver context open for these inspection snippets:

```python
snapshot = agent.get_state(config)
print(snapshot.metadata)
print(snapshot.next)
print([(t.name, t.result, t.error, t.interrupts) for t in snapshot.tasks])
```

In the default-factory booking run, `next` is `("tools",)`. But `tasks` contains **three different tasks named `tools`**. Flight and hotel have results; car has none. `next` lists unfinished work, so it isn't a count of all the task instances represented in the snapshot.

So far, we've followed the factory-built vacation agent. I also ran the same booking operations in a few other arrangements to see how the way we structure the work affects what gets saved. Before comparing their snapshots, here's what each name means:

- **Factory default:** The `create_agent` example above, with no concurrency override. Each requested booking becomes a separate `Send` task targeting the same registered `tools` node.
- **Factory with `max_concurrency=1`:** The same agent, but with its execution pool limited to one slot. It still creates separate tool tasks; this setting doesn't combine them into one task.
- **Manual aggregate ToolNode:** A hand-built model-and-tools loop that passes all three calls into one ToolNode execution. That single graph task returns a combined result after all three tools finish. This is a different graph from the factory's, not another factory setting.
- **Separate graph nodes:** A small graph with `book_flight_node -> book_hotel_node -> book_car_node`. Each booking has its own node and graph step. I left out the model loop here to look specifically at how those steps save their results.
- **Sequential Functional API tasks:** A `bookings` function decorated with `@entrypoint` calls three booking functions decorated with `@task`. It waits for flight's result before starting hotel, then waits for hotel before starting car. These are tasks inside a function, not three graph nodes.
- **Parallel Functional API tasks:** The same entrypoint/task approach, but it starts all three tasks before waiting for their results. In this test, car waits while flight and hotel finish.

The Functional API tests use `max_concurrency=8` so the entrypoint and its tasks have room to run. The sequential version still waits for each booking in order; having more execution slots doesn't change that code into the parallel version. I'll show the task code later.

There's one more distinction in the table: **which version is running** and **when I stop its worker process**. The first two rows are earlier stop points in the default factory agent, not extra configurations: before invoking it at all, and during its first model call. The other rows show the worker process killed during car, after flight and hotel finish but before the car booking commits.

The snapshot table includes the sequential Functional API case. Its parallel counterpart appears in the booking-results comparison later:

| Kill point / configuration | Has checkpoint? | Latest `source` / `step` | `next` | Saved booking results |
| --- | --- | --- | --- | --- |
| Before any invocation | No | None | `[]` | None; no tasks |
| Factory, inside first model call | Yes | `loop` / `0` | `["model"]` | None; one unfinished model task |
| Factory default, inside car | Yes | `loop` / `1` | `["tools"]` | Flight/hotel `messages` writes; three tools tasks, two with results |
| Factory, `max_concurrency=1`, inside car | Yes | `loop` / `1` | `["tools","tools","tools"]` | No booking result writes in this selected window; three unfinished tools tasks |
| Manual aggregate ToolNode, inside car | Yes | `loop` / `1` | `["tools"]` | None; one unfinished tools task |
| Separate graph nodes, inside car | Yes | `loop` / `2` | `["book_car_node"]` | Flight/hotel already in full checkpoint state |
| Sequential Functional API tasks, inside car | Yes | `input` / `-1` | `["bookings"]` | Flight/hotel `__return__` writes |

A run that never started is different from a run whose first model call never finished. In the first-model crash, the saved history includes the input checkpoint at `input/-1`, followed by `loop/0`. The replacement worker process sees the unfinished model task, with no recorded error or interrupt, and can continue using the saved input.

The unused thread has no checkpoint at all. Invoking `None` there raises `EmptyInputError: Received no input for __start__`. There's no saved request to continue. And the lack of an error on the crashed model task doesn't mean it completed; the process disappeared before it could report one.

---

## The full checkpoint isn't the whole saved run

Let's look underneath the public snapshot:

```python
saved = saver.get_tuple(config)
if saved is not None:
    print(saved.metadata)
    print(saved.checkpoint["channel_values"])
    print(saved.checkpoint["channel_versions"])
    print(saved.checkpoint["versions_seen"])
    print(saved.pending_writes)
```

The factory's latest full checkpoint is `source='loop', step=1`. Its message state contains the user's request and the model's three tool calls, before the tools' superstep finishes. It does **not** yet contain the flight and hotel results.

Those results are already stored separately, as pending writes against that checkpoint. Each completed `tools` task has a `messages` write whose payload is a list containing its `ToolMessage`: `flight-confirmed` with `tool_call_id='call-flight'`, or `hotel-confirmed` with `tool_call_id='call-hotel'`. There are also `branch:to:model` writes for those tasks. Car has neither a result message nor a saved completion.

These are not Functional API `__return__` rows. They're the factory tools tasks' ordinary graph-channel writes, attached to their distinct task IDs. "Pending" here doesn't mean they're still waiting in the dead process's memory. They were committed to SQLite before the kill; they're pending incorporation into the next full checkpoint.

That's how the full checkpoint can be older than two results already visible through `get_state()`. The public snapshot reconstructs a view using saved writes as well as checkpoint state. The whole tools superstep hasn't finished, so there isn't a later full checkpoint containing all three results yet.

The channel versions still matter. `channel_versions` and `versions_seen` help LangGraph reconstruct which channel-triggered work is eligible. The saved Send packets describe the per-call work, and pending writes say which reconstructed task IDs already produced output. Don't try to infer all of that from the step number alone.

In this version, the Pregel loop reapplies successful writes to matching reconstructed task IDs. The execution path submits tasks that still lack writes. Flight and hotel therefore don't run their bodies again; car does.

[![Checkpoint state and saved Send packets reconstruct runtime tasks. Persisted messages identify completed tasks; an explicit continuation executes work that still lacks saved results.]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/saved-write-recovery.png)]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/saved-write-recovery.svg)

[Open the full-size diagram]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/saved-write-recovery.svg) | [Mermaid source]({{ site.baseurl }}/assets/img/posts/langgraph-after-the-crash/saved-write-recovery.mmd)

*This is the factory path. The identity belongs to work reconstructed in that saved execution, not a global cache indexed by a Python function's name.*

If you're inspecting the SQLite database directly, this saver uses a physical table named `writes`. For the factory's saved booking messages:

```sql
SELECT checkpoint_id, task_id, channel, type
FROM writes
WHERE thread_id = ? AND checkpoint_ns = ? AND channel = 'messages'
ORDER BY checkpoint_id, task_id;
```

Bind the original thread and namespace. This can also show input or model message writes on earlier checkpoints, so check the checkpoint and task IDs, not just the channel name. Use the saver's serializer to decode payloads; a raw BLOB isn't the same thing as its Python `ToolMessage`.

---

## Which booking functions actually ran again?

I counted two things separately: **body attempts**, meaning entry into a booking function, and **effects**, meaning booking records committed in the separate fake service. Each vector below is `[flight,hotel,car]`, counting the original process and its explicit continuation together.

First, kill before car commits its booking:

| Configuration | Body attempts | Booking effects |
| --- | --- | --- |
| `create_agent`, default concurrency | `[1,1,2]` | `[1,1,1]` |
| `create_agent`, `max_concurrency=1` | `[2,2,2]` | `[2,2,1]` |
| Manual aggregate ToolNode, `max_concurrency=1` | `[2,2,2]` | `[2,2,1]` |
| Separate graph nodes, `max_concurrency=1` | `[1,1,2]` | `[1,1,1]` |
| Sequential Functional API tasks, `max_concurrency=8` | `[1,1,2]` | `[1,1,1]` |
| Parallel Functional API tasks, `max_concurrency=8` | `[1,1,2]` | `[1,1,1]` |

The serialized row is worth pausing over. The factory still created **three separate tasks**, and the flight and hotel functions returned. But their results hadn't reached persistent storage before the crash. In the follow-up trace, their saver submissions were queued on the same one-slot executor whose running car task occupied its only worker. **A task boundary alone doesn't mean its result has reached durable storage.**

With the default factory, flight and hotel each ran once. Car was entered twice, but only its second attempt made a booking. That's the behavior we're looking for in this before-effect window.

In the serialized factory, all three bodies ran again after the kill because none of their booking results had been saved in that selected window. This wasn't serialization combining them into an aggregate task; their Send task identities remained distinct.

There are two kinds of evidence behind that explanation. [Source inspection](https://github.com/tamirdresher/langgraph-internals-samples/blob/45d28f66ae1a91ad00011fd725537d7e41e67fc7/crash-recovery/SOURCE_MAP.md) shows that the synchronous loop passes its background submitter to the task runner and also uses it for saver writes. The [targeted probe](https://github.com/tamirdresher/langgraph-internals-samples/blob/45d28f66ae1a91ad00011fd725537d7e41e67fc7/crash-recovery/lab.py) then records what actually happened: flight and hotel task executions finished; their saver futures were submitted to that same executor, queued and not running; car was running; and neither matching saver call had started before the kill. The unfiltered SQLite writes and reconstructed task state both lacked those results.

The release control matters too. Instead of killing the serialized worker, I let car finish. The queued saver calls then started, completed, and their results appeared in SQLite. In the default-concurrency controls, flight and hotel saver calls completed while car was still held. That checks the queue explanation against actual draining, rather than treating an absent query result as proof by itself.

The [observational wrappers](https://github.com/tamirdresher/langgraph-internals-samples/blob/45d28f66ae1a91ad00011fd725537d7e41e67fc7/crash-recovery/executor_trace.py) leave the original calls, futures and write policy intact, but logging does add overhead. These are bounded mechanism checks of the pinned synchronous `invoke` path, default `async` durability, SQLite saver and `max_concurrency=1`—not a claim that every serialized agent loses completed results, or a measurement of arbitrary-crash failure rates.

The manual aggregate ToolNode reaches the same numbers for a different reason. That control feeds all three calls into one ordinary `tools` graph task. Its ToolNode gathers the tool outputs before returning its combined result. Killing it inside car leaves no independently completed graph task for flight or hotel. That's a graph you can build manually, but it isn't the default factory topology.

---

## What do separate nodes and native tasks change?

Separate graph nodes put flight and hotel in earlier supersteps. By the time the car node starts, their results are part of the full checkpoint. The saved state says `loop/2`, with only `book_car_node` next. This control doesn't include the agent's model loop.

The native Functional API gives us another shape. Here the entrypoint calls three individually recorded tasks, sequentially:

```python
from langgraph.func import entrypoint, task

@task
def book_flight_task():
    return record_booking(booking_db, "flight")

@task
def book_hotel_task():
    return record_booking(booking_db, "hotel")

@task
def book_car_task():
    return record_booking(booking_db, "car")

@entrypoint(checkpointer=saver)
def bookings(inputs):
    return [book_flight_task().result(),
            book_hotel_task().result(),
            book_car_task().result()]
```

*This excerpt uses the companion's booking helper and database, plus an open persistent saver. The control was invoked with `max_concurrency=8`, leaving capacity for the entrypoint and its tasks. The `.result()` calls still make the bookings sequential. It is not the factory implementation.*

Here the latest full checkpoint really is `input/-1`, because the `bookings` entrypoint hasn't returned. Flight and hotel nevertheless have separately saved `__return__` values. On continuation, the entrypoint runs again, and the module-level `_call` helper in `langgraph.pregel._runner` can resolve those reconstructed task futures from their saved `RETURN` values rather than executing the completed bodies. Car has no saved return, so its body runs.

That is different machinery from the factory's `messages` writes. Both avoid repeating work whose matching result was persisted, but the factory didn't need me to wrap every tool in `@task`.

For the parallel native-task control, I submitted all three futures, held car, and checked that flight and hotel `__return__` writes were in storage before the kill. The table covers only that completed-sibling, before-effect window. I did not measure a post-effect window for parallel Functional API tasks.

---

## What if the car was booked before the crash?

Move the stop point slightly. The car service commits its reservation, then the process dies before the tool returns a result LangGraph can save. The replacement worker process still has unfinished car work, but the service already has a booking.

Here's the matching after-effect window:

| Configuration | Body attempts | Booking effects |
| --- | --- | --- |
| `create_agent`, default concurrency | `[1,1,2]` | `[1,1,2]` |
| `create_agent`, `max_concurrency=1` | `[2,2,2]` | `[2,2,2]` |
| Manual aggregate ToolNode, `max_concurrency=1` | `[2,2,2]` | `[2,2,2]` |
| Separate graph nodes, `max_concurrency=1` | `[1,1,2]` | `[1,1,2]` |
| Sequential Functional API tasks, `max_concurrency=8` | `[1,1,2]` | `[1,1,2]` |

The default factory still leaves flight and hotel alone. But car now has two booking records: one from before the kill and one from continuation.

The gap is between two commits. The booking service records the reservation, and LangGraph records the task's result afterward. A checkpoint doesn't make those writes atomic. One final saved car result can follow two external bookings.

The test service logged the same logical idempotency key on both attempts and deliberately didn't enforce uniqueness. **Recording an idempotency key is not enforcing idempotency.** The system performing the booking has to recognize repeated requests and prevent a second reservation, or offer a reliable way to reconcile an uncertain outcome. LangGraph's task persistence doesn't give arbitrary external effects an exactly-once guarantee.

Those observations are about the fake service used here. A real provider's deduplication contract needs its own validation. And the factory's parallel after-effect result doesn't fill in the unmeasured parallel Functional API case.

---

## Reproduce the selected crash windows

The [reproduction package](https://github.com/tamirdresher/langgraph-internals-samples/blob/45d28f66ae1a91ad00011fd725537d7e41e67fc7/crash-recovery/README.md) contains the offline agent, all six graph configurations, the A–M crash matrix and the executor probe with its no-kill release control. It needs no model key or real booking service. From that directory, after following its CFS-based setup:

```powershell
python .\smoke.py --output .\outputs\smoke-01
python .\lab.py --output .\outputs\matrix-01 --repeats 3
python .\lab.py --output .\outputs\probe-01 --suite probe --repeats 3
```

Each command requires a fresh output directory. The harness keeps failures as well as successful runs, checks the executing worker PID before killing its owned process, and records actual booking rows separately from the graph's saved writes. The matrix reproduces selected windows with three repetitions per case; it isn't a random-crash reliability test. The package's source map links to the version-tagged upstream implementation rather than bundling library source.

---

## Who actually restarts the agent?

Opening the databases and rebuilding the agent didn't execute a tool. In every recovery trial, the replacement worker process first inspected the saved state and then sat idle for one second. No new booking attempts or effects appeared during that interval.

Work advanced when the caller explicitly invoked the saved run:

```python
result = agent.invoke(None, config)
```

`None` means continue the existing thread, not submit the vacation request again. Repeating the original user input isn't an interchangeable recovery operation.

The saved state isn't Python's instruction pointer either. LangGraph reconstructs tasks and reapplies saved outputs. In our default-factory run, that means preserving flight and hotel and executing the unfinished car task, not jumping into the dead Python stack at the next line.

A SQLite file is an excellent historian and a terrible on-call engineer.

Your application, a supervisor or a hosting service still has to start a replacement worker process and own that continuation call. The bounded idle observation shows what happened in this directly used library setup; it isn't a claim about every host that can run LangGraph.

And the "another machine?" question has a storage condition. That machine needs access to the persisted state through a suitable storage arrangement. Reusing the thread ID doesn't teleport a local SQLite file to a new host. I tested different processes on the same machine, not cross-machine SQLite recovery.

---

## What should you check in your own agent?

Start with what the factory actually builds, not just the static node count. Inspect the runtime task IDs, their inputs and their saved writes. Three calls to one registered node can be three separately recoverable tasks.

Then read the full checkpoint and pending writes together. An older full checkpoint can coexist with newer saved results. Check the actual channel and payload for your API: factory `messages` writes and Functional API `__return__` values aren't interchangeable explanations.

Finally, count external effects separately from task completions, and identify the component that owns recovery. A function returning isn't proof its result reached durable storage, a saved task result isn't proof the downstream effect happened exactly once, and a recoverable graph doesn't invoke itself.

For this vacation, the default factory can already reuse the persisted flight and hotel results. But after the worker process dies, the unfinished car booking still needs someone to get it running again. In these tests, that meant my caller code opening the saved run and explicitly resuming it. We also saw why I can't treat a tool function returning as proof that its result is safely recorded. Saving progress and taking responsibility for finishing the work are two different jobs.

In the next post, I'll show how we're running each of these LangGraph tool calls as a durable activity with Durable Task Scheduler (DTS). The scheduler tracks each invocation and its recorded completion, and can deliver unfinished work to an available replacement worker process without the original caller resuming the graph. That gives us durable execution around each tool without building our own delivery and recovery machinery. It builds on LangGraph's saved state and task results; the booking service still needs to handle duplicate requests safely.
