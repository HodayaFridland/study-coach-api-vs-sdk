"""The scenario's pass/fail checks, on hand-made runs: a good one passes all, a bad one fails the right ones."""
import copy

from shared import scenario as sc

SCENARIO = sc.load(sc.ROOT / "scenario.json")
EXAMS = [{"id": "E1", "course": "אלגברה לינארית", "date": "2027-05-02", "topics": []},
         {"id": "E2", "course": "מבני נתונים", "date": "2027-05-09", "topics": []}]
ALGEBRA = [{"id": f"S{i}", "course": "אלגברה לינארית", "date": d, "start": "19:00", "minutes": 120, "topic": ""}
           for i, d in ((3, "2027-04-18"), (4, "2027-04-19"), (5, "2027-04-20"))]
EVENING = {"preferred_study_time": {"value": "evening", "previous": []},
           "max_daily_minutes": {"value": "120", "previous": []}}
MORNING = {"preferred_study_time": {"value": "morning", "previous": ["evening"]},
           "max_daily_minutes": {"value": "180", "previous": ["120"]}}
LONG = {"id": "S6", "course": "מבני נתונים", "date": "2027-05-05", "start": "09:00", "minutes": 180, "topic": ""}


def turn(n, session, tools=(), answer="", sessions=(), memory=None):
    return {"session": session, "turn": n, "tools": list(tools), "answer": answer,
            "state": {"exams": EXAMS, "sessions": list(sessions), "memory": memory or {}}}


def good_run():
    return [turn(1, 1, ["add_exam", "add_exam"]),
            turn(2, 1, ["remember", "remember"], memory=EVENING),
            turn(3, 1, ["israel_holidays"] + ["schedule_study"] * 3, sessions=ALGEBRA, memory=EVENING),
            turn(4, 2, answer="הכי טוב לך בערב, עד 120 דקות ביום", sessions=ALGEBRA, memory=EVENING),
            turn(5, 2, answer="זה סותר את המגבלה", sessions=ALGEBRA, memory=EVENING),
            turn(6, 2, ["remember", "remember", "schedule_study"], sessions=ALGEBRA + [LONG], memory=MORNING),
            turn(7, 2, ["list_plan"], sessions=ALGEBRA + [LONG], memory=MORNING)]


def test_a_good_run_passes_every_check():
    results = sc.run_checks(SCENARIO, good_run())
    assert len(results) >= 5 and all(r["passed"] for r in results), results
    assert sum(r["kind"] == "state" for r in results) > len(results) / 2  # most checks read saved state


def test_a_bad_run_fails_the_right_checks():
    run = good_run()
    pesach = copy.deepcopy(ALGEBRA)
    pesach[2]["date"] = "2027-04-21"  # Erev Pesach
    run[2]["state"]["sessions"] = pesach
    run[4]["state"]["sessions"] = ALGEBRA + [dict(LONG, start="19:00")]  # 180m booked despite the limit
    run[5]["state"]["memory"] = {**MORNING, "study_time_old": {"value": "evening", "previous": []}}  # duplicate
    failed = {r["name"] for r in sc.run_checks(SCENARIO, run) if not r["passed"]}
    assert failed == {"sessions_respect_preferences_and_holidays", "conflicting_request_not_applied_silently",
                      "contradiction_replaces_memory_without_duplicates"}


def test_totals_and_cache_percentage():
    turns = [{"tokens": {"input": 100, "cache_read": 800, "cache_write": 100, "output": 50},
              "model_calls": 2, "tools": ["a"], "cost_usd": 0.01, "seconds": 1.0}] * 2
    t = sc.totals(turns)
    assert t["cache_hit_pct"] == 80.0 and t["model_calls"] == 4 and t["cost_usd"] == 0.02
