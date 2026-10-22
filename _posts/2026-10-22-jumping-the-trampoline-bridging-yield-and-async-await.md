---
layout: post
date: 2026-10-21
title: "Jumping the Trampoline: How a 2009 C# Trick Helped Me Bridge yield and async/await in Python"
tags: [python, async-await, generators, coroutines, trampoline, reactive-extensions, csharp, wpf, architecture]
---

It's so cool how the brain works. You can be staring at a problem in 2026, and suddenly you remember something you read way, way back that kind of saves your ass.

For me, that moment happened last week when I wanted to combine together two Python libraries that speak a different language, or more accurately, two different async idioms.

One of the libraries is `async`/`await` all the way down. You call an `async def` entry point, and internally it opens `AsyncExitStack` scopes, checks `asyncio.get_running_loop()`, and fans out concurrent work using `asyncio.gather()` or `anyio.create_task_group()`.

The other library drives its execution using **synchronous Python generators** (`def my_flow(ctx):`). Instead of `await`, it expects you to `yield` task objects back to its runner loop:

```python
def my_flow(ctx, payload):
    step_1 = yield ctx.schedule("fetch_data", input=payload)
    step_2 = yield ctx.schedule("process_data", input=step_1)
    return step_2
```

Both models make complete sense on their own terms, and out of the box they refuse to talk to each other. You can't `yield` to an outer generator from ten frames deep inside a third-party `async def` call stack, and you can't `await` an `async def` function inside a plain generator without something stepping the coroutine.

I needed a bridge so they could play nice together.

* * *

## Remembering Bart De Smet, Rx, and the Trampoline

As I was sitting there trying to figure out how to let a deep chain of `async`/`await` calls pause, hand a yielded object out to a synchronous generator loop, and resume on the exact same thread without blowing the stack or spinning up background threads, a 17-year-old memory popped into my head.

