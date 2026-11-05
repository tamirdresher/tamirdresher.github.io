"""Small runtime smoke: factory start/resume plus negative and queued-write cases."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from lab import launch_environment, dump
from vacation import disable_tracing
import os


def wrapper_contract(root):
    from executor_trace import ExecutorTrace
    from langgraph.pregel._executor import BackgroundExecutor
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langchain_core.tools import tool
    trace = ExecutorTrace(root / "wrapper-contract.jsonl")
    trace.install()
    try:
        sentinel = ValueError("observable-test-exception")

        def raises():
            raise sentinel

        with BackgroundExecutor({"max_concurrency": 1}) as submit:
            value = object()
            future = submit(lambda argument, *, named: (argument, named), value, named=7)
            if future.result() != (value, 7):
                raise AssertionError("Submit arguments or return value changed")
            failed = submit(raises, __reraise_on_exit__=False)
            try:
                failed.result()
            except ValueError as exc:
                if exc is not sentinel:
                    raise AssertionError("Exception identity changed")
            else:
                raise AssertionError("Exception was hidden")
        with SqliteSaver.from_conn_string(":memory:") as saver:
            saver.put_writes(config={"configurable": {"thread_id": "contract",
                             "checkpoint_ns": "", "checkpoint_id": "checkpoint"}},
                             writes=[("contract", "value")], task_id="task")
            if saver.conn.execute("SELECT COUNT(*) FROM writes").fetchone()[0] != 1:
                raise AssertionError("Keyword saver write did not commit")

        @tool
        def checked_tool() -> str:
            """Test observational return forwarding."""
            return "checked"

        if checked_tool.invoke({}) != "checked":
            raise AssertionError("Tool return changed")
    finally:
        trace.restore()


def main():
    disable_tracing()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    wrapper_contract(root)
    source = Path(__file__).resolve().parent
    environment = launch_environment()
    env = dict(os.environ, PYTHONPATH=environment["site_packages"],
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    prefix = [environment["direct_base_executable"], "-S", "-B"]
    results = []
    for action in ("start", "resume"):
        command = prefix + [str(source / "vacation.py"), action,
                            "--data-dir", str(root / "vacation-data")]
        proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        dump(root / f"{action}-process.json", {
            "command": command, "exit_code": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr})
        proc.check_returncode()
        result = json.loads(proc.stdout)
        if (len(result["bookings"]) != 3 or result["next"] or
                result["final_message"] != "Vacation booked."):
            raise AssertionError("Unexpected factory sample result")
        results.append(result)
    if results[0]["bookings"] != results[1]["bookings"]:
        raise AssertionError("Completed-thread resume duplicated bookings")
    commands = [
        prefix + [str(source / "lab.py"), "--output", str(root / "negative"),
                  "--cases", "A", "--repeats", "1"],
        prefix + [str(source / "lab.py"), "--output", str(root / "queued"),
                  "--suite", "probe", "--cases", "ER", "--repeats", "1"],
    ]
    for number, command in enumerate(commands):
        proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=240)
        dump(root / f"lab-{number}.json", {"command": command, "exit_code": proc.returncode,
                                         "stdout": proc.stdout, "stderr": proc.stderr})
        proc.check_returncode()
    dump(root / "result.json", {"passed": True, "sample_runs": results})
    print("PASS: factory start/resume; empty-thread negative; serialized kill/release probe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
