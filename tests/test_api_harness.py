"""Each API harness file on its own, with a fake model."""
import json
from types import SimpleNamespace

from fakes import response, text, tool_use, usage

from API.harness import caching, loop
from API.harness.context import ContextBuilder
from API.harness.history import History
from API.harness.memory import Memory
from API.harness.tokens import TokenMeter
from API.harness.tools import ToolRegistry
from shared.planner import StudyPlanner, ToolError


def test_loop_runs_while_tool_use_and_sends_all_results_in_one_message(tmp_path):
    history = History(tmp_path)
    history.append({"role": "user", "content": "add two exams"})
    scripted = [response(tool_use("ok", {}, "t1"), tool_use("missing", {}, "t2"), stop_reason="tool_use"),
                response(text("done"))]
    seen = []

    def call_model(messages):
        seen.append(len(messages))
        return scripted.pop(0)

    final, calls = loop.run(call_model, history, ToolRegistry({"ok": lambda: "fine"}))
    assert calls == 2 and final.stop_reason == "end_turn"
    roles = [m["role"] for m in history.messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    results = history.messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]  # both in ONE user message
    assert "is_error" not in results[0] and results[1]["is_error"] is True


def test_tool_errors_go_back_to_the_model_as_is_error():
    def broken(**_):
        raise ToolError("date must be YYYY-MM-DD")

    registry = ToolRegistry({"add_exam": broken, "list_plan": lambda: "x" * 5000})
    err = registry.execute(SimpleNamespace(name="add_exam", input={"date": "soon"}, id="a"))
    assert err == {"type": "tool_result", "tool_use_id": "a", "content": "error: date must be YYYY-MM-DD",
                   "is_error": True}
    bad_args = registry.execute(SimpleNamespace(name="list_plan", input={"nope": 1}, id="b"))
    assert bad_args["is_error"] and "bad arguments" in bad_args["content"]
    long = registry.execute(SimpleNamespace(name="list_plan", input={}, id="c"))
    assert len(long["content"]) < 1600 and "truncated" in long["content"]
    assert [s["name"] for s in registry.schemas] == ["add_exam", "schedule_study", "list_plan",
                                                     "israel_holidays", "remember", "recall"]


def test_history_is_append_only_and_replays_after_compaction(tmp_path):
    h = History(tmp_path, "conv-test")
    h.append({"role": "user", "content": "1"})
    h.append({"role": "assistant", "content": "2"})
    h.compact("summary of 1 and 2")
    assert History(tmp_path, "conv-test").pending_summary == "summary of 1 and 2"
    h.append({"role": "user", "content": "3"})
    lines = h.path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["type"] for line in lines] == ["message", "message", "compaction", "message"]
    resumed = History(tmp_path, "conv-test")
    assert resumed.messages == [{"role": "user", "content": "3"}] and resumed.pending_summary is None
    assert History.latest_id(tmp_path) == "conv-test"


def test_cache_breakpoints_are_added_to_a_copy_only():
    messages = [{"role": "user", "content": "hi"},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}]
    sent = caching.with_message_breakpoint(messages)
    assert sent[-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in messages[-1]["content"][-1]
    assert caching.system_blocks("S")[0]["cache_control"] == {"type": "ephemeral"}


def test_token_cost_per_turn():
    meter = TokenMeter("claude-opus-5-5")
    meter.start_turn()
    meter.record(usage(input_tokens=1000, output_tokens=100, cache_read=10_000, cache_write=2000))
    meter.record(usage(input_tokens=0, output_tokens=0))
    turn = meter.end_turn()
    # 1000*$4 + 100*$20 + 10000*$0.20 + 2000*$5, per million
    assert turn["cost_usd"] == 0.018 and turn["model_calls"] == 2 and turn["cache_read"] == 10_000


def test_memory_retrieval_returns_only_the_relevant_entries(tmp_path):
    memory = Memory(tmp_path)
    for i in range(6):
        memory.remember(f"note_{i}", f"unrelated fact {i}")
    memory.remember("preferred_study_time", "evening")
    top = memory.relevant("what study time do I prefer?", k=2)
    assert top[0] == ("preferred_study_time", "evening") and len(top) == 2


def test_context_sends_each_fact_once_and_never_the_full_plan(tmp_path):
    memory = Memory(tmp_path)
    memory.remember("preferred_study_time", "evening")
    planner = StudyPlanner(tmp_path / "study.json", "2027-03-14")
    planner.add_exam("Algebra", "2027-05-02")
    ctx = ContextBuilder(memory, planner, "2027-03-14")
    first = ctx.user_content("hello")
    assert "today: 2027-03-14" in first[0]["text"] and "preferred_study_time: evening" in first[0]["text"]
    assert "1 exams" in first[0]["text"] and "EXAM" not in first[0]["text"]
    assert ctx.user_content("again") == [{"type": "text", "text": "again"}]  # nothing new -> nothing added
    planner.schedule_study("Algebra", "2027-04-18", "19:00", 60)
    assert "1 sessions" in ctx.user_content("and now?")[0]["text"]
    ctx.reset()
    assert len(ctx.user_content("after compaction", summary="S")) == 3
