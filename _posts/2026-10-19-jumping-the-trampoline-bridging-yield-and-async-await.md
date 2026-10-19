---
layout: post
date: 2026-10-19
title: "Jumping the Trampoline: How a 2009 C# Trick Helped Me Bridge yield and async/await in Python"
tags: [python, async-await, generators, coroutines, trampoline, reactive-extensions, csharp, architecture]
---

Over the last couple of weeks, I was working on connecting a few well-known Python libraries (including **LangGraph** and **Pydantic AI**) to a workflow execution engine.

I won't bore you here with the whole backstory of *why* I was wiring them together — the fun part was the mechanical clash I hit the moment the two worlds met.

On one side, modern Python agent and graph libraries are `async`/`await` all the way down. You call `await agent.run(...)`, and internally the library opens `AsyncExitStack` scopes, checks `asyncio.get_running_loop()`, and fans out parallel tool calls using `asyncio.gather()` or `anyio.create_task_group()`.

On the other side, the workflow engine I was plugging them into drives its orchestrations as **synchronous Python generators** (`def workflow(ctx):`). Instead of `await`, it expects you to `yield` task objects back to a deterministic runner:

```python
def workflow(ctx, payload):
    step_1 = yield ctx.call_activity("fetch_data", input=payload)
    step_2 = yield ctx.call_activity("process_data", input=step_1)
    return step_2
```

Two battle-tested models. Both completely reasonable on their own terms. And out of the box, they refuse to talk to each other: you can't `yield` to an outer generator from deep inside a third-party `async def` call stack, and you can't `await` an `async def` library inside a plain generator without something driving the coroutine.

We needed a bridge so they could play nice together.

* * *

## A 15-Year-Old Memory from Reactive Extensions and Bart De Smet

As I was staring at the problem — how to let a deep chain of `async`/`await` calls pause, hand a task out to a synchronous `yield` loop, and resume on the exact same thread without blowing the stack or spinning up background threads — a very old memory clicked in my head.

