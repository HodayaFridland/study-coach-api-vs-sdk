"""Runs the API version: `--scenario scenario.json --out results/api.json`, or `--chat` to talk to it."""
import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from API.agent import ApiAgent  # noqa: E402
from API.harness.history import History  # noqa: E402
from shared import scenario as sc  # noqa: E402

HARNESS = ["loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"]


def run_scenario(path: str, out: str) -> None:
    sc.log_next_to(out)
    scenario = sc.load(path)
    state = ROOT / "API" / "state" / "scenario"
    sc.clean_dir(state)
    turns, agent = [], None
    for session in scenario["sessions"]:
        conversation = agent.history.id if agent and session.get("resume_previous") else None
        print(f"\n=== session {session['id']}: new agent instance, state loaded from disk ({state}) ===")
        agent = ApiAgent(state, scenario["today"], scenario["api"]["compaction_threshold_tokens"],
                         conversation_id=conversation)
        for text in session["turns"]:
            n = len(turns) + 1
            print(f"\n--- turn {n} (session {session['id']}) ---\nUSER: {text}")
            started = time.perf_counter()
            record = agent.ask(text)
            record["seconds"] = round(time.perf_counter() - started, 2)
            print(f"AGENT: {record['answer']}")
            turns.append({"session": session["id"], "turn": n, "user": text, **record, "state": sc.snapshot(state)})

    loc = {f"{name}.py": len(sc.code_lines(ROOT / "API" / "harness" / f"{name}.py")) for name in HARNESS}
    loc["harness total"] = sum(loc.values())
    loc["agent.py + main.py"] = sum(len(sc.code_lines(ROOT / "API" / f)) for f in ("agent.py", "main.py"))
    extra = {"compactions": sum(t["compacted"] for t in turns),
             "compaction_threshold_tokens": scenario["api"]["compaction_threshold_tokens"]}
    sc.write(out, sc.build_results("api", scenario, turns, loc, extra))


def chat(resume: bool) -> None:
    state = ROOT / "API" / "state" / "chat"
    agent = ApiAgent(state, date.today().isoformat(), conversation_id=History.latest_id(state) if resume else None)
    print("Study Coach (API). Empty line to quit.")
    while text := input("> ").strip():
        print(agent.ask(text)["answer"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario")
    parser.add_argument("--out", default="results/api.json")
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--resume", action="store_true", help="with --chat: continue the latest conversation")
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Set it in this terminal only (never in code or git), e.g. in PowerShell:\n"
              '  $env:ANTHROPIC_API_KEY = "sk-ant-..."')
        return 2
    if args.chat:
        chat(args.resume)
    elif args.scenario:
        run_scenario(args.scenario, args.out)
    else:
        parser.error("use --scenario <file> or --chat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
