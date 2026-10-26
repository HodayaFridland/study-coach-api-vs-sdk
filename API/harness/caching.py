"""caching.py: where the cache_control breakpoints go. Prefix order is tools -> system -> messages."""
EPHEMERAL = {"type": "ephemeral"}  # 5-minute TTL: turns here start well under 5 minutes apart


def log(msg):
    print(f"[caching.py] {msg}")


def system_blocks(text: str) -> list[dict]:
    """Breakpoint 1: end of the system prompt, so tools + system (identical on every call) are cached."""
    return [{"type": "text", "text": text, "cache_control": EPHEMERAL}]


def with_message_breakpoint(messages: list[dict]) -> list[dict]:
    """Breakpoint 2: the last block of the last message, so the whole conversation so far is cached.
    Returns a copy; the stored history never contains cache_control."""
    if not messages:
        return messages
    last = dict(messages[-1])
    content = last["content"]
    content = [{"type": "text", "text": content}] if isinstance(content, str) else list(content)
    content[-1] = {**content[-1], "cache_control": EPHEMERAL}
    last["content"] = content
    log(f"breakpoints: system + messages[{len(messages) - 1}] ({content[-1]['type']})")
    return messages[:-1] + [last]
