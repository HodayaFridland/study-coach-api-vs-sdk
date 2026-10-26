"""Measurement code used by both runners: scenario, state snapshots, pass/fail checks, line counts, results file."""
import json
import platform
import re
import shutil
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path

from shared.memory_store import MemoryStore
from shared.planner import StudyPlanner
from shared.specs import EFFORT, MODEL

ROOT = Path(__file__).resolve().parents[1]
TOKEN_FIELDS = ("input", "cache_read", "cache_write", "output")


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)
        return len(text)

    def flush(self):
        for s in self.streams:
            s.flush()


def log_next_to(out: str) -> None:
    """Everything printed also goes to results/<name>.log (UTF-8)."""
    path = Path(out).with_suffix(".log")
    path.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = _Tee(sys.stdout, path.open("w", encoding="utf-8"))


def clean_dir(path: Path) -> None:
    """Every run starts from a clean state."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def snapshot(state_dir: Path) -> dict:
    state = StudyPlanner(state_dir / "study.json", "2000-01-01").snapshot()
    state["memory"] = MemoryStore(state_dir / "memory.json").all()
    return state


# ---- checks: most read the saved state after a given turn, not the answer text ----------------
def _state(turns, spec):
    n = spec.get("after_turn", len(turns))
    return turns[n - 1]["state"]


def _memory_lines(state):
    return [f"{k}: {e['value']}" for k, e in state["memory"].items()]


def _match(pattern, text):
    return re.search(pattern, text, re.IGNORECASE) is not None


def check_exam_dates(spec, turns):
    dates = sorted(e["date"] for e in _state(turns, spec)["exams"])
    ok = all(d in dates for d in spec["dates"]) and (not spec.get("exact") or len(dates) == len(spec["dates"]))
    return ok, f"exam dates saved: {dates}"


def check_memory_matches(spec, turns):
    lines = _memory_lines(_state(turns, spec))
    ok = all(any(_match(p, line) for line in lines) for p in spec["patterns"])
    return ok, f"memory: {lines}"


def check_sessions_in_range(spec, turns):
    sessions = [s for s in _state(turns, spec)["sessions"]
                if _match(spec["course"], s["course"]) and spec["from"] <= s["date"] <= spec["to"]]
    problems = [f"{s['id']} {s['date']} {s['start']} {s['minutes']}m" for s in sessions
                if s["minutes"] > spec["max_minutes"] or s["start"] < spec["start_not_before"]
                or s["date"] in spec.get("forbidden_dates", [])]
    ok = len(sessions) >= spec["min_count"] and not problems
    return ok, f"{len(sessions)} sessions in range, violations: {problems or 'none'}"


def check_max_session_minutes(spec, turns):
    longest = max((s["minutes"] for s in _state(turns, spec)["sessions"]), default=0)
    return longest <= spec["max_minutes"], f"longest session: {longest}m"


def check_memory_superseded(spec, turns):
    memory = _state(turns, spec)["memory"]
    details, ok = [], True
    for rule in spec["entries"]:
        updated = [k for k, e in memory.items() if _match(rule["new"], f"{k}: {e['value']}")
                   and any(_match(rule["old"], p) for p in e["previous"])]
        stale = [k for k, e in memory.items() if _match(rule["old"], f"{k}: {e['value']}")]
        ok = ok and bool(updated) and not stale
        details.append(f"{rule['new']!r}: updated={updated} stale={stale}")
    return ok, "; ".join(details)


def check_session_exists(spec, turns):
    hits = [s for s in _state(turns, spec)["sessions"] if s["date"] == spec["date"]
            and s["minutes"] == spec["minutes"] and s["start"] < spec["start_before"]]
    return bool(hits), f"matching sessions: {[s['id'] + ' ' + s['start'] for s in hits]}"


def check_tool_called(spec, turns):
    used = [t["turn"] for t in turns if t["session"] == spec["in_session"] and spec["tool"] in t["tools"]]
    return bool(used), f"{spec['tool']} called in turns {used}"


def check_answer_matches(spec, turns):
    answer = turns[spec["turn"] - 1]["answer"]
    missing = [p for p in spec["patterns"] if not _match(p, answer)]
    return not missing, f"missing patterns: {missing or 'none'}"


CHECKS = {f.__name__.removeprefix("check_"): f for f in (
    check_exam_dates, check_memory_matches, check_sessions_in_range, check_max_session_minutes,
    check_memory_superseded, check_session_exists, check_tool_called, check_answer_matches)}


def run_checks(scenario: dict, turns: list[dict]) -> list[dict]:
    results = []
    for spec in scenario["checks"]:
        try:
            passed, detail = CHECKS[spec["type"]](spec, turns)
        except Exception as e:  # a crashed check is a failed check
            passed, detail = False, f"check crashed: {type(e).__name__}: {e}"
        results.append({"name": spec["name"], "kind": spec["kind"], "passed": passed, "detail": detail})
        print(f"[check] {'PASS' if passed else 'FAIL'} {spec['name']} ({spec['kind']}): {detail}")
    return results


# ---- lines of code -------------------------------------------------------------------------------
def code_lines(path: Path) -> list[str]:
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def count_replaces(paths) -> dict:
    """Counts SDK code lines tagged `# replaces: <file>` per replaced file."""
    counts = {}
    for path in paths:
        for line in code_lines(path):
            if "# replaces:" in line:
                tags = line.split("# replaces:")[1].split("(")[0]  # "(...)" is a free-text note
                for name in (t.strip() for t in tags.split(",")):
                    if name:
                        name = name.split()[0]
                        counts[name] = counts.get(name, 0) + 1
    return counts


# ---- results file --------------------------------------------------------------------------------
def totals(turns: list[dict]) -> dict:
    t = {f: sum(turn["tokens"][f] for turn in turns) for f in TOKEN_FIELDS}
    prompt = t["input"] + t["cache_read"] + t["cache_write"]
    t["cache_hit_pct"] = round(100 * t["cache_read"] / prompt, 1) if prompt else 0.0
    t["model_calls"] = sum(turn["model_calls"] for turn in turns)
    t["tool_calls"] = sum(len(turn["tools"]) for turn in turns)
    t["cost_usd"] = round(sum(turn["cost_usd"] for turn in turns), 4)
    t["seconds"] = round(sum(turn["seconds"] for turn in turns), 1)
    return t


def _version(package):
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def build_results(harness: str, scenario: dict, turns: list[dict], loc: dict, extra: dict) -> dict:
    checks = run_checks(scenario, turns)
    passed = sum(c["passed"] for c in checks)
    return {
        "harness": harness,
        "model": MODEL,
        "effort": EFFORT,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "versions": {"python": platform.python_version(), "anthropic": _version("anthropic"),
                     "claude-agent-sdk": _version("claude-agent-sdk")},
        "totals": totals(turns),
        "checks_passed": f"{passed}/{len(checks)}",
        "checks": checks,
        "loc": loc,
        "extra": extra,
        "turns": turns,
    }


def write(path: str, results: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    t = results["totals"]
    print(f"[results] {out}: checks {results['checks_passed']}, calls {t['model_calls']}, "
          f"cache {t['cache_hit_pct']}%, cost ${t['cost_usd']}, {t['seconds']}s")
