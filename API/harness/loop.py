"""loop.py: the agent loop. It runs while stop_reason == "tool_use"; all tool_results go back in ONE user message."""
MAX_MODEL_CALLS = 12


def log(msg):
    print(f"[loop.py] {msg}")


def _as_dict(block) -> dict:
    # Thinking blocks are kept exactly as returned (with their signature): the history is append-only.
    return block.model_dump(mode="json", exclude_none=True)


def run(call_model, history, tools):
    def call():
        response = call_model(history.messages)
        history.append({"role": "assistant", "content": [_as_dict(b) for b in response.content]})
        return response

    response, calls = call(), 1
    while response.stop_reason == "tool_use":
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        log(f"call {calls}: stop_reason=tool_use -> {len(tool_uses)} tool(s): {[b.name for b in tool_uses]}")
        results = [tools.execute(b) for b in tool_uses]
        history.append({"role": "user", "content": results})  # one message with every tool_result
        if calls >= MAX_MODEL_CALLS:
            log(f"stopping: reached {MAX_MODEL_CALLS} model calls")
            break
        response, calls = call(), calls + 1
    log(f"call {calls}: stop_reason={response.stop_reason} -> turn done")
    return response, calls
