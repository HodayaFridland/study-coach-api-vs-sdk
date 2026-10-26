"""SDK tools: the same shared domain functions, wrapped with @tool and served in-process by an SDK MCP server."""
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from shared.calendar_api import israel_holidays
from shared.memory_store import MemoryStore
from shared.planner import StudyPlanner
from shared.specs import TOOL_SPECS

SERVER = "study"
ALLOWED = [f"mcp__{SERVER}__{spec['name']}" for spec in TOOL_SPECS]  # replaces: tools.py
CLAUDE_MD = ("# Study Coach memory\n"
             "The user's saved preferences and decisions (written by the remember tool; newer values replace older).\n")


def build_server(workspace: Path, today: str):
    handlers = make_handlers(workspace, today)  # replaces: tools.py
    return create_sdk_mcp_server(SERVER, tools=[_wrap(s, handlers[s["name"]]) for s in TOOL_SPECS])  # replaces: tools.py


def make_handlers(workspace: Path, today: str) -> dict:
    planner = StudyPlanner(workspace / "study.json", today)
    memory = MemoryStore(workspace / "memory.json")  # replaces: memory.py

    def remember(key: str, value: str) -> str:  # replaces: memory.py
        result = memory.remember(key, value)  # replaces: memory.py
        lines = [f"- {k}: {e['value']}" for k, e in memory.all().items()]  # replaces: memory.py
        (workspace / "CLAUDE.md").write_text(CLAUDE_MD + "\n".join(lines) + "\n", encoding="utf-8")  # replaces: memory.py
        return result  # replaces: memory.py

    return {"add_exam": planner.add_exam, "schedule_study": planner.schedule_study,  # replaces: tools.py
            "list_plan": planner.list_plan, "israel_holidays": israel_holidays,  # replaces: tools.py
            "remember": remember, "recall": memory.recall}  # replaces: tools.py


def _wrap(spec: dict, fn):  # replaces: tools.py
    @tool(spec["name"], spec["description"], spec["input_schema"])  # replaces: tools.py
    async def handler(args: dict) -> dict:  # replaces: tools.py
        try:  # replaces: tools.py
            output, is_error = fn(**args), False  # replaces: tools.py
        except Exception as e:  # replaces: tools.py
            output, is_error = f"error: {e}", True  # replaces: tools.py
        print(f"[SDK/tools.py] {spec['name']}({args}) -> {'ERROR ' if is_error else ''}{output.splitlines()[0][:90]}")
        return {"content": [{"type": "text", "text": output}], "is_error": is_error}  # replaces: tools.py
    return handler  # replaces: tools.py
