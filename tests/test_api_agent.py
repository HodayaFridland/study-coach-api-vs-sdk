"""The whole API agent with a fake client: two sessions, memory across instances, compaction."""
from fakes import FakeClient, response, text, tool_use, usage

from API.agent import ApiAgent


def test_memory_survives_a_new_agent_instance(tmp_path):
    client = FakeClient([
        response(tool_use("remember", {"key": "preferred_study_time", "value": "evening"}, "t1"),
                 stop_reason="tool_use"),
        response(text("שמרתי")),
        response(text("בערב")),
    ])
    first = ApiAgent(tmp_path, "2027-03-14", client=client)
    turn = first.ask("תזכור: ערב")
    assert turn["tools"] == ["remember"] and turn["model_calls"] == 2 and turn["answer"] == "שמרתי"

    second = ApiAgent(tmp_path, "2027-03-14", client=client)  # session 2: new instance, new conversation
    assert second.history.id != first.history.id
    assert second.ask("מתי אני לומד?")["answer"] == "בערב"
    context = client.requests[-1]["messages"][-1]["content"][0]["text"]
    assert "preferred_study_time: evening" in context


def test_every_request_has_the_same_cached_prefix_and_settings(tmp_path):
    client = FakeClient([response(tool_use("list_plan", {}, "t1"), stop_reason="tool_use"), response(text("ok"))])
    ApiAgent(tmp_path, "2027-03-14", client=client).ask("show plan")
    first, second = client.requests
    for key in ("system", "tools", "model", "output_config", "betas", "fallbacks"):
        assert first[key] == second[key]
    assert first["model"] == "claude-opus-5-5" and first["output_config"] == {"effort": "medium"}
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert second["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert len(first["tools"]) == 6


def test_compaction_replaces_the_transcript_with_a_summary(tmp_path):
    client = FakeClient([
        response(text("first answer"), u=usage(input_tokens=500)),
        response(text("SUMMARY: exams saved")),  # the compaction call
        response(text("second answer")),
    ])
    agent = ApiAgent(tmp_path, "2027-03-14", compaction_threshold=300, client=client)
    assert agent.ask("one")["compacted"] is False
    turn = agent.ask("two")
    assert turn["compacted"] is True and turn["model_calls"] == 2
    assert client.requests[1]["tool_choice"] == {"type": "none"}
    new_messages = client.requests[2]["messages"]
    assert len(new_messages) == 1  # only summary + new turn, nothing replayed
    assert "SUMMARY: exams saved" in new_messages[0]["content"][0]["text"]
    assert "compaction" in agent.history.path.read_text(encoding="utf-8")
