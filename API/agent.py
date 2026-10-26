"""API version of the agent: wires the hand-written harness pieces in API/harness/ around the raw Messages API."""
from pathlib import Path

import anthropic

from API.harness import caching, loop
from API.harness.compaction import Compactor
from API.harness.context import ContextBuilder
from API.harness.history import History
from API.harness.memory import Memory
from API.harness.tokens import TokenMeter
from API.harness.tools import ToolRegistry
from shared.calendar_api import israel_holidays
from shared.planner import StudyPlanner
from shared.specs import EFFORT, MODEL, SYSTEM_PROMPT

API_NOTE = ("\n\nUser messages may start with a <context> block (today's date, relevant saved memories, a one-line "
            "plan summary) and, after a compaction, a <conversation_summary>. Treat both as facts, not as the user's words.")
# Server-side refusal fallback, on by default for Claude Opus 5.5. A study planner should never trigger it;
# the served model is printed on every call so a fallback would be visible.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def log(msg):
    print(f"[agent.py] {msg}")


class ApiAgent:
    def __init__(self, state_dir: Path, today: str, compaction_threshold: int = 50_000,
                 client=None, conversation_id: str | None = None):
        self.client = client or anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        planner = StudyPlanner(Path(state_dir) / "study.json", today)
        self.memory = Memory(state_dir)
        self.history = History(state_dir, conversation_id)
        self.context = ContextBuilder(self.memory, planner, today)
        self.tools = ToolRegistry({
            "add_exam": planner.add_exam, "schedule_study": planner.schedule_study, "list_plan": planner.list_plan,
            "israel_holidays": israel_holidays, "remember": self.memory.remember, "recall": self.memory.recall})
        self.meter = TokenMeter(MODEL)
        self.compactor = Compactor(compaction_threshold)
        # Frozen for the whole conversation: same system + tools on every call keeps the cache (and thinking) valid.
        self.params = dict(model=MODEL, max_tokens=16000, system=caching.system_blocks(SYSTEM_PROMPT + API_NOTE),
                           tools=self.tools.schemas, output_config={"effort": EFFORT},
                           betas=[FALLBACK_BETA], fallbacks="default")
        log(f"ready: model={MODEL} effort={EFFORT} tools={len(self.tools.schemas)} conversation={self.history.id}")

    def _create(self, **request):
        return self.client.beta.messages.create(**request)

    def _call_model(self, messages: list[dict]):
        response = self._create(**self.params, messages=caching.with_message_breakpoint(messages))
        self.meter.record(response.usage, f"model call ({response.model})")
        return response

    def ask(self, text: str) -> dict:
        self.meter.start_turn()
        self.tools.calls = []
        summary = self.history.pending_summary
        if self.history.messages and self.compactor.needed(self.meter.last_context_tokens):
            summary = self.compactor.summarize(self._create, self.params, self.history.messages, self.meter)
            self.history.compact(summary)
            self.context.reset()
        self.history.pending_summary = None
        self.history.append({"role": "user", "content": self.context.user_content(text, summary)})

        response, _ = loop.run(self._call_model, self.history, self.tools)
        answer = "\n".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "refusal":
            answer = answer or "[refusal]"
        turn = self.meter.end_turn()
        return {"answer": answer,
                "tokens": {f: turn[f] for f in ("input", "cache_read", "cache_write", "output")},
                "model_calls": turn["model_calls"], "cost_usd": turn["cost_usd"],
                "tools": list(self.tools.calls), "compacted": summary is not None}
