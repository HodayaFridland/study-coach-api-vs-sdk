import pytest

from shared.calendar_api import israel_holidays
from shared.memory_store import MemoryStore
from shared.planner import StudyPlanner, ToolError


@pytest.fixture
def planner(tmp_path):
    return StudyPlanner(tmp_path / "study.json", "2027-03-14")


def test_exam_in_the_past_is_an_error(planner):
    with pytest.raises(ToolError, match="in the past"):
        planner.add_exam("Algebra", "2027-01-01")


def test_duplicate_exam_is_not_saved_twice(planner):
    planner.add_exam("Algebra", "2027-05-02", ["matrices"])
    assert planner.add_exam("Algebra", "2027-05-02").startswith("already saved")
    assert len(planner.snapshot()["exams"]) == 1


def test_overlapping_sessions_are_rejected_and_day_total_reported(planner):
    assert planner.schedule_study("Algebra", "2027-04-18", "19:00", 60).endswith("day total 60m")
    with pytest.raises(ToolError, match="overlaps"):
        planner.schedule_study("Algebra", "2027-04-18", "19:30", 60)
    assert planner.schedule_study("Algebra", "2027-04-18", "20:00", 30).endswith("day total 90m")


def test_list_plan_is_one_line_per_item_sorted(planner):
    planner.add_exam("Algebra", "2027-05-02", ["matrices"])
    planner.schedule_study("Algebra", "2027-04-18", "19:00", 90, "matrices")
    lines = planner.list_plan().splitlines()
    assert lines == ["S2 2027-04-18 19:00 90m Algebra (matrices)", "E1 2027-05-02 EXAM Algebra: matrices"]
    assert planner.list_plan(until="2027-04-30") == lines[0]
    assert "1 exams" in planner.summary()


def test_holidays_are_compacted_to_one_line_each():
    def fake_fetch(url):
        assert "start=2027-04-18" in url and "i=on" in url
        return {"items": [
            {"date": "2027-04-21", "title": "Erev Pesach", "category": "holiday", "subcat": "major", "hebrew": "..."},
            {"date": "2027-04-22", "title": "Omer", "category": "omer"},
        ]}
    assert israel_holidays("2027-04-18", "2027-04-24", fetch=fake_fetch) == "2027-04-21 Erev Pesach (major)"


def test_holidays_range_validation():
    with pytest.raises(ToolError, match="too long"):
        israel_holidays("2027-01-01", "2027-12-31", fetch=lambda url: {})
    with pytest.raises(ToolError, match="before start"):
        israel_holidays("2027-02-01", "2027-01-01", fetch=lambda url: {})


def test_memory_contradiction_replaces_value_and_keeps_history(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    assert store.remember("Preferred Study Time", "evening") == "saved preferred_study_time: evening"
    assert store.remember("preferred_study_time", "morning") == "updated preferred_study_time: evening -> morning"
    assert store.all() == {"preferred_study_time": {"value": "morning", "previous": ["evening"]}}
    assert store.recall("time") == "preferred_study_time: morning"
