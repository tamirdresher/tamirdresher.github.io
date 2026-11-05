"""Observational runtime wrappers; no library files or scheduling policy changed."""
import functools
import json
import os
import threading
import time


def write_details(args, kwargs=None):
    values = dict(zip(("config", "writes", "task_id", "task_path"), args))
    values.update(kwargs or {})
    config, writes, task_id = values["config"], values["writes"], values["task_id"]
    calls = []
    for channel, value in writes:
        if channel == "messages" and isinstance(value, (tuple, list)):
            calls.extend(getattr(m, "tool_call_id", None) for m in value
                         if getattr(m, "tool_call_id", None))
    return {"task_id": task_id, "checkpoint_id": config["configurable"].get("checkpoint_id"),
            "channels": [c for c, _ in writes], "tool_call_ids": calls}


class ExecutorTrace:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.local = threading.local()
        self.jobs = {}
        self.sequence = 0
        self.cost_ns = 0
        self.count = 0

    def log(self, event, **fields):
        begin = time.perf_counter_ns()
        with self.lock:
            self.sequence += 1
            row = {"sequence": self.sequence, "monotonic_ns": time.monotonic_ns(),
                   "wall_time_ns": time.time_ns(), "pid": os.getpid(),
                   "thread_id": threading.get_ident(), "event": event, **fields}
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(row) + "\n")
                file.flush()
            self.count += 1
            self.cost_ns += time.perf_counter_ns() - begin

    def sample(self):
        with self.lock:
            for job, info in self.jobs.items():
                future = info.get("future")
                if future is not None:
                    self.log("future_sample", job=job, **info["meta"],
                             running=future.running(), done=future.done(),
                             cancelled=future.cancelled(), started=info["started"])
            self.log("logging_cost", events=self.count, measured_log_ns=self.cost_ns)

    def install(self):
        from langgraph.pregel._executor import BackgroundExecutor
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langchain_core.tools import StructuredTool
        original_submit = BackgroundExecutor.submit
        original_writes = SqliteSaver.put_writes
        original_tool_run = StructuredTool._run
        trace = self

        @functools.wraps(original_submit)
        def submit(executor, fn, *args, **kwargs):
            name = f"{getattr(fn, '__module__', '')}.{getattr(fn, '__qualname__', type(fn).__name__)}"
            meta = {"executor_id": id(executor), "pool_id": id(executor.executor),
                    "max_workers": executor.executor._max_workers, "function": name}
            if getattr(fn, "__name__", "") == "put_writes":
                meta.update(write_details(args, kwargs))
            elif args and hasattr(args[0], "id") and hasattr(args[0], "input"):
                task = args[0]
                meta.update(task_id=task.id, task_name=task.name)
                if isinstance(task.input, list):
                    meta["tool_call_ids"] = [c.get("id") for c in task.input
                                             if isinstance(c, dict) and "id" in c]
            with trace.lock:
                job = len(trace.jobs) + 1
                trace.jobs[job] = {"meta": meta, "started": False}
                trace.log("submit", job=job, **meta)

            @functools.wraps(fn)
            def observed(*inner_args, **inner_kwargs):
                with trace.lock:
                    trace.jobs[job]["started"] = True
                previous = getattr(trace.local, "job", None)
                trace.local.job = job
                trace.log("start", job=job, **meta)
                try:
                    result = fn(*inner_args, **inner_kwargs)
                except BaseException as exc:
                    trace.log("finish_error", job=job, **meta, error=type(exc).__name__)
                    raise
                else:
                    trace.log("finish", job=job, **meta)
                    return result
                finally:
                    trace.local.job = previous

            future = original_submit(executor, observed, *args, **kwargs)
            with trace.lock:
                trace.jobs[job]["future"] = future
            trace.log("submit_return", job=job, **meta, future_id=id(future),
                      running=future.running(), done=future.done(),
                      cancelled=future.cancelled())
            return future

        @functools.wraps(original_writes)
        def put_writes(saver, *args, **kwargs):
            details = write_details(args, kwargs)
            trace.log("saver_enter", job=getattr(trace.local, "job", None),
                      saver_id=id(saver), **details)
            try:
                result = original_writes(saver, *args, **kwargs)
            except BaseException as exc:
                trace.log("saver_error", job=getattr(trace.local, "job", None),
                          **details, error=type(exc).__name__)
                raise
            trace.log("saver_exit", job=getattr(trace.local, "job", None), **details)
            return result

        @functools.wraps(original_tool_run)
        def tool_run(tool, *args, **kwargs):
            task_id = kwargs.get("config", {}).get("configurable", {}).get("__pregel_task_id")
            try:
                result = original_tool_run(tool, *args, **kwargs)
            except BaseException as exc:
                trace.log("tool_error", tool_name=tool.name, task_id=task_id,
                          error=type(exc).__name__)
                raise
            trace.log("tool_return", tool_name=tool.name, task_id=task_id, result=result)
            return result

        BackgroundExecutor.submit = submit
        SqliteSaver.put_writes = put_writes
        StructuredTool._run = tool_run
        self.originals = (original_submit, original_writes, original_tool_run)
        self.log("installed")

    def restore(self):
        from langgraph.pregel._executor import BackgroundExecutor
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langchain_core.tools import StructuredTool
        BackgroundExecutor.submit, SqliteSaver.put_writes, StructuredTool._run = self.originals
        self.sample()
        self.log("restored")
