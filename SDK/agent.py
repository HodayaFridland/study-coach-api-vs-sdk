"""SDK version of the agent: Claude Code runs the harness (loop, history, caching, compaction); we configure it."""
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, ToolUseBlock

from SDK import tools
from shared.specs import EFFORT, MODEL, SYSTEM_PROMPT

SDK_NOTE = ("\n\nToday is {today}. Saved memories are in CLAUDE.md, loaded automatically when the session starts; "
            "use recall to search them.")

# replaces: compaction.py - nothing to write, Claude Code compacts on its own near the context limit
# replaces: caching.py - nothing to write, Claude Code places the cache_control breakpoints itself


def build_options(workspace: Path, today: str, resume: str | None = None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        effort=EFFORT,
        system_prompt=SYSTEM_PROMPT + SDK_NOTE.format(today=today),  # replaces: context.py
        setting_sources=["project"],  # replaces: memory.py, context.py (loads workspace/CLAUDE.md)
        cwd=str(workspace),  # replaces: memory.py
        mcp_servers={tools.SERVER: tools.build_server(workspace, today)},  # replaces: tools.py
        tools=[],  # no built-in tools: the only tools are our 6
        allowed_tools=tools.ALLOWED,  # replaces: tools.py
        permission_mode="dontAsk",  # anything not allowed is denied, never prompted
        strict_mcp_config=True,  # ignore every other MCP config on this machine
        resume=resume,  # replaces: history.py
    )


class SdkAgent:
    def __init__(self, workspace: Path, today: str, resume: str | None = None):
        self.client = ClaudeSDKClient(options=build_options(workspace, today, resume))
        self.session_id = resume
        self.session_cost = 0.0
        self.model_usage = {}

    async def __aenter__(self):
        await self.client.connect()
        return self

    async def __aexit__(self, *exc):
        await self.client.disconnect()

    async def ask(self, text: str) -> dict:
        await self.client.query(text)  # replaces: loop.py
        used, seen, calls, result = [], set(), set(), None
        async for message in self.client.receive_response():  # replaces: loop.py
            if isinstance(message, AssistantMessage):
                calls.add(message.message_id)
                for block in message.content:
                    if isinstance(block, ToolUseBlock) and block.id not in seen:
                        seen.add(block.id)
                        used.append(block.name.removeprefix(f"mcp__{tools.SERVER}__"))
            elif isinstance(message, ResultMessage):
                result = message
        usage = result.usage or {}  # replaces: tokens.py (summed over this turn's calls, main model only)
        total = result.total_cost_usd or 0.0  # replaces: tokens.py (cumulative for the session, all models)
        cost, self.session_cost = total - self.session_cost, total  # replaces: tokens.py
        before, self.model_usage = self.model_usage, result.model_usage or {}  # replaces: tokens.py
        self.session_id = result.session_id  # replaces: history.py
        return {
            "answer": (result.result or "").strip(),
            "tokens": {"input": usage.get("input_tokens", 0),  # replaces: tokens.py
                       "cache_read": usage.get("cache_read_input_tokens", 0),  # replaces: tokens.py
                       "cache_write": usage.get("cache_creation_input_tokens", 0),  # replaces: tokens.py
                       "output": usage.get("output_tokens", 0)},  # replaces: tokens.py
            "cache_write_1h": (usage.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0),
            "model_calls": len(calls),  # one AssistantMessage id per model call
            "side_model_calls": _side_models(before, self.model_usage),
            "cost_usd": round(cost, 6),
            "tools": used,
        }


def _side_models(before: dict, after: dict) -> dict:
    """Tokens Claude Code spent this turn on other models (e.g. a small model for housekeeping)."""
    side = {}
    for model, u in after.items():
        if model == MODEL:
            continue
        old = before.get(model, {})
        delta = {"input": u["inputTokens"] - old.get("inputTokens", 0),
                 "output": u["outputTokens"] - old.get("outputTokens", 0),
                 "cost_usd": round(u["costUSD"] - old.get("costUSD", 0), 6)}
        if delta["input"] or delta["output"]:
            side[model] = delta
    return side
