"""Domain code: the study plan (exams + study sessions) stored in study.json. Tool outputs are kept compact."""
import json
from datetime import date, datetime
from pathlib import Path

MAX_LINES = 25


class ToolError(Exception):
    """A failure the model should see and recover from (sent back as is_error)."""


def parse_date(value: str, field: str = "date") -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolError(f"{field} must be YYYY-MM-DD, got {value!r}")


def parse_time(value: str) -> int:
    """'19:30' -> minutes after midnight."""
    try:
        t = datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError):
        raise ToolError(f"start must be HH:MM, got {value!r}")
    return t.hour * 60 + t.minute


def fmt_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class StudyPlanner:
    def __init__(self, path: Path, today: str):
        self.path = Path(path)
        self.today = parse_date(today, "today")

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"exams": [], "sessions": [], "next_id": 1}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def _future(self, value: str) -> date:
        d = parse_date(value)
        if d < self.today:
            raise ToolError(f"{value} is in the past (today is {self.today})")
        return d

    # ---- tools -------------------------------------------------------------
    def add_exam(self, course: str, date: str, topics: list[str] | None = None) -> str:
        self._future(date)
        data = self._load()
        for exam in data["exams"]:
            if exam["course"] == course and exam["date"] == date:
                return f"already saved: {exam['id']} {date} {course}"
        exam = {"id": f"E{data['next_id']}", "course": course, "date": date, "topics": topics or []}
        data["next_id"] += 1
        data["exams"].append(exam)
        self._save(data)
        return f"OK {exam['id']} exam {date} {course} ({len(exam['topics'])} topics)"

    def schedule_study(self, course: str, date: str, start: str, minutes: int, topic: str = "") -> str:
        self._future(date)
        begin = parse_time(start)
        if isinstance(minutes, float) and minutes.is_integer():
            minutes = int(minutes)
        if not isinstance(minutes, int) or not 15 <= minutes <= 480:
            raise ToolError(f"minutes must be an integer 15-480, got {minutes!r}")
        end = begin + minutes
        if end > 24 * 60:
            raise ToolError("session must end before midnight")
        data = self._load()
        same_day = [s for s in data["sessions"] if s["date"] == date]
        for s in same_day:
            s_begin = parse_time(s["start"])
            if begin < s_begin + s["minutes"] and s_begin < end:
                raise ToolError(f"overlaps {s['id']} ({s['start']}-{fmt_time(s_begin + s['minutes'])})")
        session = {"id": f"S{data['next_id']}", "course": course, "date": date,
                   "start": fmt_time(begin), "minutes": minutes, "topic": topic}
        data["next_id"] += 1
        data["sessions"].append(session)
        self._save(data)
        day_total = minutes + sum(s["minutes"] for s in same_day)
        return f"OK {session['id']} {date} {session['start']} {minutes}m {course} | day total {day_total}m"

    def list_plan(self, until: str | None = None, course: str | None = None) -> str:
        last = parse_date(until, "until") if until else None
        data = self._load()
        rows = []
        for e in data["exams"]:
            rows.append((e["date"], "", f"{e['id']} {e['date']} EXAM {e['course']}: {', '.join(e['topics'])}", e["course"]))
        for s in data["sessions"]:
            topic = f" ({s['topic']})" if s["topic"] else ""
            rows.append((s["date"], s["start"], f"{s['id']} {s['date']} {s['start']} {s['minutes']}m {s['course']}{topic}", s["course"]))
        rows = [r for r in rows if (not last or r[0] <= last.isoformat())
                and (not course or course.lower() in r[3].lower())]
        rows.sort()
        if not rows:
            return "plan is empty" if not (until or course) else "nothing matches"
        lines = [r[2] for r in rows[:MAX_LINES]]
        if len(rows) > MAX_LINES:
            lines.append(f"+{len(rows) - MAX_LINES} more (narrow with until/course)")
        return "\n".join(lines)

    # ---- helpers for the harnesses -----------------------------------------
    def summary(self) -> str:
        """One line about the plan, for per-turn context (never the full plan)."""
        data = self._load()
        if not data["exams"] and not data["sessions"]:
            return "plan is empty"
        upcoming = sorted(data["exams"], key=lambda e: e["date"])
        nxt = f"next: {upcoming[0]['course']} on {upcoming[0]['date']}" if upcoming else "none"
        total = sum(s["minutes"] for s in data["sessions"])
        return f"{len(data['exams'])} exams ({nxt}), {len(data['sessions'])} sessions totalling {total}m"

    def snapshot(self) -> dict:
        data = self._load()
        return {"exams": data["exams"], "sessions": data["sessions"]}
