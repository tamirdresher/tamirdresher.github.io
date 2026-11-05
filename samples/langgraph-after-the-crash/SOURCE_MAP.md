# Public upstream source map

These are version-tagged public sources, not copies of library code. The six
complete modules below were fetched and matched byte-for-byte to the installed
modules used for the study's mechanism check. Line ranges are for those tags.

| What the source establishes | Public source |
|---|---|
| Factory routing creates one `Send("tools", [tool_call])` per pending call | [LangChain 1.3.14 factory, lines 1840–1881](https://github.com/langchain-ai/langchain/blob/langchain%3D%3D1.3.14/libs/langchain_v1/langchain/agents/factory.py#L1840-L1881) |
| The synchronous loop obtains its submitter from `BackgroundExecutor` | [LangGraph 1.2.10 loop, line 1691](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/_loop.py#L1691) |
| Pending task outputs are submitted to the saver through `self.submit` | [Loop, lines 415–500](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/_loop.py#L415-L500) |
| The synchronous runner receives the loop's submitter | [Pregel main, lines 2923–2928](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/main.py#L2923-L2928) |
| Tool task work uses that submitter; completed work commits writes | [Runner, lines 258–275](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/_runner.py#L258-L275), [lines 570–615](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/_runner.py#L570-L615) |
| Background submission delegates to its configured thread pool | [Executor, lines 40–75](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/_executor.py#L40-L75) |
| The pool reads `max_concurrency` as `max_workers` | [Core 1.5.3 config, lines 660–675](https://github.com/langchain-ai/langchain/blob/langchain-core%3D%3D1.5.3/libs/core/langchain_core/runnables/config.py#L660-L675) |
| Successful graph writes reattach by task ID; execution selects tasks lacking writes | [Loop, lines 736–749](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/_loop.py#L736-L749), [main, line 2968](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/main.py#L2968) |
| Native task replay resolves saved `RETURN` values in a different path | [Module-level runner `_call`, lines 700–780](https://github.com/langchain-ai/langgraph/blob/1.2.10/libs/langgraph/langgraph/pregel/_runner.py#L700-L780) |

Source inspection establishes the call graph and bounded pool configuration.
The [probe](lab.py) additionally observes actual submitted saver futures queued
on the same one-slot executor as running car, and [the wrappers](executor_trace.py)
record whether saver entry/exit occurs. Source inspection alone is not a trace.

The SQLite saver package is pinned separately in `requirements.txt`; the
LangGraph tag is not assumed to be an exact source snapshot of every separately
versioned checkpoint package.
