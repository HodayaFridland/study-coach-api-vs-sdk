"""SDK tools and options, offline (no Claude Code process is started)."""
import asyncio

from SDK import tools
from SDK.agent import build_options
from shared import scenario as sc
from shared.specs import TOOL_SPECS


def _handler(name, fn):
    spec = next(s for s in TOOL_SPECS if s["name"] == name)
    return tools._wrap(spec, fn).handler


def test_tool_errors_are_returned_as_is_error():
    def broken(**_):
        raise ValueError("bad date")

    out = asyncio.run(_handler("add_exam", broken)({"course": "x", "date": "y"}))
    assert out == {"content": [{"type": "text", "text": "error: bad date"}], "is_error": True}


def test_remember_writes_claude_md_for_the_next_session(tmp_path):
    remember = tools.make_handlers(tmp_path, "2027-03-14")["remember"]
    assert not (tmp_path / "CLAUDE.md").exists()
    remember("preferred_study_time", "evening")
    remember("preferred_study_time", "morning")
    md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "- preferred_study_time: morning" in md and "evening" not in md
    assert sc.snapshot(tmp_path)["memory"]["preferred_study_time"]["previous"] == ["evening"]


def test_server_exposes_all_six_tools(tmp_path):
    server = tools.build_server(tmp_path, "2027-03-14")
    assert server["type"] == "sdk" and server["name"] == "study"


def test_options_are_restricted_and_match_the_api_version(tmp_path):
    options = build_options(tmp_path, "2027-03-14")
    assert options.model == "claude-opus-5-5" and options.effort == "medium"
    assert options.tools == [] and options.strict_mcp_config is True
    assert options.setting_sources == ["project"] and options.permission_mode == "dontAsk"
    assert options.allowed_tools == [f"mcp__study__{s['name']}" for s in TOOL_SPECS]
    assert "2027-03-14" in options.system_prompt and options.resume is None


def test_every_replaced_api_file_is_tagged_in_the_sdk():
    counts = sc.count_replaces([sc.ROOT / "SDK" / f for f in ("agent.py", "tools.py", "main.py")])
    for name in ("loop.py", "tools.py", "history.py", "memory.py", "context.py", "tokens.py"):
        assert counts.get(name, 0) > 0, name
    assert "compaction.py" not in counts and "caching.py" not in counts  # automatic: only comments
    assert set(counts) <= {"loop.py", "tools.py", "history.py", "memory.py", "context.py", "tokens.py"}