Years ago, when I was deep into **Reactive Extensions (Rx.NET)** (and writing *Rx.NET in Action*), I used to devour everything the Rx team at Microsoft and the programming-languages crowd on [Lambda the Ultimate](http://lambda-the-ultimate.org/) wrote about continuations, iterators, and schedulers.

In particular, I remembered a classic 2009 blog post by **Bart De Smet** (one of the brilliant minds behind Rx and LINQ at Microsoft): [**"Jumping the Trampoline in C# – Stack-Friendly Recursion"**](https://openmindtree.blogspot.com/2012/03/jumping-trampoline-in-c-stack-friendly.html).

In that post, Bart used the mental model of an **acrobat on a trampoline**:

> *"One main characteristic of trampolines is that they bounce back. Jump on them and you'll be catapulted in the air... While in the air you can make funny transformations, but in the end you'll end up on the trampoline again. The whole cycle repeats till you run out of energy and just stay at rest on the trampoline."*

Instead of Function A calling Function B directly (growing the call stack deeper and deeper, or blocking a thread while waiting for the next step), each step does a small burst of work "in the air" and **returns a representation of what to do next** back down to a flat `while` loop — the **trampoline**.

Rx itself used that exact concept everywhere:
- `CurrentThreadScheduler` used a **trampoline queue** on a single thread so scheduled continuations wouldn't recursively stack-overflow or race across threads.
- Before C# 5 even had `async`/`await`, Rx showed how C# iterators (`IEnumerable` with `yield return`) and continuation-passing `async` methods were really two sides of the same state-machine coin.

Sitting there in 2026 staring at Python's `yield` and `async`/`await`, I realized: **this is the exact same trampoline problem.**

* * *

## Attempt 1: The 10-Line Coroutine Driver (and Why It Breaks)

If you look under the hood of Python (or C#, for that matter), `def ... yield` generators and `async def ... await` coroutines are practically twins.

In CPython, a coroutine object created by an `async def` function has the exact same `.send(value)` and `.throw(exception)` methods as a generator. When an `async def` function hits an `await`, it suspends its frame and yields control up to whatever is driving it.

So your first instinct is to write a 10-line manual driver that steps the coroutine with `.send()` and re-yields whatever comes out:

```python
def naive_bridge(coro):
    value = None
    exc = None
    while True:
        try:
            # Bounce up into the async coroutine
            yielded_task = coro.send(value) if exc is None else coro.throw(exc)
        except StopIteration as done:
            return done.value

        # Bounce back down: hand the task to the outer yield runner
        try:
            value = yield yielded_task
            exc = None
        except BaseException as err:
            value = None
            exc = err
```

For a toy `async def` function that only awaits custom `__await__` objects, those 10 lines work like magic!

And then you point it at a real library like **Pydantic AI** or **LangGraph**, and it blows up in five seconds:

```text
RuntimeError: no running event loop
```

Why? Because real-world `async` libraries don't just `await` your leaf functions in a vacuum:

1. **They ask `asyncio` who is driving.** Libraries (and `anyio` underneath them) call `asyncio.get_running_loop()` and `asyncio.current_task()` to manage `AsyncExitStack` cleanup, cancellation scopes, and `contextvars`. When you drive a raw coroutine with `coro.send(None)`, there is no running `asyncio` event loop.
2. **They fan out parallel work.** When an agent decides to call three tools in parallel, the library doesn't `await` them one by one — it spawns child tasks using `asyncio.gather()` or `anyio.create_task_group()`. A raw `coro.send()` loop has no task scheduler and no microtask queue to step three child coroutines concurrently.

* * *

## Why "Just Run `asyncio.run()` on Another Thread" Is a Trap

At this point, the second temptation shows up: *"Fine! Let's spin up a background thread running `asyncio.run()`, and pass tasks back and forth to the `yield` generator over a thread-safe `queue.Queue`!"*

In fact, some synchronous-to-async bridges do exactly that when the caller is a normal blocking function.

But when the outer side is a **`yield` generator** (especially in a replay-based workflow engine), a two-thread queue bridge is a trap for two reasons:

1. **Abandoned generators leak blocked threads.** Generator runners often step a generator up to a `yield`, see that the yielded task isn't ready yet, and simply drop the generator frame until the external work finishes later. If you have a background OS thread parked on `queue.get()` inside `asyncio.run()`, that thread hangs forever.
2. **OS thread scheduling ruins parallel determinism.** Suppose your `async` code spawns three parallel child tasks (`Task A`, `Task B`, `Task C`) via `asyncio.gather()`. If the event loop is racing on a separate OS thread, the generator thread might wake up and `yield` as soon as `Task A` pushes to the queue — before `Task B` and `Task C` have even reached their `await` lines! Instead of one parallel batch of three tasks, you get non-deterministic scheduling that changes from run to run.

We don't want two threads racing over a queue. We want **Bart De Smet's trampoline**: one thread, one flat loop, where the `async` tasks jump up, run every pure-memory microtask until they all hit their suspension boundary, and land right back on the trampoline together.

* * *

## The Real Solution: A Single-Threaded `TrampolineLoop`

Here is the trick that made both our **Pydantic AI** and **LangGraph** bridges click.

Instead of fighting `asyncio`, Python lets you subclass `asyncio.BaseEventLoop` (or `AbstractEventLoop`) and build a **deterministic, zero-I/O, single-threaded trampoline loop** in about 120 lines of code.

If you come from C# and .NET, think of this as writing a custom single-threaded `SynchronizationContext` + `TaskScheduler`: instead of dispatching `await` continuations to the OS thread pool or an `epoll`/`IOCP` selector, `call_soon()` simply drops callbacks into an in-memory `collections.deque`.

<pre class="mermaid">
sequenceDiagram
    participant Gen as Outer yield Generator
    participant Tramp as TrampolineLoop (drain_ready)
    participant Tasks as async/await Tasks (gather / anyio)

    Gen->>Tramp: 1. drain_ready() (installs loop on current thread)
    Tramp->>Tasks: 2. Run _ready microtasks in a flat while loop
    Tasks->>Tramp: 3. Child tasks await YieldFuture(task_1), YieldFuture(task_2)
    Note over Tramp,Tasks: _ready queue is now empty!<br/>All active tasks are parked on YieldFutures
    Tramp-->>Gen: 4. Return pending [YieldFuture_1, YieldFuture_2]
    Gen-->>Gen: 5. yield when_all([task_1, task_2]) to outer runner
    Gen->>Tramp: 6. Feed results into YieldFutures &amp; repeat!
</pre>

Let's look at the three small pieces that make up the whole bridge.

### Piece 1: `YieldFuture` — The Suspension Hook

First, we need an awaitable object that connects the two worlds. `YieldFuture` is a real `asyncio.Future` attached to our `TrampolineLoop`, carrying the `task` object that the outer `yield` generator understands:

```python
import asyncio
from collections import deque
from typing import Any, Callable, Coroutine, Generator, Generic, TypeVar

T = TypeVar("T")

class YieldFuture(asyncio.Future[T], Generic[T]):
    """An asyncio.Future paired with a task to be yielded by the outer generator."""

    def __init__(self, loop: "TrampolineLoop", external_task: Any) -> None:
        super().__init__(loop=loop)
        self.external_task = external_task
```

Because `YieldFuture` is a genuine `asyncio.Future`, whenever an `async def` function executes `result = await loop.create_yield_future(external_task)`, standard `asyncio` suspends the current `asyncio.Task` and registers its continuation callback (`Task.__step`) on the future.

### Piece 2: `TrampolineLoop` and `drain_ready()` — The Bounce

Next is `TrampolineLoop`. It doesn't open sockets, doesn't touch selectors, and never spawns threads. Its `call_soon` just appends a handle to `self._ready`:

```python
class TrampolineLoop(asyncio.BaseEventLoop):
    """Single-threaded trampoline event loop with zero OS I/O."""

    def __init__(self) -> None:
        self._ready: deque[asyncio.Handle] = deque()
        self._pending_yields: list[YieldFuture[Any]] = []
        self._running = False
        self._closed = False

    def is_running(self) -> bool:
        return self._running

    def is_closed(self) -> bool:
        return self._closed

    def call_soon(self, callback: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.Handle:
        handle = asyncio.Handle(callback, args, self, context)
        self._ready.append(handle)
        return handle

    def call_soon_threadsafe(self, callback: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.Handle:
        return self.call_soon(callback, *args, context=context)

    def create_future(self) -> asyncio.Future[Any]:
        return asyncio.Future(loop=self)

    def create_task(self, coro: Coroutine[Any, Any, T], *, name: str | None = None, context: Any = None) -> asyncio.Task[T]:
        return asyncio.Task(coro, loop=self, name=name, context=context)

    def create_yield_future(self, external_task: Any) -> YieldFuture[Any]:
        fut: YieldFuture[Any] = YieldFuture(self, external_task)
        self._pending_yields.append(fut)
        return fut
```

Now look at `drain_ready()` — this is the heart of the trampoline:

```python
    def drain_ready(self) -> list[YieldFuture[Any]]:
        """Bounce through all ready microtasks until every task is parked on a YieldFuture."""
        prev_loop = asyncio._get_running_loop()
        asyncio._set_running_loop(self)
        self._running = True
        try:
            # The Trampoline: run ready callbacks in a flat loop
            while self._ready:
                handle = self._ready.popleft()
                if not handle._cancelled:
                    handle._run()

            active = [f for f in self._pending_yields if not f.done() and not f.cancelled()]
            self._pending_yields = active
            return list(active)
        finally:
            self._running = False
            asyncio._set_running_loop(prev_loop)
```

Look closely at what happens inside that `while self._ready:` loop when your `async` library uses `asyncio.gather()` or `anyio.create_task_group()` to run three tasks in parallel:

1. Because `asyncio._set_running_loop(self)` is set, `asyncio.get_running_loop()`, `asyncio.current_task()`, `AsyncExitStack`, and `anyio` task groups all see a real, running `asyncio` loop!
2. When `gather()` or `TaskGroup` spawns three child `asyncio.Task`s, each child task queues its initial `Task.__step` callback onto `self._ready`.
3. Before `drain_ready()` returns, the `while self._ready:` loop pops and runs **all three** child tasks up to their first `await create_yield_future(...)` suspension point!
4. Only when every runnable microtask in memory has settled does `self._ready` become empty. `drain_ready()` then returns all three pending `YieldFuture`s in deterministic order.

### Piece 3: `drive_coroutine()` — Bridging `await` to `yield`

Finally, `drive_coroutine()` is the generator function that our `yield`-based workflow calls with `yield from`:

```python
    def drive_coroutine(self, coro: Coroutine[Any, Any, T]) -> Generator[Any, Any, T]:
        """Drive an async coroutine by yielding tasks out to a synchronous generator."""
        prev_loop = asyncio._get_running_loop()
        asyncio._set_running_loop(self)
        try:
            root_task = self.create_task(coro)
        finally:
            asyncio._set_running_loop(prev_loop)

        while not root_task.done():
            pending = self.drain_ready()
            if root_task.done():
                break

            if len(pending) == 1:
                # Single awaited operation -> yield a single task
                yf = pending[0]
                try:
                    result = yield yf.external_task
                except BaseException as exc:
                    yf.set_exception(exc)
                else:
                    yf.set_result(result)
            else:
                # Parallel asyncio.gather / TaskGroup -> yield a batch!
                batch_tasks = [yf.external_task for yf in pending]
                try:
                    results = yield batch_tasks  # e.g., yield task.when_all(batch_tasks)
                except BaseException as exc:
                    for yf in pending:
                        if not yf.done():
                            yf.set_exception(exc)
                else:
                    for yf, res in zip(pending, results):
                        if not yf.done():
                            yf.set_result(res)

        return root_task.result()
```

When `yf.set_result(result)` runs, `asyncio.Future` schedules `Task.__step` back onto `self._ready`. On the very next iteration of `while not root_task.done():`, `drain_ready()` bounces the coroutine forward to the next `await` — or all the way to its final return value.

And on the caller side? You just use standard Python `yield from`:

```python
def my_generator_workflow(ctx, prompt: str):
    loop = TrampolineLoop()
    # Run an async/await library seamlessly inside a yield generator!
    answer = yield from loop.drive_coroutine(run_my_async_agent(prompt))
    return answer
```

* * *

## The Flip Side: Keeping Async Libraries Happy Across Sync Callbacks

Interestingly, when we wired up **LangGraph** and **Pydantic AI**, we also hit the mirror-image bridge problem on the worker side: calling an `async def` library from inside a synchronous callback function (`def run_step(...) -> dict:`).

The naive answer there is `asyncio.run(coro)`.

And just like the naive `coro.send()` bridge, `asyncio.run()` has a subtle trap with stateful libraries: **`asyncio.run()` creates a brand-new event loop and closes it as soon as the call returns.**

If your library caches an `httpx.AsyncClient` connection pool, an `aiosqlite` database connection (`AsyncSqliteSaver`), or an `asyncio.Lock` across steps, those objects bind themselves to the event loop that was active when they were created. On step 2, when `asyncio.run()` spins up a *second* event loop and closes the first one, you immediately hit:

```text
RuntimeError: Event loop is closed
# or:
RuntimeError: Task got Future attached to a different loop
```

The fix on that side is another simple bridge pattern: instead of creating and destroying an event loop on every synchronous call with `asyncio.run()`, spin up **one persistent daemon event-loop thread** (`loop.run_forever()`) per worker process and bounce coroutines onto it via `asyncio.run_coroutine_threadsafe(coro, bg_loop).result()`. Your synchronous callback blocks cleanly until the coroutine finishes, while every `httpx` pool, MCP session, and `aiosqlite` connection stays warm on the exact same event loop across steps.

* * *

## Old Tricks Are the Best Tricks

There is something deeply satisfying about hitting a modern integration problem in 2026 — trying to get `async`/`await` agent frameworks and `yield`-based workflow engines to cooperate — and realizing the cleanest solution is a pattern you first read about in a 2009 C# blog post.

Libraries and syntax evolve. C# iterators became `async`/`await`; Rx schedulers inspired a generation of reactive streams; Python evolved from `yield` generators (`@asyncio.coroutine` in Python 3.4) to native `async def` coroutines and `anyio` task groups.

But underneath the syntax, a coroutine is still just a state machine waiting for someone to step it — and when two state machines speak different dialects, a good old-fashioned **trampoline** is still the best way to help them bounce together.
