---
layout: post
date: 2026-10-10
title: "What LangGraph Actually Builds: Runnables, Channels, Bubble-Up, Agents and Deep Agents"
tags: [langgraph, langchain, deep-agents, ai-agents, python, internals]
---

I spent a while reading LangGraph's source, and the thing that surprised me most is how *small* the core idea is. A graph, a ReAct agent and a Deep Agent are not three different machines. They are one machine (Pregel) fed three different amounts of configuration.

Everything below was run offline: no network, no live model, a scripted fake chat model. Versions are pinned to **langgraph 1.2.12, langchain-core 1.6.6, langchain 1.4.3, deepagents 0.7.20**; internals move between releases, so treat the class names as a snapshot. The code is in the [samples repo](https://github.com/tamirdresher/langgraph-internals-samples): [`langgraph_primitives_demo.py`](https://github.com/tamirdresher/langgraph-internals-samples/blob/main/langgraph_primitives_demo.py) produced every printed output in sections 1–6, and [`structured_cases.py`](https://github.com/tamirdresher/langgraph-internals-samples/blob/main/structured_cases.py) covers section 5c.

## Side notes before we start: Python pieces and C# equivalents

If you come from C#, a few Python/LangGraph words show up immediately. They're plain Python or plain LangGraph.

| You'll see | What it is | Closest C# idea |
|---|---|---|
| `TypedDict` | A dictionary whose keys and value types are declared for type checkers; at run time it's an ordinary `dict`. | A DTO / `record`, except it stays a dictionary. |
| `Annotated[list, operator.add]` | A type with attached metadata: "this is a `list`, *and* here's extra info." Python itself ignores the extra part; LangGraph reads it. | A type plus an attribute, e.g. `[Reducer(Add)] List<string> visited`. |
| `operator.add` | A plain function that does `a + b` (for lists, concatenation). | A method group such as `(a, b) => a + b`, passed as a `Func<T,T,T>`. |
| `lambda x: x + 1` | An anonymous function. That's what I meant by "unnamed" before: not a keyword of this project, just Python's lambda. | A C# lambda `x => x + 1`; a `Func<int,int>` delegate. |
| a function passed as a value | Functions are first-class objects, so `add_node("a", a)` just hands over the function. | Passing a delegate or method group. |
| `invoke`, `stream` | Methods on a runnable. | `Execute` / `IAsyncEnumerable<T>` on an interface. |

Two LangGraph words are worth fixing in your head now.

**State** is the dictionary that flows through the graph. Every node receives it and returns a partial update to it, not a whole new state. If you know C#, think of an immutable record plus `with { ... }` expressions, applied by the engine for you.

**Channel** is one named slot of that state, and it owns the rule for how new values are merged in. A state key `total` becomes a channel called `total`. The rule matters when several nodes write in the same round: should the new value replace the old one, or be combined with it? In C# terms a channel is roughly a field paired with its own merge function, like `Func<T, T, T> merge`.

The name is misleading if you know C#. It is **not** `System.Threading.Channels`: nothing is queued for a consumer to await, and nothing blocks. It is **not** Rx's `IObservable`: nothing pushes values to subscribers. It is not a TPL Dataflow block either, though that is the closest family, because "a node runs when something it depends on was updated" is the same idea as dataflow triggering. The nearest literal picture is a **versioned cell in a shared state object**: a field whose `Update(IEnumerable<T> writes)` method decides how writes combine, plus a version number that goes up when it changes. Nodes are woken by comparing those versions, not by receiving messages. (Two exceptions behave a bit more like queues: `Topic`, used for `Send`, collects several values; `EphemeralValue` holds a value for one round only.)

**Reducer** is that merge function: `reducer(old, new) -> combined`. You attach one with `Annotated`. If you've used LINQ's `Aggregate`, it's the same shape: fold each new value into a running one. `operator.add` as a reducer on a list means "append the new items to the old items".

With those in hand, here is the smallest interesting graph.

## 1. The only contract: `Runnable`

A `Runnable` is anything with `invoke`, `ainvoke`, `stream`, `astream`, `batch` and `with_config`. That's it. In C# you'd call this an interface that everything implements, an `IRunnable<TIn, TOut>`. The `|` operator composes two of them (Python lets a class overload `|`, like a C# `operator |`):

```python
chain = RunnableLambda(lambda x: x + 1) | RunnableLambda(lambda x: x * 10)
type(chain).__name__   # RunnableSequence
chain.invoke(1)        # 20
```

Why this matters: a compiled LangGraph is *also* a `Runnable`. Its MRO starts `CompiledStateGraph → Pregel → PregelProtocol`. (MRO is the method resolution order, Python's inheritance chain: `CompiledStateGraph : Pregel : PregelProtocol`.) So a whole graph can sit inside a chain, or inside a node of another graph. That is how subagents work later.

## 2. What `compile()` produces

Take the smallest interesting graph: two nodes with a state that has an overwrite field and an append field. A node is just a function that takes the state and returns a partial update:

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END

class S(TypedDict):
    total: int                              # bare key: one write per superstep
    visited: Annotated[list, operator.add]  # reducer: appends

def a(s):                               # node "a": doubles n, logs "a"
    return {"total": s["total"] * 2, "visited": ["a"]}

def b(s):                               # node "b": adds 1 to n, logs "b"
    return {"total": s["total"] + 1, "visited": ["b"]}

g = StateGraph(S)
g.add_node("a", a)
g.add_node("b", b)
g.add_edge(START, "a")
g.add_edge("a", "b")
g.add_edge("b", END)
app = g.compile()
app.invoke({"total": 10, "visited": []})        # {'total': 21, 'visited': ['a', 'b']}
```

`StateGraph` is only a builder (like a C# `ServiceCollection` before `BuildServiceProvider()`). `compile()` lowers it into primitives. Here is what the demo prints for the compiled object:

Those lines are not part of the graph code above. They come from a small inspection helper I wrote (it's `show()` in the [demo script](https://github.com/tamirdresher/langgraph-internals-samples/blob/main/langgraph_primitives_demo.py)). It reads the public attributes of the compiled object, `app.channels` and `app.nodes`:

```python
# `app` is the compiled graph from above (a Pregel object)
print("channels:", {name: type(ch).__name__ for name, ch in app.channels.items()
                    if not name.startswith("branch:")})    # hide the per-edge channels for brevity
for name, node in app.nodes.items():
    if name == "__start__":
        continue                                            # internal input node, skipped for brevity
    print(f"node {name!r}: triggers={node.triggers} bound={type(node.bound).__name__}"
          f" writers={len(node.writers)}")
```

which prints:

```
channels: {'total': 'LastValue', 'visited': 'BinaryOperatorAggregate',
           '__start__': 'EphemeralValue', '__pregel_tasks': 'Topic'}
node 'a': triggers=['branch:to:a'] bound=RunnableCallable writers=2
node 'b': triggers=['branch:to:b'] bound=RunnableCallable writers=1
```

The lines starting with `node` describe `PregelNode` objects, so here is what one is. This is the class from `langgraph/pregel/_read.py`, trimmed to the fields that matter here (I left out error-handler and subgraph fields, and the docstrings are mine, condensed from the source's):

```python
class PregelNode:
    # A container, not a Runnable. The engine uses it to build a runnable task each time the node fires.

    channels: str | list[str]      # which channels to READ as input. For node "a": ['total', 'visited'],
                                   # so your function receives a dict with those two keys (the `s` in `def a(s)`)
    triggers: list[str]            # which channels WAKE the node: if any is written, the node runs next step.
                                   # For node "a": ['branch:to:a']
    bound: Runnable                # the actual logic: a Runnable wrapping your function, called with the input
    writers: list[Runnable]        # run AFTER `bound`; each takes its output and writes it to channels
                                   # (one stores your return value in state, one wakes the next node)
    mapper: Callable | None        # optional transform of the input before `bound` (None for node "a")

    retry_policy: Sequence[RetryPolicy] | None   # what happens if the node raises (None here)
    cache_policy: CachePolicy | None             # reuse results for identical input (None here)
    timeout: TimeoutPolicy | None                # per-invocation limit (async nodes only)
    tags: Sequence[str] | None                   # tracing labels
    metadata: Mapping[str, Any] | None           # tracing metadata
```

Note the split between `channels` (what it reads) and `triggers` (what wakes it). They are separate on purpose: a node can read many channels but be woken by just one. In C# terms a `PregelNode` is a record of "my inputs, my wake-up conditions, my handler, my post-processing", much like a message handler registration with a filter, except the messages are channel updates.

How to read the printout, line by line:

- **`'total': 'LastValue'`**: the `total` field became a channel of type `LastValue`. It holds one value, and a write replaces it. That is what the plain `total: int` in `S` meant.
- **`'visited': 'BinaryOperatorAggregate'`**: the `visited` field became a channel that combines old and new with your function, here `operator.add`. That is what `Annotated[list, operator.add]` meant, and why the list grows.
- **`'__start__': 'EphemeralValue'`**: an internal channel that carries your `invoke(...)` input into the graph. `EphemeralValue` means it only lives for one round.
- **`'__pregel_tasks': 'Topic'`**: an internal queue-like channel. It is where `Send` packets go (section 5c); our graph doesn't use it, but every graph has it.
- **`node 'a': triggers=['branch:to:a']`**: node `a` runs when the channel `branch:to:a` is updated. That channel is what the edge `START → a` turned into, so there is no edge object, only "wake `a` when this channel changes".
- **`bound=RunnableCallable`**: the thing that actually runs. It is a `Runnable` wrapper around your plain function `a`.
- **`writers=2` vs `writers=1`**: after `a` runs, two things write: one stores its returned update into `total`/`visited`, and one writes to `branch:to:b` to wake node `b`. `b` is last, so it only has the first writer; its edge goes to `END`, which wakes nothing.

Note the channel list has no `branch:to:a` or `branch:to:b`, because my filter hid them. They exist, one per edge, and the nodes' `triggers` point at them.

Here is the same transformation as a picture. The first diagram is what you drew with `add_edge`; the second is what `compile()` actually builds (I added the `__start__` input channel and the two writers per node to the picture, as the printout showed them):

**What you wrote (builder):**

<pre class="mermaid">flowchart LR
   S([START]) --> a --> b --> E([END])</pre>

**What `compile()` built (runtime):**

<pre class="mermaid">flowchart TD
   I["__start__ channel&lt;br/&gt;(your input)"] -->|wakes| CA["channel branch:to:a"]
   CA -->|wakes| NA["node a&lt;br/&gt;reads: total, visited&lt;br/&gt;bound = a(s)&lt;br/&gt;writer1 → total, visited&lt;br/&gt;writer2 → channel branch:to:b"]
   NA -->|wakes| NB["node b&lt;br/&gt;reads: total, visited&lt;br/&gt;bound = b(s)&lt;br/&gt;writer1 → total, visited&lt;br/&gt;(no writer2: its edge goes to END)"]</pre>

The arrows between nodes are gone in the second diagram. What remains are boxes (nodes) and named mailboxes (channels): "a" does not know "b" exists, it just drops a message in `branch:to:b`.

So the mental model is:

- **Channels** hold state (see the side notes above). Each state key becomes a channel whose *type* is its merge rule: `LastValue` keeps the latest value across steps but accepts **at most one write per superstep** (two parallel writers raise `InvalidUpdateError`, shown in 5c); `BinaryOperatorAggregate` applies your reducer (`operator.add`), which is why `visited` appends instead of replacing. Extra channels carry control flow: `__start__` holds the input, and an edge `a → b` becomes a channel named `branch:to:b`. The double underscores are only a naming convention for internal channels (Python's `__name__` style, not a keyword).
- **Nodes** are `PregelNode`s. Each has `triggers` (which channels wake it), `channels` (which it reads), `bound` (the actual `Runnable`, here a wrapper around your function) and `writers` (what it writes after running).
- **Edges disappear.** There is no edge object at run time. `a → b` is "a's writer writes to `branch:to:b`, and b triggers on `branch:to:b`". `get_graph()` reconstructs the pretty edge list for drawing, but the engine never walks it.

Conditional edges and `Send` use the same mechanism: a router `Runnable` runs as an extra writer and writes to whichever `branch:to:X` channels it chooses (or sends a task with its own input for map-reduce).

To see it, add a router to the same graph: `a` now picks `b` or `c` with `g.add_conditional_edges("a", route, ["b", "c"])`, where `route(s)` returns `"b"` if `s["total"] > 5` else `"c"`. As code (it reuses `S`, `a` and `b` from above, and adds node `c` and the router):

```python
def c(s):                                # node "c": the alternative path, resets total
    return {"total": 0, "visited": ["c"]}

def route(s):                            # the router: returns the NAME of the next node
    return "b" if s["total"] > 5 else "c"

g = StateGraph(S)
g.add_node("a", a)
g.add_node("b", b)
g.add_node("c", c)
g.add_edge(START, "a")
g.add_conditional_edges("a", route, ["b", "c"])   # replaces add_edge("a", "b")
g.add_edge("b", END)
g.add_edge("c", END)
app = g.compile()
app.invoke({"total": 10, "visited": []})   # {'total': 21, 'visited': ['a', 'b']}  (a: 20 > 5 -> b)
app.invoke({"total": 1,  "visited": []})   # {'total': 0,  'visited': ['a', 'c']}  (a: 2 -> c)
```

I compiled and ran this, and inspected it the same way:

```
channels: total=LastValue, visited=BinaryOperatorAggregate, __start__, __pregel_tasks=Topic,
          branch:to:a, branch:to:b, branch:to:c   (the last three are EphemeralValue)
node a: triggers=['branch:to:a']  writers=[state write, _route]
node b: triggers=['branch:to:b']  writers=[state write]
node c: triggers=['branch:to:c']  writers=[state write]
```

**What you wrote:**

<pre class="mermaid">flowchart LR
   S([START]) --> a
   a --> b --> E1([END])
   a --> c --> E2([END])</pre>

**What `compile()` built:**

<pre class="mermaid">flowchart TD
   NA["node a&lt;br/&gt;writer1: state write → total, visited&lt;br/&gt;writer2: _route(s) ← your router function"]
   NA -->|"router returns 'b'"| CB["writes branch:to:b"] -->|wakes| NB[node b]
   NA -->|"router returns 'c'"| CC["writes branch:to:c"] -->|wakes| NC[node c]</pre>

The difference from the linear case is only the second writer of `a`. Instead of a fixed write to `branch:to:b`, it is `_route`, which calls your function and writes to whichever channel the answer names. The other channel is never written, so that node simply doesn't run. With `total` starting at 10, `a` makes it 20, the router picks `b`, and `invoke` returns `{'total': 21, 'visited': ['a', 'b']}`; `c` never fires. Start at 1 and the router picks `c` instead. (`_route` is the internal writer's name as I saw it in this version; treat it as an implementation detail.)

## 3. Pregel: the superstep loop

Pregel is a model for computing over graphs, described in a 2010 Google paper (["Pregel: A System for Large-Scale Graph Processing"](https://research.google/pubs/pregel-a-system-for-large-scale-graph-processing/), SIGMOD 2010). It builds on the older "bulk synchronous parallel" idea. Open-source systems such as Apache Giraph, Spark GraphX and Flink Gelly offer the same vertex-centric model. LangGraph borrows the idea to run your graph (it also names its compiled graph class `Pregel`, and that is why the module is called `pregel`). In one sentence: work proceeds in rounds, where every ready node runs in parallel on the same snapshot of the state, and only when all of them finish are their results merged and the next round decided. In C# terms, picture a round of `Task.WhenAll(...)` over the ready nodes, where every task reads the same snapshot and a barrier merges their results before the next round. (LangGraph's version is an adaptation: Google's Pregel passes messages between graph vertices, while LangGraph's "vertices" are your nodes and the messages are channel writes.) If you work in .NET, you may already have met this algorithm: Microsoft Agent Framework's workflow engine, in both its C# and Python versions, uses what its docs call "a modified Pregel execution model — a Bulk Synchronous Parallel (BSP) approach with superstep-based processing", so its executors run in the same supersteps. See [Workflow Builder & Execution, "Execution Model: Supersteps"](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/builder-and-execution) for details. In `langgraph/pregel/_loop.py` each round is:

1. `tick`: check the stop conditions, then `prepare_next_tasks` finds every node whose trigger channel was updated since it last ran.
2. Run those tasks (in parallel if there is more than one). A task reads the channel values from the *start* of the round and returns writes; nothing it writes is visible to its siblings.
3. `after_tick`: `apply_writes` merges all the writes into the channels through each channel's rule, bumps versions, emits stream output, and (with a checkpointer) saves a checkpoint.

Repeat until no node is triggered. Running the two-node graph with `invoke` gives `{'total': 21, 'visited': ['a', 'b']}`, and `stream_mode="updates"` shows one superstep per node:

```
[{'a': {'total': 20, 'visited': ['a']}}, {'b': {'total': 21, 'visited': ['b']}}]
```

The "write then apply at the barrier" split is the single most important idea. It's why parallel branches are safe (they can't see each other), why reducers exist (two branches writing the same key in the same round need an `Annotated` reducer, otherwise the graph fails), and why a checkpoint between rounds is a consistent snapshot of ordinary channels (the Deep Agents `DeltaChannel` is the exception, see 5b).

### Send: when one node must become many tasks

A normal edge says "after `a`, run `b`", once, with the shared state as input. Sometimes you don't know *how many* tasks you need until runtime: the model asked for three tools, or you have N documents to process. `Send(node, arg)` covers that. It is a small packet meaning "run this node once, with this private input", and a router can return a whole list of them:

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import START, END, StateGraph
from langgraph.types import Send

class S(TypedDict):
    items: list
    out: Annotated[list, operator.add]       # reducer, so parallel writes are appended

def fan(s):                                  # router: one Send per item
    return [Send("work", {"x": i}) for i in s["items"]]

def work(a):                                 # 'a' is the Send's argument, NOT the graph state
    return {"out": [a["x"] * 10]}

g = StateGraph(S)
g.add_node("work", work)
g.add_conditional_edges(START, fan, ["work"])
g.add_edge("work", END)
app = g.compile()

print(app.invoke({"items": [1, 2, 3], "out": []}))
```

Streaming with `stream_mode="debug"` and printing each `task` event shows what the loop scheduled (I ran this):

```
task work {'x': 1} step 1
task work {'x': 2} step 1
task work {'x': 3} step 1
{'items': [1, 2, 3], 'out': [10, 20, 30]}
```

One node, three tasks, all in the same superstep, each with its own input. Who does what:

- **You (or `create_agent`) write the router.** It only *returns* the `Send` objects; it doesn't run anything.
- **The Pregel loop owns the tasks.** The router's return value is written to the internal `__pregel_tasks` channel (the `Topic` from section 2). At the next barrier the loop reads that channel and, for each packet, builds a task for the named node with the packet's argument as its input (internally `prepare_push_task_send`, as opposed to the ordinary "triggered by a channel" tasks). The runner then executes those tasks together, like any other superstep.
- **When:** the router runs at the end of one superstep; the `Send` tasks run in the very next one. They then write their results through the normal channels, which is why the example needs the `operator.add` reducer: three tasks wrote `out` in the same round.

The C# picture is `await Task.WhenAll(items.Select(i => Work(i)))`, except the list is decided by a router in the middle of the graph, and each of those calls is a first-class task that gets its own checkpoint writes. This is exactly what `create_agent` does for parallel tool calls, as the next section shows.

**In one sentence:** the Pregel loop runs your graph in *supersteps*, where a superstep is one round in which every ready node runs on the same snapshot of state and all their writes are merged at a barrier before the next round starts.

## 4. Example: an AI agent is just a graph

Before the harder parts (bubble-up, reducers, durability), here is the payoff of everything so far: an AI agent is expressed as a graph. It sounds like a different species, but `create_agent(model, tools=[...])` returns a `CompiledStateGraph`, the same kind of object as `app` in section 2. So we can read how it is built, then run it, then look at the graph it produces.

### 4.1 The code of `create_agent`

`create_agent` is not magic; it is a function that makes a `StateGraph` using the same builder calls as section 2 and compiles it. Below is the relevant core of `langchain/agents/factory.py` (langchain 1.4.3), **condensed by me** to the path with no middleware and no structured output; the real file is about 2,000 lines, and bodies marked `...` are omitted. The node and router functions are shown in full, simplified from `model_node`, `_make_model_to_tools_edge` and `_make_tools_to_model_edge`:

```python
def create_agent(model, tools, ...):
    graph = StateGraph(state_schema=AgentState, ...)   # 'messages' etc. become channels

    # ---- node 1: "model" -- a plain function node ----
    def model_node(state, runtime):
        messages = state["messages"]                    # read the channel
        if system_message:
            messages = [system_message, *messages]
        ai_message = model.bind_tools(tools).invoke(messages)   # call the chat model
        return {"messages": [ai_message]}               # write: append to 'messages'
    graph.add_node("model", RunnableCallable(model_node))

    # ---- node 2: "tools" -- a ToolNode, itself a Runnable ----
    tool_node = ToolNode(tools)    # reads the last AIMessage's tool_calls, runs each tool,
    graph.add_node("tools", tool_node)                  # and writes one ToolMessage per call

    graph.add_edge(START, "model")                      # entry point

    # ---- router after "model": tool calls -> "tools", otherwise finish ----
    def model_to_tools(state):
        last_ai = last_ai_message(state["messages"])
        if not last_ai.tool_calls:                      # classic exit condition of an agent loop
            return END
        pending = [c for c in last_ai.tool_calls if c["id"] not in answered_ids(state)]
        return [Send("tools", [call]) for call in pending]   # one task per pending tool call
    graph.add_conditional_edges("model", model_to_tools, ["tools", END])

    # ---- router after "tools": loop back, unless a return_direct tool ran ----
    def tools_to_model(state):
        if all_executed_tools_are_return_direct(state):
            return END
        return "model"                                  # let the model read the results
    graph.add_conditional_edges("tools", tools_to_model, ["model"])

    return graph.compile(checkpointer=checkpointer, ...)   # same compile() as section 2
```

Three things are worth noticing, because they connect back to what we already saw:

- **Nodes are ordinary functions of state.** `model_node` reads the `messages` channel and returns a partial update that the reducer appends. That is exactly what node `a` did in section 2. `ToolNode` is just another `Runnable`.
- **The loop is two conditional edges.** `model_to_tools` and `tools_to_model` are the same kind of router as `route` in section 2. The cycle `model → tools → model` is the whole agent loop.
- **Parallel tool calls are `Send`.** When the model asks for two tools at once, the router returns one `Send("tools", [call])` per call, so each runs as its own task in the next superstep (the `Send` mechanism explained at the end of section 3). In our one-tool run there is just one pending call, so there is one task.

The real function adds more nodes and edges when you pass middleware or a response format (that is what the extra `...middleware.before_agent` nodes in the Deep Agents section are), but the skeleton is this.

### 4.2 Using it

Here is the code from the demo that calls `create_agent`. To stay offline and deterministic it uses a *scripted* model, a fake chat model that first asks to call the tool `double(21)` and then, once it sees the tool's result, answers. (A real agent would pass a real chat model in its place.)

```python
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

@tool                                    # turns a plain function into a tool the model can call
def double(n: int) -> str:
    """Double n."""                      # the docstring is the description the model sees
    return str(n * 2)

class Scripted(BaseChatModel):           # a fake model with a fixed script
    @property
    def _llm_type(self): return "scripted"
    def bind_tools(self, tools, **kw): return self.bind(tools=tools, **kw)
    def _generate(self, messages, stop=None, run_manager=None, **kw):
        done = [m for m in messages if isinstance(m, ToolMessage)]
        if not done:                     # turn 1: no tool result yet, so ask for the tool
            msg = AIMessage(content="", id="ai-1", tool_calls=[
                {"name": "double", "args": {"n": 21}, "id": "call-1", "type": "tool_call"}])
        else:                            # turn 2: tool result is in the history, so answer
            msg = AIMessage(content=f"answer {done[-1].content}", id="ai-2")
        return ChatResult(generations=[ChatGeneration(message=msg)])

agent = create_agent(Scripted(), tools=[double])      # one call builds the whole graph
out = agent.invoke({"messages": [HumanMessage("double 21")]})
```

Inspecting `agent` the same way as before prints:

```
nodes   : ['model', 'tools']
channels: {'messages': 'BinaryOperatorAggregate', 'jump_to': 'EphemeralValue',
           'structured_response': 'LastValue', '__start__': ..., '__pregel_tasks': ...}
node 'model': bound=RunnableCallable
node 'tools': bound=ToolNode
edges   : [('__start__','model'), ('model','__end__',cond), ('model','tools',cond), ('tools','model',cond)]
messages: HumanMessage 'double 21' → AIMessage[tool_call double] → ToolMessage '42' → AIMessage 'answer 42'
```

### 4.3 The graph it produced

The graph that `create_agent` built is small. Asking the compiled object to draw itself (`agent.get_graph().draw_mermaid()`) gives this, where dashed arrows are conditional edges:

<pre class="mermaid">graph TD;
    __start__([__start__]) --> model(model)
    model -.->|tool calls present| tools(tools)
    model -.->|no tool calls| __end__([__end__])
    tools -.-> model</pre>

This is what `get_graph().draw_mermaid()` produced (I ran it), with the two edge labels added by me to explain the routing. Walking it with our run: `__start__` puts the `HumanMessage` into `messages` and wakes `model`. The scripted model replies with a tool call, so the router sends the run to `tools`. `tools` executes `double(21)` and appends a `ToolMessage('42')`, which wakes `model` again. This time the reply has no tool calls, so the router goes to `__end__`. That is the `messages:` line above: two trips through `model`, one through `tools`.

That is the whole ReAct loop:

- State is a `messages` channel with an *append* reducer (so the conversation accumulates, just like `visited` above).
- `model` is a node that calls the chat model. `tools` is a `ToolNode`: a `Runnable` that reads the last `AIMessage`'s `tool_calls`, runs each tool and writes `ToolMessage`s.
- The loop is a **conditional edge** out of `model`: tool calls present → `tools`, otherwise → `__end__`. And `tools → model` is a plain back-edge. A cycle in the graph is the agent loop; the Pregel loop just keeps ticking while something is triggered.

Nothing agent-specific exists in the engine. "Agent" is a graph *shape*.

## 5. Graph bubble-up

A quick way to place this next to `Send` from the previous section: both are things a node or router hands to the loop, but in opposite directions. `Send` is **data going down**: a request to *create* tasks, written to a channel and picked up at the next barrier. Bubble-up is a **control signal going up**: an exception that *stops* work and travels from inside a node to the code that owns the run. They are separate mechanisms. They meet in one place: a task created by `Send` is an ordinary task, so if it calls `interrupt()` or raises a `GraphBubbleUp`, that signal bubbles up through the loop like any other (for example, an agent whose tool asks a human for approval).

Some things a node does are not return values. `interrupt("approve?")` has to stop the whole run, not just the node. LangGraph implements that as an exception, much like throwing a custom exception in C# that a `catch` further up the stack deliberately handles:

```
GraphBubbleUp(Exception)
  ├─ GraphDrained        (cooperative drain)
  ├─ GraphInterrupt      (interrupt(), human-in-the-loop)
  │    └─ NodeInterrupt
  └─ ParentCommand       (a subgraph telling its parent what to do)
```

"Bubble up" means exactly that: the exception is raised inside the node and travels *up* through the runner. Per `_retry.py` and `_runner.py`:

- the retry wrapper (`run_with_retry`) deliberately does **not** retry a `GraphBubbleUp`; ordinary exceptions go through your `RetryPolicy`;
- a `GraphInterrupt` has its pending writes saved to the checkpointer, so the pause survives;
- a `ParentCommand` is handled by the enclosing graph, which is how a `Command(graph=Command.PARENT, ...)` from a subgraph reaches its parent; a root graph suppresses a `GraphInterrupt` and returns the interrupt in its result rather than raising.

`Command` is just a small dataclass of four optional fields: `update`, `goto`, `resume`, `graph`. You use it in two places, and a different pair of fields matters in each:

- **Returned from a node**, to do "update state *and* route" in one step: `Command(update={"total": 1}, goto="b")`. `update` is applied like a normal node return value, and `goto` (a node name, a list of names, or `Send` packets) picks what runs next without needing an edge. `graph=Command.PARENT` aims it at the enclosing graph instead of the current one (that is the `ParentCommand` above).
- **Passed as the input to `invoke`**, to continue a paused run: `Command(resume="yes")`. Normally `invoke` takes new state; here it is told "don't start over, the saved run is waiting for an answer, and this is it". `resume` is the value that the pending `interrupt()` call returns.

The demo below uses the second form. The first form (`update`/`goto`) is shown in section 5c.

The demo shows the whole cycle with an in-memory saver. First the graph, with one node that calls `interrupt()`. A checkpointer is required, because the pause has to be saved somewhere:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

def ask(s):
    answer = interrupt("approve?")       # pauses the whole run here; returns the resume value next time
    return {"visited": [f"answer={answer}"]}

h = StateGraph(S)                        # same state class S as before
h.add_node("ask", ask)
h.add_edge(START, "ask")
h.add_edge("ask", END)
happ = h.compile(checkpointer=InMemorySaver())
cfg = {"configurable": {"thread_id": "t"}}   # identifies the saved conversation/run

print("first call :", happ.invoke({"total": 0, "visited": []}, cfg))   # runs until interrupt(), returns
print("next       :", happ.get_state(cfg).next)                        # which node is waiting
print("resumed    :", happ.invoke(Command(resume="yes"), cfg))         # continue, answering "yes"
```

which prints (the interrupt id is shortened):

```
first call : {'total': 0, 'visited': [], '__interrupt__': [Interrupt(value='approve?', id='014f…')]}
next       : ('ask',)
resumed    : {'total': 0, 'visited': ['answer=yes']}
```

Reading it: the first `invoke` does not raise. It returns normally, with the pending question under `__interrupt__`. `get_state(cfg).next` says node `ask` is the one waiting. The second `invoke` is given a `Command(resume="yes")` instead of new input; it finds the saved checkpoint for the same `thread_id` and continues.

Note what "resume" really is: the node runs **again from the top**, and this time `interrupt()` returns the resume value instead of raising. That re-execution is why side effects before an `interrupt()` must be idempotent.

## 6. And Deep Agents

**Where it comes from.** `create_deep_agent` lives in the `deepagents` package, a separate open-source (MIT) project from LangChain, published at `langchain-ai/deepagents`. Its package metadata describes it as an "agent harness with a built-in filesystem and context management, sub-agent delegation, skills, and long-term memory", and marks it Beta (I used 0.7.20). It is not part of `langgraph` or `langchain`; it depends on `langchain`. Its source imports `create_agent` from `langchain.agents`, and its docstring says several arguments are "passed through to `create_agent`".

**Where it sits in the stack.** Think of three layers, each built on the one below:

```
deepagents   create_deep_agent   a ready-made "harness": files, subagents, summarization, skills, memory
   |  calls
langchain    create_agent        the model <-> tools loop, plus the middleware system
   |  builds
langgraph    StateGraph / Pregel the runtime: channels, supersteps, checkpoints
```

In C# terms: LangGraph is the runtime (like ASP.NET's host and pipeline), `create_agent` is a minimal app template, and Deep Agents is the opinionated starter kit that pre-installs a set of middleware on that template. Which is why the graph below looks the same as section 4's.

`create_deep_agent(model=..., tools=[...])` also returns a `CompiledStateGraph`, with the same `model` and `tools` nodes, plus a middleware node. What the demo printed:

```
nodes   : ['model', 'tools', 'PatchToolCallsMiddleware.before_agent']
channels: messages: DeltaChannel, files: DeltaChannel,
          _summarization_event, _summarization_session_id, ...
tools the model sees: ['delete','double','edit_file','execute','glob','grep','ls','read_file','task','write_file']
edges   : ... ('model','model',cond), ('model','tools',cond), ('tools','model',cond) ...
```

So Deep Agents is the agent graph with extra *state* and extra *tools*, added by middleware:

- **Extra channels:** `files` (a virtual file system kept in graph state) and summarization bookkeeping for long conversations. `messages` is a `DeltaChannel` here rather than a plain reducer channel, so I wouldn't assume the agent's channel types equal the plain agent's.
- **Extra tools:** `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `execute` from the filesystem middleware, and `task`. `execute` is listed to the model, but the default `StateBackend` has no `execute` (I checked: `hasattr(StateBackend, "execute")` is `False`); it only runs when the backend implements `SandboxBackendProtocol`, otherwise it returns an error. So no shell access by default, and `files` is ephemeral graph state.
- **A middleware hook as a node:** `PatchToolCallsMiddleware.before_agent` runs before the first model call (it repairs dangling tool calls). Only middleware that overrides `before_agent`, `before_model`, `after_model` or `after_agent` adds nodes (I confirmed `M.before_model` and `M.after_model` appear in `nodes`); middleware that wraps model or tool calls does not.

### What is middleware?

Middleware is how `create_agent` is extended without editing the loop. It is the same idea as ASP.NET middleware or `DelegatingHandler`: you write a class, hand a list of them to `create_agent(..., middleware=[...])`, and the loop calls your hooks at defined points. `AgentMiddleware` has two families of hooks (from `langchain/agents/middleware/types.py`):

- **Node hooks**, which run *between* steps: `before_agent`, `before_model`, `after_model`, `after_agent`. They receive the state and return a state update (or `None`), and can set `jump_to` to redirect the loop. Each one you override becomes a **real node in the graph**.
- **Wrap hooks**, which run *around* a call: `wrap_model_call(request, handler)` and `wrap_tool_call(request, handler)`. You call `handler(request)` to continue, so you can change the request, retry, short-circuit or post-process the response. These live inside the existing `model` and `tools` nodes, so they add no nodes.

A middleware can also contribute `tools` and extra state keys. I ran this to check:

```python
class Audit(AgentMiddleware):
    def before_model(self, state, runtime):             # a node hook
        log.append(f"before_model: {len(state['messages'])} msgs"); return None
    def wrap_model_call(self, request, handler):        # a wrap hook
        log.append("wrap_model_call: enter")
        resp = handler(request)                         # the next layer, ending in the model
        log.append("wrap_model_call: exit"); return resp

agent = create_agent(fake_model, middleware=[Audit()])
```

```
nodes: ['Audit.before_model', '__end__', '__start__', 'model']
log  : ['before_model: 1 msgs', 'wrap_model_call: enter', 'wrap_model_call: exit']
```

`Audit.before_model` is a new node; `wrap_model_call` added nothing to the graph but ran around the model call. That is exactly the `PatchToolCallsMiddleware.before_agent` node in the Deep Agents output above. Deep Agents is mostly a curated middleware list (filesystem, summarization, tool-call patching, optional skills and memory).

### What is the state backend?

Deep Agents' file tools (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`) do not touch the disk directly. They call a **backend**, an object implementing `BackendProtocol` (`ls`, `read`, `write`, `edit`, `grep`, `glob`, `delete`, upload/download). The backend decides where files actually live, so the same agent can run against different storage. It is a repository/strategy interface, like `IFileProvider` in .NET. The backends in the package:

| Backend | Where files live |
|---|---|
| `StateBackend` (the default) | In the graph state's `files` channel. Ephemeral: persists within a thread through checkpoints, not across threads |
| `StoreBackend` | A LangGraph `BaseStore`, so persistent across conversations |
| `FilesystemBackend` | The real disk |
| `LocalShellBackend` | The real disk plus unrestricted local shell (`execute`) |
| `BaseSandbox` (and subclasses) | A sandbox that implements `execute()` |
| `CompositeBackend` | Routes by path prefix to other backends (for example `/memories/` to a store, the rest to state) |

Note: this is **not** the same thing as a LangGraph checkpointer, which is also sometimes called a state backend (section 5b). The checkpointer stores *the graph's* snapshots; the Deep Agents backend stores *the agent's files*. With the default `StateBackend` the two meet: its docstring says reads and writes go through `CONFIG_KEY_READ` and `CONFIG_KEY_SEND`, so a file write is just an ordinary channel write to `files`, applied at the barrier and checkpointed like any other state. That is why `files` showed up as a channel in the output above, and why the default needs no disk. `StateBackend` raises if used outside a graph run; to pre-seed files, pass `{"files": {...}}` to `invoke`.

> **Side note: the same pattern in the Squad SDK.** Squad's SDK ([bradygaster/squad](https://github.com/bradygaster/squad), `packages/squad-sdk`) has the matching idea in its **`StorageProvider`** interface (`read`, `write`, `append`, `list`, `delete`, `mkdir`, `rename`, `stat`, `createIfAbsent`...), with `FSStorageProvider` (default), `InMemoryStorageProvider` and `SQLiteStorageProvider`: a narrow interface, several implementations, one default. It was added by Dina Berry (`diberry`; [#567](https://github.com/bradygaster/squad/pull/567), [#640](https://github.com/bradygaster/squad/pull/640)). Squad also has a separate, higher-level `StateBackend` (working-tree files, an orphan git branch, or that plus git notes), which is *not* the same thing: an adapter wraps it as a `StorageProvider`. Source, pinned to the commit I read: [`storage-provider.ts`](https://github.com/bradygaster/squad/blob/e0c84dd0d32189ba0744cf5bb717906e02801215/packages/squad-sdk/src/storage/storage-provider.ts), [`state-backend.ts`](https://github.com/bradygaster/squad/blob/e0c84dd0d32189ba0744cf5bb717906e02801215/packages/squad-sdk/src/state-backend.ts), [State Backends docs](https://github.com/bradygaster/squad/blob/e0c84dd0d32189ba0744cf5bb717906e02801215/docs/src/content/docs/features/state-backends.md). Back to Deep Agents.

### What is `DeltaChannel`?

Both `messages` and `files` in the Deep Agents graph are `DeltaChannel`s instead of the plain reducer channel. The problem it solves: a normal reducer channel checkpoints its full value every step, so a long conversation or a large virtual file system is copied into every checkpoint. `DeltaChannel` (beta, `langgraph/channels/delta.py`) instead stores only a **sentinel** in ordinary checkpoints and rebuilds the value by replaying the earlier writes through the reducer, writing a full snapshot every so often (every 1000 updates by default). It is event sourcing: the log of writes is the truth, snapshots are an optimization.

The price is in its own docstring: the reducer must be deterministic and *batching-invariant* (`reducer(reducer(s, xs), ys) == reducer(s, xs + ys)`), and the checkpoint saver must keep the ancestor writes (`get_delta_channel_history`). Section 5b covers what this means for checkpoints.

### Deep Agents capability inventory

From the installed package layout (`deepagents/middleware` and `deepagents/backends`), and what I observed above:

- **Middleware modules:** filesystem, subagents, async subagents, summarization, memory, skills, permissions, rubric, patch-tool-calls, prompt caching, message eviction, overflow clipping, unsupported-content, tool exclusion.
- **Backends** (where `files`/`execute` actually go): state (graph state, the default seen in the demo), store, composite, filesystem, local shell, sandbox, LangSmith, context hub.
- Only middleware that defines `before_*`/`after_*` hooks becomes a graph node (we saw `PatchToolCallsMiddleware.before_agent`); the others wrap the model or tool call in place, so they don't appear in `nodes`. I inferred that rule from this one observed node and the module layout, not from reading the middleware loader.
- In this default build the model's tools were the seven filesystem/shell tools, `task`, and my own `double`. I did not see a todo-list tool, so I won't claim one.

### `task` is a graph calling a graph

The subagent mechanism is the most interesting part, and it is ordinary LangGraph. In `deepagents/middleware/subagents.py`, `task` is a `StructuredTool`. Its body prepares a fresh state (for a normal subagent just `{"messages": [HumanMessage(description)]}` plus non-private state keys), then calls:

```python
result = subagent.invoke(subagent_state, subagent_config)
return _return_command_with_state_update(result, runtime.tool_call_id)
```

Because a compiled graph is a `Runnable` (section 1), the subagent is simply another compiled agent invoked from *inside a tool call*. Its result comes back as a `Command(update={..., "messages": [ToolMessage(...)]})`, which the parent's `ToolNode` applies to the parent's channels. The subagent's context window is isolated; only its final message and selected state keys return.

## 5b. Reducers, channel types and checkpoints, for real

**Checkpoints.** With a checkpointer, each superstep boundary writes a row. The demo saves the two-node graph in an `InMemorySaver` and lists it:

```
step=-1 source=input values={'__start__': {'total': 10, 'visited': []}}
step= 0 source=loop  values={'total': 10, 'visited': []}
step= 1 source=loop  values={'total': 20, 'visited': ['a']}
step= 2 source=loop  values={'total': 21, 'visited': ['a', 'b']}
versions_seen keys: ['__input__', '__start__', 'a', 'b']
channel_versions: {'__start__': '2', 'total': '4', 'visited': '4', 'branch:to:a': '3', 'branch:to:b': '4'}
```

A checkpoint is a small dict: `channel_values`, `channel_versions`, `versions_seen`, `updated_channels`, an `id`, a timestamp and `v`. Two fields do the scheduling:

- `channel_versions` is a monotonically increasing version per channel (the real strings are zero-padded counters plus a random suffix; I shortened them).
- `versions_seen[node]` records which trigger version each node last consumed. `prepare_next_tasks` runs a node when a trigger channel's version is newer than what that node has seen. That is the whole "what runs next" rule, and it is why resuming from a checkpoint needs no extra bookkeeping.

Step `-1` stores the raw input; steps 0..N are loop supersteps. Writes made by tasks that have run but not yet been applied are stored separately as *pending writes* against their parent checkpoint (`put_writes`). That is how a crash in the middle of a parallel superstep doesn't lose the branches that already finished, and how `interrupt` state survives.

**The saver (state backend) contract.** `BaseCheckpointSaver` is the storage seam. The core methods are `put` (a checkpoint), `put_writes` (pending writes for a task), `get_tuple` and `list` (read), with async twins (`aput`, `aget_tuple`, ...), plus thread deletion/pruning helpers and a `serde` (here `JsonPlusSerializer`). Rows are addressed by `thread_id`, `checkpoint_ns` (the subgraph namespace) and `checkpoint_id`; a new thread id is a new empty history. I only ran `InMemorySaver`; I haven't exercised the SQLite or Postgres savers, so I make no claim about them.

**Caveat: `DeltaChannel`.** Deep Agents' `messages` and `files` use `DeltaChannel` (beta in `langgraph/channels/delta.py`). Per my reading of that source, not a run, it checkpoints a sentinel on ordinary steps and rebuilds the value from ancestor writes, with periodic full snapshots, so it needs deterministic reducers and savers that keep ancestor history. "Each checkpoint is a full snapshot" holds only for ordinary channels.

### 5c. When things get structured or go wrong: conflicts, routing, subgraphs, retry

The earlier sections showed the happy path. This one covers what happens when things go wrong or get more structured: two nodes fight over a key, a node needs to both update state and choose where to go, a graph contains another graph, a node throws, and you want to control how often state is saved or watch it live. I ran every snippet below offline (`structured_cases.py` in the samples repo); outputs are quoted as seen.

### Two parallel nodes write the same key

Remember the superstep rule from section 3: nodes in the same superstep all read the old state, and their writes are applied together at the barrier. So what if two of them write the same key? For a plain field like `total: int`, the channel is a `LastValue`, which can hold only one value. "Which of the two writes wins?" has no sane answer, so LangGraph refuses to guess:

```python
class S(TypedDict):
    total: int

g = StateGraph(S)
g.add_node("a", lambda s: {"total": 1})
g.add_node("b", lambda s: {"total": 1})
g.add_edge(START, "a")                           # a and b both start from START,
g.add_edge(START, "b")                           # so they run in the same superstep
g.add_edge("a", END)
g.add_edge("b", END)
g.compile().invoke({"total": 0})
```

```
InvalidUpdateError: At key 'total': Can receive only one value per step. Use an Annotated key to handle multiple values.
```

The error message already contains the fix. If you declare the key as `Annotated[list, operator.add]`, the channel becomes a `BinaryOperatorAggregate`, which knows how to combine several writes, and the same graph returns `{'total': ['a', 'b']}`. In C# terms: it is the difference between two threads assigning the same field (a race you must forbid) and two threads calling `list.AddRange` through a lock (a merge you defined). The reducer *is* the lock.

### `Command`: update state and choose the next node in one return

Normally a node returns a state update, and the *edges* decide what runs next. Sometimes the node itself knows where to go (a router, an agent deciding to hand off). Returning a `Command` lets it do both at once, as defined in section 5:

```python
def router(s):
    return Command(update={"out": ["r"]}, goto="t")   # write state AND pick the next node

g = StateGraph(C)                       # C has: total: int, out: Annotated[list, operator.add]
g.add_node("r", router)
g.add_node("t", lambda s: {"out": ["t"]})
g.add_edge(START, "r")
g.add_edge("t", END)                                   # note: no edge from r to t
g.compile().invoke({"total": 0, "out": []})
```

```
{'total': 0, 'out': ['r', 't']}
```

There is no `r → t` edge in the graph. The `goto` created that routing at run time, and `out` shows both nodes ran, in order. The other two uses of `Command` you already met: `resume=` to continue after an interrupt (section 5), and `graph=Command.PARENT` to send the update to the *enclosing* graph when you are inside a subgraph (next subsection). `Send` (section 3) is the third routing tool: use `goto` to pick one next node, `Send` to start many tasks with different inputs.

### A graph inside a graph (subgraphs)

Because a compiled graph is a `Runnable` (section 1), you can pass it to `add_node` like any function. The parent treats it as one node; inside, it runs its own supersteps. Its checkpoints live in their own namespace so they don't collide with the parent's, and `stream(..., subgraphs=True)` lets you see inside:

```python
child = StateGraph(C)                        # C is the same state schema as above
child.add_node("t", lambda s: {"out": ["t"]})
child.add_edge(START, "t")
child.add_edge("t", END)

parent = StateGraph(C)
parent.add_node("child", child.compile())    # a compiled graph used as a node
parent.add_edge(START, "child")
parent.add_edge("child", END)
app = parent.compile(checkpointer=InMemorySaver())

cfg = {"configurable": {"thread_id": "1"}}
for event in app.stream({"total": 0, "out": []}, cfg, subgraphs=True):
    print(event)
```

```
(('child:512f5449-103f-f070-0e96-928c949f2c95',), {'t': {'out': ['t']}})
((), {'child': {'total': 0, 'out': ['t']}})
```

Each event is `(path, update)`. The first has a non-empty path: node `t` finished *inside* the child. The second has the empty path `()`: the parent sees the whole `child` node finish. The path is the namespace. This is also why the `task` tool from section 6 is "a graph calling a graph".

### Retry: what happens when a node throws

A node that raises normally fails the whole run. Attach a `RetryPolicy` and the loop reruns just that node instead. One gotcha I hit: the default `retry_on` deliberately *excludes* `ValueError` (programming-error exceptions are not retried by default), so my flaky node needed `retry_on=ValueError` explicitly:

```python
def flaky(s):
    n["i"] += 1
    if n["i"] < 3: raise ValueError("boom")        # fails twice, then works
    return {"out": ["ok"]}

g.add_node("f", flaky, retry_policy=RetryPolicy(retry_on=ValueError, initial_interval=0.01))
```

```
{'total': 0, 'out': ['ok']}      # n["i"] == 3: two failures, third attempt succeeded
```

The retry is around the *node*, not the graph, so other nodes' finished work in the same superstep is not repeated. And the control-flow exceptions from section 5 (`GraphBubbleUp`: interrupts, parent commands) are never retried, because they are not failures. In C# this is Polly's `Retry` policy wrapped around one call, with the exception filter being `retry_on`.

### Saving less often, and watching live

Two knobs control the cost and visibility of all this machinery:

- **`durability`** on `invoke`/`stream` decides *when* checkpoints are written: `'sync'` (before the next step starts; safest, slowest), `'async'` (in the background while the next step runs), or `'exit'` (only when the run ends; fastest, but a crash loses the in-flight run). These descriptions are from the parameter's documented meaning, not something I measured. The signature default is `None`; I did not verify what that resolves to, so I don't state an effective default.
- **Stream modes** choose what `stream` emits: `values` (full state after each step), `updates` (just each node's return, which is what you saw above), `checkpoints`, `tasks`, `debug`, `messages` (LLM tokens), and `custom` (whatever your node writes via the stream writer). Same run, different views.

### Deep Agents extras (listed, not exercised)

From the module inventory only, I did not run these: skills, memory (prompt injection or a `BaseStore`), permissions, and `interrupt_on` human-in-the-loop. Subagents can be any compatible runnable, and `task` isolates context by default; an experimental fork mode inherits parent state.

### Reading state back, and time travel

`get_state(cfg)` returns a `StateSnapshot` (`values, next, config, metadata, created_at, parent_config, tasks, interrupts`), and `get_state_history(cfg)` walks the parent chain. **Time travel** is just picking an older snapshot and invoking from it:

```
state before b = {'total': 20, 'visited': ['a']}  ->  invoke(None, that config) = {'total': 21, 'visited': ['a', 'b']}
```

**The Store is a different thing.** A checkpointer is per-thread run state. `BaseStore` (demo: `InMemoryStore`) is cross-thread long-term memory addressed by a namespace tuple and a key: `store.put(("users","tamir"), "pref", {...})`. Deep Agents' `memory` and store-backed file backends build on this idea; I only verified the plain `InMemoryStore` here.

## A final thought

What stayed with me after reading all this code is how little magic there is. A graph is a set of channels and the nodes that wake when those channels change. Edges are just writes to channels, supersteps give you a clean read, write, merge rhythm, and the occasional special exception or `Command` is how a node steers the loop from the inside. An agent is that same machine with a model node and a tool node in a cycle, and a Deep Agent is the same machine again, with middleware adding channels, tools and hook nodes. Once I saw it that way, the docs, the stack traces and the checkpoints all started to make sense, and I stopped treating LangGraph as a black box.

If you want to poke at it yourself, everything in this post runs offline, with no API key, in the [samples repo](https://github.com/tamirdresher/langgraph-internals-samples). Pin the versions from the top of the post, because the internals move between releases.