Years ago, when I was deep into **Reactive Extensions (Rx.NET)** and writing *Rx.NET in Action*, I was obsessed with everything the fathers of Rx at Microsoft (Erik Meijer, Bart De Smet, Wes Dyer, and Jeffrey Van Gogh) were putting out. I read all of their MSDN blog posts (like Wes Dyer's posts on continuations, monads, and iterators, and Bart's deep dives on the B# blog), and I used to watch and listen to every single piece they recorded on **Channel 9 (RIP)**, where they would stand in front of a whiteboard and derive async, iterators, and schedulers from first principles.

In particular, I remembered a 2009 post by **Bart De Smet**: [**"Jumping the Trampoline in C#: Stack-Friendly Recursion"**](https://openmindtree.blogspot.com/2012/03/jumping-trampoline-in-c-stack-friendly.html) (preserved on a 2012 mirror after his old blog moved).

In that post, Bart explained trampolines using the image of an acrobat jumping on a trampoline:

> *"One main characteristic of trampolines is that they bounce back. Jump on them and you'll be catapulted in the air... While in the air you can make funny transformations, but in the end you'll end up on the trampoline again. The whole cycle repeats till you run out of energy and just stay at rest on the trampoline."*

### What Is a Trampoline, Really?

If you haven't run into the term before, the idea is much simpler than functional-programming articles sometimes make it sound.

In normal function calls or recursion, when Function A calls Function B, and B calls C, and C calls D, the runtime stacks them on top of each other:

```text
Call Stack:  [Main] -> [Step 1] -> [Step 2] -> [Step 3] -> [Step 4] ...
```

Each function stays on the call stack waiting for the next one to finish. Go too deep and you blow the stack (`RecursionError` or `StackOverflowException`). Worse, the caller at the bottom (`Main`) has no control over the steps in the middle. It cannot pause the chain at Step 3, inspect what Step 3 wants to do, hand that work to an outside runner, and resume Step 4 later.

A trampoline flips that around.

Instead of `step_1()` calling `step_2()` directly, `step_1()` does its small piece of work and **returns** a callable (a thunk) representing the next step. At the bottom sits a flat `while` loop that calls them one by one:

```python
def trampoline(step):
    while callable(step):
        step = step()  # Jump up for one hop, land back with the next step
    return step
```

The `while` loop is the trampoline mat. Calling `step()` sends the code up into the air for one short hop. Instead of climbing higher and higher on the call stack, the function lands right back on the mat by returning what it wants to run next.

And because every step lands back on the mat, the loop at the bottom is in control of what happens between hops. If a step returns another local callback, the loop can bounce it right back up. If a step lands holding an external task that the outer `yield` generator needs to run, the loop can pause, `yield` that task out to the generator, wait for the result to come back, and then resume bouncing.

Once you see that pattern, you notice it everywhere. Rx's `CurrentThreadScheduler` is a single-threaded trampoline queue. And before C# 5 had `async`/`await`, people in the .NET community used C# `yield return` iterators (`IEnumerable<Task>`) driven by a trampoline loop to write sequential-looking async code without nested callbacks.

Sitting there in 2026 staring at Python's `yield` and `async`/`await`, I realized I had the exact same problem, just in reverse. Back in 2009, we used `yield` to build `async`/`await`. Now I had `async`/`await` code that I needed to drive through `yield`.

* * *

## Wait, Doesn't This Already Exist?

Before looking at the code, it is worth answering two obvious questions.

**First, why not just use `asyncio.run()` or `nest_asyncio`?**

Because `nest_asyncio` solves the opposite problem. It patches a running `asyncio` loop so a synchronous function can call `loop.run_until_complete()` and block the call stack until an async future finishes.

Here, we cannot block the call stack waiting for the task to finish. The outer library is a generator runner (`result = yield task`). The only way to hand work to it is to literally `yield` the task object out of the generator function and return control to the runner. `nest_asyncio` cannot turn an `await` ten frames deep into a `yield` at the top of a generator.

**Second, didn't Temporal write a blog post about a custom `asyncio` event loop?**

They did. Chad Retz's post on [Temporal's Durable, Distributed Asyncio Event Loop](https://temporal.io/blog/durable-distributed-asyncio-event-loop) is a great read. In fact, this is very much similar to how it works in the .NET Durable Task Framework with `TaskOrchestrationSynchronizationContext` and `SynchronousTaskScheduler`, which I explained in my earlier post [What Actually Happens When a Durable Orchestration Awaits an Activity?](/blog/2026/09/21/durable-await-replay).

The underlying insight is the same: an event loop is really just a loop that runs ready callbacks in memory until every coroutine is parked waiting on a future, and then waits to be triggered again.

The difference is who owns the outer runtime. In Temporal's Python SDK, Temporal owns the runner from the top (`@workflow.run async def run(self):`), so their Rust-backed worker drives its custom `AbstractEventLoop` from the outside and collects commands at the end of each tick. In my case, I didn't own the outer runner. The host library expected a synchronous `def fn(ctx): yield task` generator, and I couldn't change its contract. So instead of an engine driving an event loop from the outside, I had to embed a tiny trampoline `AbstractEventLoop` *inside* a generator (`yield from loop.drive_coroutine(...)`) so that `await` on the inside turns into `yield` on the outside.

* * *

## Attempt 1: The 10-Line Coroutine Driver (and Why It Breaks)

Under the hood in Python (just like `IAsyncStateMachine` and `IEnumerator` in C#), `def ... yield` generators and `async def ... await` coroutines are nearly identical state machines.

In CPython, a coroutine object created by an `async def` function has the same `.send(value)` and `.throw(exception)` methods as a generator. When an `async def` function hits an `await`, it suspends its frame and yields control up to whatever is driving it.

So my first attempt was the obvious 10-line bridge: step the coroutine with `.send()` and re-yield whatever comes out:

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

On paper, those 10 lines look like all you need. Beautiful. It works, in theory. But you know the old joke about the difference between theory and reality...

*(Side note, in case you don't: in theory, there is no difference between theory and reality. In reality, there is.)*

And reality hits the moment you point those 10 lines at a real `async` library:

```text
RuntimeError: no running event loop
```

Real-world `async` libraries don't just `await` leaf functions in isolation. They call `asyncio.get_running_loop()` and `asyncio.current_task()` (often through `anyio`) to manage `AsyncExitStack` cleanup, cancellation scopes, and `contextvars`. When you step a raw coroutine with `coro.send(None)`, there is no running `asyncio` event loop.

Even more importantly, they fan out concurrent work. When a library runs three operations in parallel, it spawns child tasks using `asyncio.gather()` or `anyio.create_task_group()`. A raw `coro.send()` loop has no task scheduler and no microtask queue to step multiple child coroutines together.

* * *

## Why Running `asyncio.run()` on a Second Thread Is a Trap

The next temptation is to spin up a background thread running `asyncio.run()` and pass tasks back and forth to the `yield` generator over a thread-safe `queue.Queue`.

If the caller is an ordinary blocking function, that works fine. When the caller is a `yield` generator, though, a two-thread queue bridge falls apart in two ways:

1. **Abandoned generators leak blocked threads.** Generator runners often step a generator up to a `yield`, see that the yielded task isn't completed yet, and discard the generator frame until the work finishes later. If you have a background thread blocked on `queue.get()` inside `asyncio.run()`, that thread is orphaned and hangs forever.
2. **Thread scheduling breaks deterministic batching.** Suppose your `async` code spawns three parallel child tasks (`Task A`, `Task B`, `Task C`) via `asyncio.gather()`. If the event loop is running on a separate OS thread, the generator thread might wake up and `yield` as soon as `Task A` pushes to the queue, before `Task B` and `Task C` even reach their `await` lines. Instead of one batch of three parallel tasks, you get timing-dependent behavior that changes from run to run.

I didn't want two threads racing over a queue. I wanted Bart De Smet's trampoline: one thread and one flat loop, where the `async` tasks jump up, run every ready microtask in memory until they all hit their suspension point, and land back on the trampoline together.

* * *

## The Real Solution: A Single-Threaded `TrampolineLoop`

Instead of fighting `asyncio`, Python lets you subclass `asyncio.BaseEventLoop` and build a deterministic, zero-I/O, single-threaded trampoline loop in about a hundred lines of code.

If you come from C# and .NET and ever worked with **WPF**, this is the exact same mechanism as the **WPF `Dispatcher`** (`DispatcherSynchronizationContext` + `Dispatcher.PushFrame`):

- When an `await` finishes on the WPF UI thread, `DispatcherSynchronizationContext.Post()` doesn't call the continuation directly on the stack. It calls `Dispatcher.BeginInvoke()`, dropping a `DispatcherOperation` into a single-threaded queue.
- When you call `Dispatcher.PushFrame(frame)`, WPF runs a loop on that same thread, popping queued items one by one until `frame.Continue = false` and returning control to the caller.

Our `TrampolineLoop` does the same thing for Python coroutines. `call_soon()` is `Dispatcher.BeginInvoke()`, dropping callbacks into an in-memory `collections.deque`. And `drain_ready()` is `Dispatcher.PushFrame()`, pumping queued microtasks on the current thread until every active task is parked on an external `YieldFuture`, then exiting so the outer generator can `yield`.

<pre class="mermaid">sequenceDiagram
    participant Gen as Outer yield Generator
    participant Tramp as TrampolineLoop (drain_ready)
    participant Tasks as async/await Tasks (gather / anyio)

    Gen->>Tramp: 1. drain_ready() (installs loop on current thread)
    Tramp->>Tasks: 2. Run _ready microtasks in a flat while loop
    Tasks->>Tramp: 3. Child tasks await YieldFuture(task_1), YieldFuture(task_2)
    Note over Tramp,Tasks: _ready queue is now empty!&lt;br/&gt;All active tasks are parked on YieldFutures
    Tramp-->>Gen: 4. Return pending [YieldFuture_1, YieldFuture_2]
    Gen-->>Gen: 5. yield [task_1, task_2] to outer runner
    Gen->>Tramp: 6. Feed results into YieldFutures &amp; repeat!</pre>

Here are the three parts of the implementation.

### 1. `YieldFuture`

First, we need an awaitable object that connects the two sides. `YieldFuture` is a real `asyncio.Future` bound to our `TrampolineLoop`, holding the `external_task` object that the outer `yield` generator knows how to run:

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

Because `YieldFuture` is a standard `asyncio.Future`, whenever an `async def` function runs `result = await loop.create_yield_future(external_task)`, `asyncio` suspends the current `asyncio.Task` and registers the task's wakeup callback on the future.

### 2. `TrampolineLoop` and `drain_ready()`

Next is `TrampolineLoop`. It doesn't open sockets, touch OS selectors, or spawn threads. Its `call_soon` method just appends a callback handle to `self._ready`:

```python
class TrampolineLoop(asyncio.BaseEventLoop):
    """Single-threaded trampoline event loop with zero OS I/O."""

    def __init__(self) -> None:
        self._ready: deque[asyncio.Handle] = deque()
        self._pending_yields: list[YieldFuture[Any]] = []
        self._running = False
        self._closed = False
        super().__init__()

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

And `drain_ready()` is the trampoline loop itself:

```python
    def drain_ready(self) -> list[YieldFuture[Any]]:
        """Bounce through all ready microtasks until every task is parked on a YieldFuture."""
        prev_loop = asyncio._get_running_loop()
        asyncio._set_running_loop(self)
        self._running = True
        try:
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

Trace what happens inside `while self._ready:` when the `async` library uses `asyncio.gather()` or `anyio.create_task_group()` to run three tasks in parallel:

1. Because `asyncio._set_running_loop(self)` is active, `asyncio.get_running_loop()`, `asyncio.current_task()`, `AsyncExitStack`, and `anyio` task groups all see a running `asyncio` loop.
2. When `gather()` or `TaskGroup` spawns three child `asyncio.Task`s, each child task queues its initial step callback onto `self._ready`.
3. Before `drain_ready()` returns, the `while self._ready:` loop pops and runs all three child tasks up to their `await create_yield_future(...)` suspension points.
4. Once every runnable callback in memory has settled, `self._ready` is empty, and `drain_ready()` returns all three pending `YieldFuture`s in deterministic order.

### 3. `drive_coroutine()`

Finally, `drive_coroutine()` is the generator method that the outer `yield`-based code calls with `yield from`:

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

            if not pending:
                raise RuntimeError("Coroutine parked without yielding a YieldFuture")

            if len(pending) == 1:
                yf = pending[0]
                try:
                    result = yield yf.external_task
                except GeneratorExit:
                    raise
                except BaseException as exc:
                    yf.set_exception(exc)
                else:
                    yf.set_result(result)
            else:
                batch_tasks = [yf.external_task for yf in pending]
                try:
                    results = yield batch_tasks
                except GeneratorExit:
                    raise
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

When `yf.set_result(result)` runs, `asyncio.Future` schedules the task's wakeup callback back onto `self._ready`. On the next iteration of `while not root_task.done():`, `drain_ready()` bounces the coroutine forward to the next `await`, or all the way to its return value.

From the outer generator, calling into the `async` library is now a single `yield from`:

```python
def my_generator_flow(ctx, payload: str):
    loop = TrampolineLoop()
    answer = yield from loop.drive_coroutine(run_async_library(payload))
    return answer
```

* * *

## The Mirror-Image Problem on the Callback Side

While building this, I also ran into the mirror-image problem when calling `async def` functions from synchronous callbacks (`def run_step(...) -> dict:`).

The obvious tool there is `asyncio.run(coro)`.

Just like the naive `coro.send()` driver, `asyncio.run()` has a subtle trap with stateful libraries: **it creates a new event loop and closes it as soon as the call returns.**

If the `async` library caches an `httpx.AsyncClient` connection pool, an `aiosqlite` database connection, or an `asyncio.Lock` across calls, those objects bind themselves to the event loop that was active when they were created. On the second call, when `asyncio.run()` spins up a fresh event loop and closes the first one, you get:

```text
RuntimeError: Event loop is closed
# or:
RuntimeError: Task got Future attached to a different loop
```

If you ever wrote WPF and got hit with `"The calling thread cannot access this object because a different thread owns it"` on a `DependencyObject`, this is the same affinity problem on an event loop.

And the fix is the same `Dispatcher.Invoke()` pattern from WPF: instead of creating and closing an event loop on every synchronous call with `asyncio.run()`, start one persistent daemon event-loop thread (`loop.run_forever()`, like `Dispatcher.Run()`) per process and submit coroutines to it via `asyncio.run_coroutine_threadsafe(coro, bg_loop).result()`. The synchronous caller blocks until the coroutine finishes, while `httpx` pools and `aiosqlite` connections stay warm on the same event loop across calls.

* * *

## Coming Full Circle

In a way, writing this bridge felt like coming full circle.

Back when I used to read those posts by Bart De Smet and the Rx team and watch their sessions on Channel 9, I was completely fascinated. I remember sitting there taking it all in and just wishing that one day I would get to work on problems like that. Their words pushed me to aim as far as I possibly could, and sitting here today, I feel like I am actually living that dream.

So who knows. Maybe someone reading this post right now feels that exact same spark, and a few years from now, they'll be writing a blog post about something they remembered from me.

