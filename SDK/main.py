"""Runs the SDK version: `--scenario scenario.json --out results/sdk.json`, or `--chat` to talk to it."""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from SDK.agent import SdkAgent  # noqa: E402
from shared import scenario as sc  # noqa: E402

SDK_FILES = [ROOT / "SDK" / f for f in ("agent.py", "tools.py", "main.py")]


async def run_scenario(path: str, out: str) -> None:
    sc.log_next_to(out)
    scenario = sc.load(path)
    workspace = ROOT / "SDK" / "workspace" / "scenario"
    sc.clean_dir(workspace)
    turns, sessions, session_id = [], [], None
    for session in scenario["sessions"]:
        resume = session_id if session.get("resume_previous") else None
        print(f"\n=== session {session['id']}: new SdkAgent (new Claude Code process), state from disk ({workspace}) ===")
        async with SdkAgent(workspace, scenario["today"], resume) as agent:
            for text in session["turns"]:
                n = len(turns) + 1
                print(f"\n--- turn {n} (session {session['id']}) ---\nUSER: {text}")
                started = time.perf_counter()
                record = await agent.ask(text)
                record["seconds"] = round(time.perf_counter() - started, 2)
                t = record["tokens"]
                print(f"[SDK/agent.py] {record['model_calls']} calls, input={t['input']} cache_read={t['cache_read']} "
                      f"cache_write={t['cache_write']} output={t['output']} -> ${record['cost_usd']:.4f}")
                print(f"AGENT: {record['answer']}")
                turns.append({"session": session["id"], "turn": n, "user": text, **record,
                              "state": sc.snapshot(workspace)})
        session_id = agent.session_id
        sessions.append({"session": session["id"], "session_id": session_id, "model_usage": agent.model_usage})

    loc = sc.count_replaces(SDK_FILES)
    loc["SDK total (agent.py + tools.py + main.py)"] = sum(len(sc.code_lines(f)) for f in SDK_FILES)
    sc.write(out, sc.build_results("sdk", scenario, turns, loc, {"sessions": sessions}))


async def chat(resume: bool) -> None:
    workspace = ROOT / "SDK" / "workspace" / "chat"
    workspace.mkdir(parents=True, exist_ok=True)
    marker = workspace / "session.json"
    previous = json.loads(marker.read_text())["session_id"] if resume and marker.exists() else None
    async with SdkAgent(workspace, date.today().isoformat(), previous) as agent:
        print("Study Coach (SDK). Empty line to quit.")
        while text := (await asyncio.to_thread(input, "> ")).strip():
            print((await agent.ask(text))["answer"])
            marker.write_text(json.dumps({"session_id": agent.session_id}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario")
    parser.add_argument("--out", default="results/sdk.json")
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--resume", action="store_true", help="with --chat: continue the latest session")
    args = parser.parse_args()
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is set, so the SDK would bill that key instead of your Claude Code login.\n"
              "Remove it in this terminal first (PowerShell):  Remove-Item Env:ANTHROPIC_API_KEY")
        return 2
    if args.chat:
        asyncio.run(chat(args.resume))
    elif args.scenario:
        asyncio.run(run_scenario(args.scenario, args.out))
    else:
        parser.error("use --scenario <file> or --chat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
