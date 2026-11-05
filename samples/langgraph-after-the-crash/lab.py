"""Controlled hard-process-kill matrix and optional shared-executor probe."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid

from vacation import KINDS, OfflineVacationModel, disable_tracing, make_tools

CASES = {
    "A": ("factory", "beforeinvoke", None),
    "B": ("factory", "firstmodel", None),
    "C": ("factory", "pre", None), "D": ("factory", "post", None),
    "E": ("factory", "pre", 1), "F": ("factory", "post", 1),
    "G": ("aggregate", "pre", 1), "H": ("aggregate", "post", 1),
    "I": ("separate", "pre", 1), "J": ("separate", "post", 1),
    "K": ("functional", "pre", 8), "L": ("functional", "post", 8),
    "M": ("functional_parallel", "pre", 8),
    "R": ("factory", "pre", 1),
}
PINS = {"langchain": "1.3.14", "langgraph": "1.2.10", "langchain-core": "1.5.3",
        "langgraph-checkpoint": "4.3.0", "langgraph-checkpoint-sqlite": "3.1.2"}
TRACE = None


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    if hasattr(value, "model_dump"):
        return {"python_type": type(value).__name__, **value.model_dump(mode="json")}
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return {"python_type": type(value).__name__, "repr": repr(value)}


def dump(path, value):
    stage = path.with_suffix(path.suffix + ".writing")
    stage.write_text(json.dumps(encode(value), indent=2), encoding="utf-8")
    retry_io(lambda: stage.replace(path), path, "replace")


def read(path):
    return json.loads(retry_io(lambda: path.read_text(encoding="utf-8"), path, "read"))


def retry_io(action, path, operation):
    # Windows can briefly deny opens around an atomic rename. Do not retry
    # malformed JSON, other I/O failures, or permanently inaccessible files.
    for attempt in range(41):
        try:
            return action()
        except PermissionError as exc:
            if os.name != "nt" or attempt == 40:
                raise
            diagnostic = {"file": path.name, "operation": operation,
                          "attempt": attempt + 1, "pid": os.getpid(),
                          "errno": exc.errno, "winerror": getattr(exc, "winerror", None),
                          "monotonic_ns": time.monotonic_ns()}
            with (path.parent / f"io-retries-{os.getpid()}.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(diagnostic) + "\n")
            time.sleep(0.025)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connect(path):
    return sqlite3.connect(path, timeout=15, check_same_thread=False)


def events(where):
    with closing(connect(where / "bookings.sqlite")) as db:
        return [json.loads(r[0]) for r in db.execute("SELECT payload FROM events ORDER BY seq")]


def record(where, op, phase, attempt_id="", **extra):
    row = dict(op=op, phase=phase, attempt_id=attempt_id, pid=os.getpid(),
               thread_id=threading.get_ident(),
               monotonic_ns=time.monotonic_ns(), time_utc=now(),
               logical_key=f"{where.name}:{op}", **extra)
    with closing(connect(where / "bookings.sqlite")) as db, db:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("INSERT INTO events(payload) VALUES (?)", (json.dumps(row),))
        row["sequence"] = cursor.lastrowid
        if phase == "effect_committed":
            db.execute("INSERT INTO bookings(kind,attempt_id,logical_key,pid) VALUES (?,?,?,?)",
                       (op, attempt_id, row["logical_key"], os.getpid()))
        db.execute("UPDATE events SET payload=? WHERE seq=?", (json.dumps(row), row["sequence"]))
        # A separate fsynced ledger, serialized with the event transaction.
        with (where / "ledger.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(row) + "\n")
            file.flush()
            os.fsync(file.fileno())
    return row


def wait(predicate, processes=(), timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        for proc in processes:
            if proc.poll() is not None:
                raise RuntimeError(f"Owned child {proc.pid} exited {proc.returncode} before condition")
        time.sleep(0.03)
    raise TimeoutError(f"Condition not reached within nominal {timeout}s budget")


def gate(where, op, phase, aid):
    row = record(where, op, phase, aid)
    dump(where / "gate.json", row)
    end = time.monotonic() + 120
    while not (where / "release.json").exists():
        if TRACE is not None:
            TRACE.sample()
        if time.monotonic() > end:
            raise TimeoutError("Controller did not terminate or release owned worker")
        time.sleep(0.10)
    record(where, op, "released", aid)


def operation(where, spec, op):
    aid = uuid.uuid4().hex
    record(where, op, "entered", aid)
    first = op == "car" and not (where / "killed.json").exists()
    if first:
        wait(lambda: {"flight", "hotel"} <=
             {r["op"] for r in events(where) if r["phase"] == "return_ready"})
        if spec["window"] == "pre":
            gate(where, op, "GATE_PRE_EFFECT", aid)
    record(where, op, "effect_committed", aid)
    if first and spec["window"] == "post":
        gate(where, op, "GATE_POST_EFFECT_PRE_RETURN", aid)
    record(where, op, "return_ready", aid)
    return f"{op}-confirmed"


def config(spec):
    value = {"configurable": {"thread_id": spec["thread_id"], "checkpoint_ns": ""}}
    if spec["max_concurrency"] is not None:
        value["max_concurrency"] = spec["max_concurrency"]
    return value


def build(where, spec, checkpoint_path=None):
    from langchain.agents import create_agent
    from langchain_core.messages import HumanMessage, ToolMessage
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.func import entrypoint, task
    from langgraph.graph import START, END, MessagesState, StateGraph
    from langgraph.prebuilt import ToolNode
    db = connect(checkpoint_path or where / "checkpoints.sqlite")
    saver = SqliteSaver(db)
    tools = make_tools(where / "bookings.sqlite",
                       recorder=lambda _, op: operation(where, spec, op))

    class GatedModel(OfflineVacationModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            record(where, "model", "model_entered")
            if spec["window"] == "firstmodel" and not (where / "killed.json").exists():
                gate(where, "model", "GATE_FIRST_MODEL", "")
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    model = GatedModel()
    inputs = {"messages": [HumanMessage(content="Book my vacation.", id="request")]}
    if spec["shape"] == "factory":
        graph = create_agent(model=model, tools=tools, checkpointer=saver)
    elif spec["shape"].startswith("functional"):
        @task
        def book_flight_task():
            return operation(where, spec, "flight")

        @task
        def book_hotel_task():
            return operation(where, spec, "hotel")

        @task
        def book_car_task():
            return operation(where, spec, "car")

        @entrypoint(checkpointer=saver)
        def bookings(inputs):
            if spec["shape"] == "functional_parallel":
                futures = [book_flight_task(), book_hotel_task(), book_car_task()]
                return [f.result() for f in futures]
            return [book_flight_task().result(), book_hotel_task().result(),
                    book_car_task().result()]

        graph, inputs = bookings, {"request": "book all three"}
    else:
        builder = StateGraph(MessagesState)
        if spec["shape"] == "separate":
            previous = START
            for kind, tool_fn in zip(KINDS, tools):
                name = f"book_{kind}_node"

                def node(state, fn=tool_fn, op=kind):
                    return {"messages": [ToolMessage(content=fn.invoke({}),
                                                     tool_call_id=f"call-{op}")]}

                builder.add_node(name, node)
                builder.add_edge(previous, name)
                previous = name
            builder.add_edge(previous, END)
        else:
            builder.add_node("model", lambda state: {"messages": [model.invoke(state["messages"])]})
            builder.add_node("tools", ToolNode(tools))
            builder.add_edge(START, "model")
            builder.add_conditional_edges("model", lambda state:
                "tools" if state["messages"][-1].tool_calls else END,
                {"tools": "tools", END: END})
            builder.add_edge("tools", "model")
        graph = builder.compile(checkpointer=saver)
    return graph, saver, db, inputs


def snapshot(graph, saver, spec):
    state = graph.get_state(config(spec))
    cp = saver.get_tuple(config(spec))
    return encode({
        "values": state.values, "next": state.next, "metadata": state.metadata,
        "tasks": [{"id": t.id, "name": t.name, "path": t.path, "result": t.result,
                   "error": t.error, "interrupts": t.interrupts} for t in state.tasks],
        "saver_tuple": None if cp is None else {
            "metadata": cp.metadata, "checkpoint": cp.checkpoint,
            "pending_writes": [{"task_id": tid, "channel": ch, "value": v}
                               for tid, ch, v in cp.pending_writes]}})


def capture(where, spec, label):
    target = where / f"{label}.sqlite"
    if target.exists():
        raise FileExistsError(target)
    with closing(connect(where / "checkpoints.sqlite")) as src, closing(connect(target)) as dst:
        src.backup(dst)
    graph, saver, db, _ = build(where, spec, target)
    try:
        value = snapshot(graph, saver, spec)
        saver.setup()
        value["physical_writes"] = [
            {"thread_id": tid, "namespace": ns, "checkpoint_id": cid,
             "task_id": taskid, "idx": idx, "channel": channel, "type": typ,
             "payload": encode(saver.serde.loads_typed((typ, blob)))}
            for tid, ns, cid, taskid, idx, channel, typ, blob in db.execute(
                "SELECT thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,type,value "
                "FROM writes ORDER BY checkpoint_id,task_id,idx")]
        value["checkpoint_metadata"] = [encode(cp.metadata) for cp in saver.list(config(spec))]
        value["sqlite_integrity"] = db.execute("PRAGMA integrity_check").fetchone()[0]
        if value["sqlite_integrity"] != "ok":
            raise RuntimeError("Backup integrity failed")
        dump(where / f"{label}.json", value)
        return value
    finally:
        db.close()


def persisted(where, spec):
    from langgraph.checkpoint.sqlite import SqliteSaver
    with closing(connect(where / "checkpoints.sqlite")) as db:
        cp = SqliteSaver(db).get_tuple(config(spec))
        if cp is None:
            return False
        if spec["shape"] == "factory":
            found = {getattr(m, "tool_call_id", "") for _, ch, value in cp.pending_writes
                     if ch == "messages" for m in value}
            return {"call-flight", "call-hotel"} <= found
        if spec["shape"].startswith("functional"):
            return {"flight-confirmed", "hotel-confirmed"} <= {
                v for _, ch, v in cp.pending_writes if ch == "__return__" and isinstance(v, str)}
        if spec["shape"] == "separate":
            return {"call-flight", "call-hotel"} <= {
                getattr(m, "tool_call_id", "")
                for m in cp.checkpoint["channel_values"].get("messages", [])}
        return True


def worker(where, role):
    global TRACE
    spec = read(where / "spec.json")
    graph, saver, db, inputs = build(where, spec)
    if spec["instrument"]:
        from executor_trace import ExecutorTrace
        TRACE = ExecutorTrace(where / f"{role}-trace.jsonl")
        TRACE.install()
    try:
        dump(where / f"{role}-ready.json", {
            "pid": os.getpid(), "state": snapshot(graph, saver, spec),
            "nodes": sorted(graph.get_graph().nodes), "config": config(spec)})
        if role == "original" and spec["window"] == "beforeinvoke":
            gate(where, "bootstrap", "GATE_BEFORE_INVOKE", "")
        if role == "replacement":
            wait(lambda: (where / "recover.json").exists(), timeout=120)
            dump(where / "before-explicit-invoke.json", snapshot(graph, saver, spec))
        actual_input = inputs if role == "original" else None
        record(where, "invocation", "invoke_begin", role=role,
               input_kind="original_input" if role == "original" else "None")
        try:
            result = graph.invoke(actual_input, config(spec))
            outcome = {"error": None, "result": encode(result)}
        except Exception as exc:
            outcome = {"error": type(exc).__name__, "message": str(exc),
                       "traceback": traceback.format_exc()}
        record(where, "invocation", "invoke_end", role=role, error=outcome["error"])
        outcome.update(pid=os.getpid(), state=snapshot(graph, saver, spec))
        dump(where / f"{role}-result.json", outcome)
    finally:
        if TRACE is not None:
            TRACE.restore()
        db.close()


def launch_environment():
    import langchain
    site = str(Path(langchain.__file__).resolve().parent.parent)
    direct = str(Path(sys._base_executable).resolve())
    constraints = {}
    for line in (Path(__file__).resolve().parent / "constraints.txt").read_text(
            encoding="utf-8").splitlines():
        package, version = line.split("==")
        installed = md.version(package)
        check(installed == version, f"Constraint mismatch: {package} expected {version}, got {installed}")
        constraints[package] = installed
    return {"direct_base_executable": direct, "site_packages": site,
            "python": sys.version, "versions": {p: md.version(p) for p in PINS},
            "constraint_versions": constraints}


def spawn(where, role, environment):
    env = dict(os.environ, PYTHONPATH=environment["site_packages"],
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    output = (where / f"{role}.log").open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [environment["direct_base_executable"], "-S", "-B", str(Path(__file__).resolve()),
             "--worker", role, "--output", str(where)], cwd=Path(__file__).resolve().parent,
            env=env, stdout=output, stderr=subprocess.STDOUT)
    except BaseException:
        output.close()
        raise
    proc.owned_log = output
    return proc


def reap(proc):
    if proc.poll() is None:
        proc.kill()
    code = proc.wait(timeout=20)
    proc.owned_log.close()
    return code


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def vectors(where):
    rows = events(where)
    attempts = [sum(r["phase"] == "entered" and r["op"] == op for r in rows) for op in KINDS]
    with closing(connect(where / "bookings.sqlite")) as db:
        bookings = [dict(zip(("id", "kind", "attempt_id", "logical_key", "pid"), row))
                    for row in db.execute("SELECT * FROM bookings ORDER BY id")]
    effects = [sum(b["kind"] == op for b in bookings) for op in KINDS]
    check(effects == [sum(r["phase"] == "effect_committed" and r["op"] == op for r in rows)
                      for op in KINDS], "Actual booking rows disagree with event counts")
    ledger = [json.loads(line) for line in (where / "ledger.jsonl").read_text(
        encoding="utf-8").splitlines()]
    check(rows == ledger, "SQLite events and independent ledger disagree")
    return attempts, effects, bookings


def validate_trace(where, spec, before, released=False):
    rows = [json.loads(line) for line in (where / "original-trace.jsonl").read_text(
        encoding="utf-8").splitlines()]
    submits = [r for r in rows if r["event"] == "submit"]
    latest = before["saver_tuple"]["checkpoint"]["id"]
    jobs = {}
    for call in ("call-flight", "call-hotel"):
        match = [r for r in submits if call in r.get("tool_call_ids", [])
                 and r["function"].endswith("SqliteSaver.put_writes")
                 and r.get("checkpoint_id") == latest]
        check(len(match) == 1, f"Expected exactly one {call} latest-checkpoint saver submission")
        jobs[call] = match[0]
    car = [r for r in submits if r["function"].endswith("run_with_retry")
           and "call-car" in r.get("tool_call_ids", [])]
    check(len(car) == 1, "Missing distinct car executor task")
    car = car[0]
    for call, job in jobs.items():
        check(job["executor_id"] == car["executor_id"] and job["pool_id"] == car["pool_id"],
              "Saver and car did not share the executor/pool")
        task = [r for r in submits if r.get("task_id") == job["task_id"]
                and r["function"].endswith("run_with_retry")]
        check(len(task) == 1 and any(r["event"] == "finish" and r["job"] == task[0]["job"]
                                    for r in rows), "Sibling execution never returned")
        check(any(r["event"] == "tool_return" and r.get("task_id") == job["task_id"]
                  and r["result"] == call.removeprefix("call-") + "-confirmed" for r in rows),
              "Tool function return not directly observed")
        if spec["max_concurrency"] == 1:
            check(job["max_workers"] == 1, "Not a single-slot executor")
            samples = [r for r in rows if r["event"] == "future_sample"
                       and r.get("job") == job["job"] and not r["started"]
                       and not r["running"] and not r["done"]]
            check(samples, "No actual queued sibling saver future observed")
            boundary = read(where / "observation-boundary.json")["monotonic_ns"]
            check(not any(r["event"] == "saver_enter" and r.get("job") == job["job"]
                          and r["monotonic_ns"] < boundary for r in rows),
                  "Saver started before held observation boundary")
            check(any(r["event"] == "future_sample" and r.get("job") == car["job"]
                      and r["running"] and not r["done"]
                      and r["monotonic_ns"] < boundary for r in rows),
                  "Car future not observed running")
        if released or spec["max_concurrency"] is None:
            check(any(r["event"] == "saver_exit" and r.get("job") == job["job"] for r in rows),
                  "Queued saver did not drain")
    return {"sibling_saver_jobs": jobs, "car_job": car,
            "events": len(rows), "release_drained": released,
            "logging_cost_samples": [r for r in rows if r["event"] == "logging_cost"]}


def expected(spec):
    case = spec["case"]
    if case == "A":
        return [0, 0, 0], [0, 0, 0]
    if case in ("B", "R"):
        return [1, 1, 1], [1, 1, 1]
    serial_or_aggregate = case in "EFGH"
    attempts = [2, 2, 2] if serial_or_aggregate else [1, 1, 2]
    effects = [2, 2, 1] if serial_or_aggregate else [1, 1, 1]
    if spec["window"] == "post":
        effects[-1] = 2
    return attempts, effects


def validate_window(spec, before):
    case = spec["case"]
    cp = before["saver_tuple"]
    if case == "A":
        check(cp is None and not before["tasks"], "Unused thread unexpectedly has state")
        return
    expected_step = (0 if case == "B" else 2 if spec["shape"] == "separate" else
                     -1 if spec["shape"].startswith("functional") else 1)
    check(cp["metadata"]["step"] == expected_step, "Unexpected latest checkpoint step")
    check(cp["metadata"]["source"] == ("input" if expected_step == -1 else "loop"),
          "Unexpected checkpoint source")
    tasks = before["tasks"]
    if spec["shape"] == "factory" and spec["window"] in ("pre", "post"):
        check(len(tasks) == 3 and len({t["id"] for t in tasks}) == 3 and
              all(t["name"] == "tools" for t in tasks), "Not three distinct factory tools tasks")
        result_count = sum(t["result"] is not None for t in tasks)
        if spec["max_concurrency"] == 1:
            check(result_count == 0 and not cp["pending_writes"],
                  "Serialized results unexpectedly persisted in this selected window")
        else:
            check(result_count == 2, "Default factory lacks two saved task results")
            check(sum(w["channel"] == "messages" for w in cp["pending_writes"]) == 2,
                  "Default factory lacks two actual messages writes")
    elif spec["shape"] == "aggregate":
        check(len(tasks) == 1 and tasks[0]["result"] is None and not cp["pending_writes"],
              "Aggregate graph unexpectedly saved partial tool task results")
    elif spec["shape"].startswith("functional"):
        check(sum(w["channel"] == "__return__" for w in cp["pending_writes"]) == 2,
              "Missing native task return values")
    elif spec["shape"] == "separate":
        check(before["next"] == ["book_car_node"], "Separate-node continuation differs")
    if case == "B":
        check(before["next"] == ["model"], "First model not pending")


def run_case(root, spec, environment):
    where = root / spec["run_id"]
    where.mkdir()
    dump(where / "spec.json", spec)
    with closing(connect(where / "bookings.sqlite")) as db, db:
        db.execute("CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,payload TEXT NOT NULL)")
        db.execute("CREATE TABLE bookings(id INTEGER PRIMARY KEY,kind TEXT,attempt_id TEXT,logical_key TEXT,pid INTEGER)")
    receipt = {"spec": spec, "passed": False, "started_utc": now()}
    owned = []
    try:
        first = spawn(where, "original", environment)
        owned.append(first)
        ready = wait(lambda: read(where / "original-ready.json")
                     if (where / "original-ready.json").exists() else None, [first])
        selected_gate = wait(lambda: read(where / "gate.json")
                             if (where / "gate.json").exists() else None, [first])
        check(first.pid == ready["pid"] == selected_gate["pid"], "Launch/gate PID identity mismatch")
        receipt.update(original_pid=first.pid, gate=selected_gate, original_ready=ready)
        if spec["window"] in ("pre", "post"):
            if spec["shape"] == "factory" and spec["max_concurrency"] == 1:
                checks = []
                begin = time.monotonic_ns()
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline:
                    checks.append({"monotonic_ns": time.monotonic_ns(),
                                   "siblings_persisted": persisted(where, spec)})
                    check(first.poll() is None, "Original died during storage observation")
                    time.sleep(0.05)
                receipt["storage_observation"] = {
                    "nominal_budget_seconds": 1.0, "actual_elapsed_seconds":
                    (time.monotonic_ns() - begin) / 1e9, "samples": checks}
            elif spec["shape"] != "aggregate":
                wait(lambda: persisted(where, spec), [first])
        before = capture(where, spec, "before")
        dump(where / "observation-boundary.json", {"monotonic_ns": time.monotonic_ns()})
        receipt["before"] = before
        validate_window(spec, before)
        if spec["case"] == "R":
            dump(where / "release.json", {"monotonic_ns": time.monotonic_ns()})
            outcome = wait(lambda: read(where / "original-result.json")
                           if (where / "original-result.json").exists() else None, [first])
            check(first.wait(timeout=20) == 0, "Release worker failed")
            check(outcome["error"] is None, "Release invoke raised")
            receipt["outcome"] = outcome
        else:
            receipt["kill_requested_monotonic_ns"] = time.monotonic_ns()
            code = reap(first)
            check(code != 0, "Expected abnormal hard-kill exit")
            receipt.update(killed_pid=first.pid, killed_exit_code=code,
                           terminated_monotonic_ns=time.monotonic_ns())
            dump(where / "killed.json", {"pid": first.pid, "exit_code": code})
            after = capture(where, spec, "after-kill")
            check(before == after, "Storage changed across kill")
            replacement = spawn(where, "replacement", environment)
            owned.append(replacement)
            ready2 = wait(lambda: read(where / "replacement-ready.json")
                          if (where / "replacement-ready.json").exists() else None, [replacement])
            check(replacement.pid == ready2["pid"] != first.pid, "Replacement PID mismatch")
            check(ready2["state"] == {k: before[k] for k in ready2["state"]},
                  "Replacement state differs before invocation")
            rows_before = events(where)
            start = time.monotonic()
            time.sleep(1.0)
            rows_after = events(where)
            receipt["idle"] = {"actual_seconds": time.monotonic() - start,
                               "events_before": len(rows_before), "events_after": len(rows_after)}
            check(rows_before == rows_after, "Unexpected work during idle interval")
            dump(where / "recover.json", {"input": None, "owner": "controller"})
            outcome = wait(lambda: read(where / "replacement-result.json")
                           if (where / "replacement-result.json").exists() else None, [replacement])
            check(replacement.wait(timeout=20) == 0, "Replacement worker failed")
            check(outcome["error"] == ("EmptyInputError" if spec["case"] == "A" else None),
                  f"Unexpected recovery result: {outcome.get('error')}")
            receipt.update(replacement_pid=replacement.pid, outcome=outcome)
        receipt["final"] = capture(where, spec, "final")
        if spec["case"] != "A":
            check(not receipt["final"]["next"], "Completed run still has pending work")
            values = receipt["final"]["values"]
            if spec["shape"].startswith("functional"):
                check(values == [f"{op}-confirmed" for op in KINDS], "Final native returns differ")
            else:
                check({m.get("tool_call_id") for m in values["messages"]
                       if m.get("tool_call_id")} == {f"call-{op}" for op in KINDS},
                      "Final persisted state lacks booking results")
        attempts, effects, bookings = vectors(where)
        receipt.update(attempt_vector=attempts, effect_vector=effects, bookings=bookings)
        check((attempts, effects) == expected(spec), "Observed vectors differ from historical expectations")
        rows = events(where)
        invocations = [(r["pid"], r["input_kind"]) for r in rows if r["phase"] == "invoke_begin"]
        wanted = ([(first.pid, "original_input")] if spec["case"] == "R" else
                  ([(first.pid, "original_input")] if spec["case"] != "A" else []) +
                  [(receipt["replacement_pid"], "None")])
        check(invocations == wanted, "Incorrect original/None invocation ownership")
        check(all(r["pid"] in {p.pid for p in owned} for r in rows), "Unowned worker event")
        if spec["case"] != "R":
            check(all(r["monotonic_ns"] < receipt["terminated_monotonic_ns"]
                      for r in rows if r["pid"] == first.pid), "Original event after termination")
        if spec["instrument"]:
            receipt["trace_verification"] = validate_trace(where, spec, before, spec["case"] == "R")
        receipt["passed"] = True
    except Exception as exc:
        receipt.update(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    finally:
        receipt["cleanup"] = [{"pid": p.pid, "exit_code": reap(p),
                               "reaped": p.poll() is not None} for p in owned]
        receipt["ended_utc"] = now()
        dump(where / "receipt.json", receipt)
    print(json.dumps({k: receipt.get(k) for k in
                      ("passed", "error", "attempt_vector", "effect_vector")} |
                     {"case": spec["run_id"]}), flush=True)
    return receipt


def main():
    disable_tracing()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suite", choices=("matrix", "probe"), default="matrix")
    parser.add_argument("--cases")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--repeat", type=int, help="Run just this repeat number")
    parser.add_argument("--worker", choices=("original", "replacement"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    where = args.output.resolve()
    if args.worker:
        worker(where, args.worker)
        return 0
    allowed = "ABCDEFGHIJKLM" if args.suite == "matrix" else "CDEFR"
    selected = args.cases or allowed
    if not selected or len(set(selected)) != len(selected) or set(selected) - set(allowed):
        parser.error(f"--cases must contain unique letters from {allowed}")
    if args.repeats < 1 or (args.repeat is not None and args.repeat < 1):
        parser.error("Repeat counts/numbers must be positive")
    environment = launch_environment()
    check(environment["versions"] == PINS, "Pinned package versions differ; use requirements.txt")
    where.mkdir(parents=True, exist_ok=False)
    dump(where / "environment.json", environment)
    dump(where / "source-hashes.json", {p.name: digest(p) for p in
         Path(__file__).resolve().parent.iterdir() if p.is_file()})
    receipts = []
    repeats = [args.repeat] if args.repeat is not None else range(1, args.repeats + 1)
    for case in selected:
        shape, window, concurrency = CASES[case]
        for repeat in repeats:
            spec = {"case": case, "run_id": f"{case}-{repeat:02d}", "repeat": repeat,
                    "shape": shape, "window": window, "max_concurrency": concurrency,
                    "thread_id": uuid.uuid4().hex, "instrument": args.suite == "probe"}
            receipts.append(run_case(where, spec, environment))
    summary = {"suite": args.suite, "planned": len(selected) * len(repeats),
               "passed": sum(r["passed"] for r in receipts),
               "failed": [r["spec"]["run_id"] for r in receipts if not r["passed"]],
               "cases": [{"case": r["spec"]["run_id"], "passed": r["passed"],
                          "attempts": r.get("attempt_vector"), "effects": r.get("effect_vector"),
                          "error": r.get("error"), "outcome": r.get("outcome", {}).get("error")}
                         for r in receipts]}
    dump(where / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if all(r["passed"] for r in receipts) else 1


if __name__ == "__main__":
    sys.exit(main())
