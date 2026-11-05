# LangGraph after the crash — offline reproduction

This sample uses the real `langchain.agents.create_agent` and a deterministic
chat-model implementation. Flight, hotel and car tools write **fake reservations**
to a local SQLite booking service, separate from the graph checkpoint database.
No keys, live model, real bookings, external tracing or runtime network calls are
required. Tracing environment variables are disabled in each test process.

## Setup and short demo

Historical environment: Python **3.12.3**, Windows 11; LangChain **1.3.14**,
LangGraph **1.2.10**, core **1.5.3**, checkpoint **4.3.0**, SQLite saver **3.1.2**.
The five direct runtime packages are pinned; `constraints.txt` also pins the
active transitive dependency closure from that environment. New runs record their actual versions/interpreter,
and are reproductions, not the original article's historical artifacts.

Use Microsoft CFS, not another package registry:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip --isolated install --index-url https://packagefeedproxy.microsoft.io/pypi/simple/ -r .\requirements.txt
.\.venv\Scripts\python.exe .\vacation.py start --data-dir .\vacation-data
.\.venv\Scripts\python.exe .\vacation.py resume --data-dir .\vacation-data
```

`start` refuses an existing data directory. `resume` verifies the sample marker
and invokes **literal `None`**, not a second user request. A completed-thread
resume adds no booking rows. The model's initial message asks for three tool
calls; after all three results arrive it says `Vacation booked.`.

## Automated smoke and full matrix

All commands below require a **new output directory**. Existing outputs are
never overwritten. Nothing runs at import. Test outputs contain local process
identities and filesystem paths; they are ignored working data, not public
source files to commit.

```powershell
.\.venv\Scripts\python.exe .\smoke.py --output .\outputs\smoke-01
.\.venv\Scripts\python.exe .\lab.py --output .\outputs\matrix-01 --repeats 3
.\.venv\Scripts\python.exe .\lab.py --output .\outputs\probe-01 --suite probe --repeats 3
```

The small smoke starts/resumes the companion, tests unused-thread recovery, and
runs one serialized kill plus one serialized release/drain probe. It also checks
wrapper argument/return forwarding, exception identity and keyword saver calls.
For a smaller reproduction use e.g. `--cases CE --repeat 2` (matrix) or
`--suite probe --cases ER --repeats 1`. Repeats are independent runs, not automatic
retries that discard failures. All failed diagnostics remain; any failed case
makes the command exit nonzero. A's expected `EmptyInputError` is a passing
**negative control**, not a successful recovery.

Each cell below is the historical expected vector **[flight, hotel, car]**,
counting original and replacement bodies/effects together. The harness asserts
these expectations, but saves every observation, including mismatches.

| Case | Shape and kill point | `max_concurrency` | Body attempts | Booking rows |
|---|---|---|---|---|
| A | Factory, before any invoke | omitted | [0,0,0] | [0,0,0] |
| B | Factory, first model call | omitted | [1,1,1] | [1,1,1] |
| C | Factory, car before effect | omitted | [1,1,2] | [1,1,1] |
| D | Factory, car after effect/before return | omitted | [1,1,2] | [1,1,2] |
| E | Factory, car before effect | 1 | [2,2,2] | [2,2,1] |
| F | Factory, car after effect/before return | 1 | [2,2,2] | [2,2,2] |
| G | Manual aggregate ToolNode, before effect | 1 | [2,2,2] | [2,2,1] |
| H | Manual aggregate ToolNode, after effect/before return | 1 | [2,2,2] | [2,2,2] |
| I | Separate graph nodes, before effect | 1 | [1,1,2] | [1,1,1] |
| J | Separate graph nodes, after effect/before return | 1 | [1,1,2] | [1,1,2] |
| K | Sequential native tasks, before effect | 8 | [1,1,2] | [1,1,1] |
| L | Sequential native tasks, after effect/before return | 8 | [1,1,2] | [1,1,2] |
| M | Parallel native tasks, before effect **only** | 8 | [1,1,2] | [1,1,1] |

These are six configurations, not thirteen factory modes. A/B are earlier
factory stop points. A manual aggregate ToolNode takes all calls in **one graph
task**; the actual factory creates three `Send` task instances of one registered
`tools` node. Serializing the factory does not merge those identities.
Separate nodes put bookings in earlier supersteps. Sequential native tasks
still wait in sequence despite eight available execution slots; parallel
native tasks submit three futures first. There is no parallel-native post-effect
result in this study.

## Observation policies and ownership

The original process is given exactly one initial input. The controller checks
that launched PID, executing PID and gate PID agree, kills only its own `Popen`
handle, waits for termination, and inspects a **SQLite backup API** snapshot.
It then launches a distinct replacement process with the same graph/thread,
inspects the saved state, observes one second of idle time, and explicitly
authorizes a `None` invocation. `finally` cleanup reaps every owned worker.
No process-name killing, background servers or automatic graph respawn.
Transient Windows JSON sharing/permission errors are retried for at most a
nominal second and each retry is logged in the output directory. Permanent
errors still fail the case; malformed JSON and other I/O errors are not hidden.

Windows venv executables can act as launcher processes. Workers therefore use
the current interpreter's `sys._base_executable` directly with `-S -B`, supplying
the actual venv package directory via `PYTHONPATH`. The launch and PID receipts
verify that the controller kills the executing interpreter rather than its
launcher. This also works without a venv, using the active package directory.

For default factory and native parallel/sequential cases, car is held while
flight/hotel results are verified in storage; for separate nodes they must be
in full checkpoint state. This deliberately selects **completed-sibling
storage windows**, not arbitrary crash timing. For serialized factory cases,
the controller observes actual storage for a **nominal one-second polling
budget** instead of requiring results that cannot drain while car holds the
only slot. Actual sample counts/elapsed times are recorded, not assumed equal
to the budget. The aggregate case has no independently completed graph task
for either sibling. Car waits for sibling return-ready events before its gate;
those markers alone are never used as proof of persisted results.

Full unfiltered typed physical writes, saver tuples, public task snapshots and
checkpoint metadata are retained before/after kill and after recovery.
The fake booking store records independent effects, attempts and a logical
idempotency key, but deliberately does **not** enforce uniqueness. A stored
result cannot make an external service transaction atomic with checkpointing.
Disk/power failure, arbitrary timing, real providers, cross-machine storage,
async Python invocation, different savers and durability modes are not tested.

## Shared-executor instrumentation

The 15-case probe runs C/D/E/F three times each, plus R three times.
R uses the same serialized pre-effect gate but **releases car without killing
the process**, verifying that queued saver work starts/drains and results
appear. Its expected attempt/effect vectors are both [1,1,1].

`executor_trace.py` wraps the actual synchronous `BackgroundExecutor.submit`
and submitted callable start/finish, plus `SqliteSaver.put_writes` entry/exit.
It also wraps `StructuredTool._run` to observe each actual booking function's
returned value and original task ID, rather than relying on a return-ready marker.
Original methods receive unchanged arguments; original futures, return values
and exceptions are preserved. No executor replacement, forced flush, synchronous
write policy, fake completion or source-file modification is used.
The car gate samples real future `running()/done()/cancelled()` state.

Traces correlate PID/thread, monotonic ordering, executor and pool identities,
pool capacity, function identities, checkpoint/task IDs and tool-call IDs.
Sibling `run_with_retry` finish events establish that their executions returned,
beyond the service's return-ready marker. The serialized assertion requires
both sibling saver futures queued/not running/not done on car's one-slot pool,
car running, and no corresponding saver entry before the held-window boundary.
Default controls require those same result saves to finish before kill.
Release controls require queued writes to finish afterward.

Logging takes locks, opens/appends a JSONL file and flushes Python's buffer;
it changes timing and is not zero-overhead or a kernel scheduler trace.
`logging_cost` samples measure cumulative logging-call time (including lock
wait), **not total instrumentation overhead**. Traces are not fsynced on every
line; the kill preserves recorded prefixes, and the controller checks required
events rather than treating missing tail events as proof by themselves.
The uninstrumented matrix and instrumented probe are separate measurements.
This tests a bounded explanation in the pinned **synchronous invoke / default
async durability / SQLite / max_concurrency=1** arrangement, not a universal
claim about all LangGraph execution.

See [SOURCE_MAP.md](SOURCE_MAP.md) for the corresponding public upstream code.
No upstream library sources or private experiment artifacts are vendored here.
