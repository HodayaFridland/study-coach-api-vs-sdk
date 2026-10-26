"""Builds the comparison tables in REPORT.md from results/api.json and results/sdk.json.
Run after every scenario run:  python shared/report.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from shared import scenario as sc  # noqa: E402

START, END = "<!-- TABLES:START -->", "<!-- TABLES:END -->"
HARNESS = ["loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"]
PENDING = "טרם הורץ"


def load(name):
    path = ROOT / "results" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def cell(result, fn):
    return fn(result) if result else PENDING


def summary_table(api, sdk):
    rows = [
        ("טוקני input (לא מה-cache)", lambda r: f"{r['totals']['input']:,}"),
        ("cache read", lambda r: f"{r['totals']['cache_read']:,}"),
        ("cache write", lambda r: f"{r['totals']['cache_write']:,}"),
        ("output", lambda r: f"{r['totals']['output']:,}"),
        ("אחוז cache (read מתוך כל ה-prompt)", lambda r: f"{r['totals']['cache_hit_pct']}%"),
        ("קריאות למודל", lambda r: str(r["totals"]["model_calls"])),
        ("קריאות לכלים", lambda r: str(r["totals"]["tool_calls"])),
        ("עלות (USD)", lambda r: f"${r['totals']['cost_usd']:.4f}"),
        ("זמן (שניות)", lambda r: str(r["totals"]["seconds"])),
        ("בדיקות שעברו", lambda r: r["checks_passed"]),
    ]
    lines = ["| מדד | API | SDK |", "|---|---|---|"]
    lines += [f"| {label} | {cell(api, fn)} | {cell(sdk, fn)} |" for label, fn in rows]
    return "\n".join(lines)


def turn_table(api, sdk):
    def describe(result, i):
        if not result:
            return PENDING
        t = result["turns"][i]
        k = t["tokens"]
        extra = " (compaction)" if t.get("compacted") else ""
        return (f"{t['model_calls']} קריאות, in {k['input']} / read {k['cache_read']} / write {k['cache_write']} "
                f"/ out {k['output']}, ${t['cost_usd']:.4f}{extra}")

    base = api or sdk
    lines = ["| תור | כלים (SDK) | API | SDK |", "|---|---|---|---|"]
    for i, t in enumerate(base["turns"]):
        tools = ", ".join((sdk or api)["turns"][i]["tools"]) or "-"
        lines.append(f"| {t['session']}.{t['turn']} | {tools} | {describe(api, i)} | {describe(sdk, i)} |")
    return "\n".join(lines)


def checks_table(api, sdk):
    names = [c["name"] for c in (api or sdk)["checks"]]
    kinds = {c["name"]: c["kind"] for c in (api or sdk)["checks"]}

    def mark(result, name):
        if not result:
            return PENDING
        return "✅" if next(c for c in result["checks"] if c["name"] == name)["passed"] else "❌"

    lines = ["| בדיקה | סוג | API | SDK |", "|---|---|---|---|"]
    lines += [f"| `{n}` | {kinds[n]} | {mark(api, n)} | {mark(sdk, n)} |" for n in names]
    return "\n".join(lines)


def loc_table():
    api = {n: len(sc.code_lines(ROOT / "API" / "harness" / f"{n}.py")) for n in HARNESS}
    sdk = sc.count_replaces([ROOT / "SDK" / f for f in ("agent.py", "tools.py", "main.py")])
    lines = ["| חלק ב-harness | API: שורות קוד בקובץ | SDK: שורות `# replaces` |", "|---|---|---|"]
    for n in HARNESS:
        s = sdk.get(f"{n}.py", 0)
        lines.append(f"| {n}.py | {api[n]} | {s if s else '0 (אוטומטי)'} |")
    lines.append(f"| **סה\"כ harness** | **{sum(api.values())}** | **{sum(sdk.values())}** |")
    glue_api = sum(len(sc.code_lines(ROOT / "API" / f)) for f in ("agent.py", "main.py"))
    glue_sdk = sum(len(sc.code_lines(ROOT / "SDK" / f)) for f in ("agent.py", "tools.py", "main.py"))
    lines.append(f"| כל קוד הגרסה (harness + agent + main + tools) | {sum(api.values()) + glue_api} | {glue_sdk} |")
    return "\n".join(lines)


def main():
    api, sdk = load("api"), load("sdk")
    if not (api or sdk):
        sys.exit("no results yet: run API/main.py and/or SDK/main.py first")
    tables = "\n\n".join([
        "### סיכום\n\n" + summary_table(api, sdk),
        "### לפי תור\n\n" + turn_table(api, sdk),
        "### בדיקות pass/fail\n\n" + checks_table(api, sdk),
        "### שורות קוד (בלי שורות ריקות והערות)\n\n" + loc_table(),
    ])
    report = ROOT / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    head, rest = text.split(START)
    _, tail = rest.split(END)
    report.write_text(f"{head}{START}\n{tables}\n{END}{tail}", encoding="utf-8")
    print(f"[report.py] tables updated in {report} (api: {'yes' if api else 'missing'}, sdk: {'yes' if sdk else 'missing'})")


if __name__ == "__main__":
    main()
