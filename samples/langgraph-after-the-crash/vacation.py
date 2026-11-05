"""Offline vacation agent: actual create_agent, fake bookings, explicit recovery."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver

KINDS = ("flight", "hotel", "car")
THREAD_CONFIG = {"configurable": {"thread_id": "vacation-001", "checkpoint_ns": ""}}
STORE_ID = {"sample": "offline-vacation-v1", "thread_id": "vacation-001"}


def disable_tracing():
    """Do not inherit optional hosted tracing from the caller."""
    for key in list(os.environ):
        if key.startswith(("LANGCHAIN_", "LANGSMITH_", "OTEL_")):
            del os.environ[key]
    os.environ.update(LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false",
                      OTEL_SDK_DISABLED="true")


class OfflineVacationModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "offline-scripted-vacation"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        names = {item.name for item in tools}
        if names != {f"book_{kind}" for kind in KINDS}:
            raise ValueError(f"Unexpected tools: {sorted(names)}")
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        results = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
        if results:
            if results != {f"call-{kind}" for kind in KINDS}:
                raise ValueError("The final model call requires all three results.")
            message = AIMessage(content="Vacation booked.", id="done")
        else:
            message = AIMessage(content="", id="plan", tool_calls=[
                {"name": f"book_{kind}", "args": {}, "id": f"call-{kind}",
                 "type": "tool_call"} for kind in KINDS])
        return ChatResult(generations=[ChatGeneration(message=message)])


def record_booking(booking_db: Path, kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"Unknown booking kind: {kind}")
    with closing(sqlite3.connect(booking_db, timeout=30)) as db, db:
        db.execute("INSERT INTO bookings(kind) VALUES (?)", (kind,))
    return f"{kind}-confirmed"


def make_tools(booking_db: Path, *, recorder=record_booking):
    @tool
    def book_flight() -> str:
        """Reserve the flight for this simulated vacation."""
        return recorder(booking_db, "flight")

    @tool
    def book_hotel() -> str:
        """Reserve a hotel room for this simulated vacation."""
        return recorder(booking_db, "hotel")

    @tool
    def book_car() -> str:
        """Reserve a rental car for this simulated vacation."""
        return recorder(booking_db, "car")

    return [book_flight, book_hotel, book_car]


def main():
    disable_tracing()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "resume"))
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    booking_db = data_dir / "bookings.sqlite"
    marker = data_dir / "sample.json"
    if args.action == "start":
        data_dir.mkdir(parents=True, exist_ok=False)
        with closing(sqlite3.connect(booking_db)) as db, db:
            db.execute("CREATE TABLE bookings(id INTEGER PRIMARY KEY,kind TEXT NOT NULL)")
        marker.write_text(json.dumps(STORE_ID), encoding="utf-8")
    else:
        if json.loads(marker.read_text(encoding="utf-8")) != STORE_ID:
            raise ValueError("This directory does not belong to this sample/thread.")
        if not booking_db.is_file() or not (data_dir / "checkpoints.sqlite").is_file():
            raise ValueError("Resume requires this sample's existing databases.")
    with SqliteSaver.from_conn_string(str(data_dir / "checkpoints.sqlite")) as saver:
        agent = create_agent(model=OfflineVacationModel(), tools=make_tools(booking_db),
                             checkpointer=saver)
        inputs = ({"messages": [HumanMessage(content="Book my vacation.", id="request")]}
                  if args.action == "start" else None)
        result = agent.invoke(inputs, THREAD_CONFIG)
        state = agent.get_state(THREAD_CONFIG)
        with closing(sqlite3.connect(booking_db)) as db:
            bookings = list(db.execute("SELECT id,kind FROM bookings ORDER BY id"))
        print(json.dumps({
            "pid": os.getpid(), "action": args.action, "bookings": bookings,
            "input_kind": "original_user_input" if inputs is not None else "None",
            "tool_results": [{"tool_call_id": m.tool_call_id, "content": m.content}
                             for m in result["messages"] if isinstance(m, ToolMessage)],
            "next": list(state.next), "nodes": sorted(agent.get_graph().nodes),
            "final_message": result["messages"][-1].content,
        }, indent=2))


if __name__ == "__main__":
    main()
