"""The API agent through the real `anthropic` SDK, with a mock HTTP transport: checks the JSON that goes on the wire."""
import json

import anthropic
import httpx2

from API.agent import ApiAgent

USAGE = {"input_tokens": 50, "output_tokens": 30, "cache_read_input_tokens": 1500,
         "cache_creation_input_tokens": 200, "cache_creation": {"ephemeral_5m_input_tokens": 200,
                                                                "ephemeral_1h_input_tokens": 0}}


def message(content, stop_reason):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": content, "stop_reason": stop_reason, "stop_sequence": None, "usage": USAGE}


def test_requests_and_responses_round_trip_through_the_real_sdk(tmp_path):
    replies = [
        message([{"type": "thinking", "thinking": "", "signature": "sig-abc"},
                 {"type": "tool_use", "id": "toolu_1", "name": "add_exam",
                  "input": {"course": "Algebra", "date": "2027-05-02"}},
                 {"type": "tool_use", "id": "toolu_2", "name": "add_exam",
                  "input": {"course": "Algebra", "date": "not-a-date"}}], "tool_use"),
        message([{"type": "text", "text": "הוספתי"}], "end_turn"),
    ]
    sent = []

    def handler(request):
        sent.append((request.headers, json.loads(request.content)))
        return httpx2.Response(200, json=replies.pop(0))

    client = anthropic.Anthropic(api_key="test-not-a-real-key",
                                 http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    turn = ApiAgent(tmp_path, "2027-03-14", client=client).ask("add the exam")

    assert turn["answer"] == "הוספתי" and turn["model_calls"] == 2 and turn["tools"] == ["add_exam", "add_exam"]
    assert turn["tokens"] == {"input": 100, "cache_read": 3000, "cache_write": 400, "output": 60}
    headers, first = sent[0]
    assert "server-side-fallback-2026-07-01" in headers["anthropic-beta"]
    assert first["fallbacks"] == "default" and first["output_config"] == {"effort": "medium"}
    assert "thinking" not in first  # Opus 5.5: adaptive thinking is on by default
    _, second = sent[1]
    assistant, results = second["messages"][1], second["messages"][2]
    assert assistant["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig-abc"}  # unchanged
    assert [r["tool_use_id"] for r in results["content"]] == ["toolu_1", "toolu_2"]  # one message
    assert results["content"][1]["is_error"] is True
    assert results["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert second["system"] == first["system"] and second["tools"] == first["tools"]  # frozen prefix
