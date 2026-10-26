"""The agent's prompt and tool descriptions. One copy, used by both API/ and SDK/, so the comparison is fair."""

MODEL = "claude-opus-5-5"
EFFORT = "medium"

SYSTEM_PROMPT = """You are Study Coach, a personal study-planning assistant for one university student.
You keep the student's exams and study sessions in a plan (through tools) and you remember durable preferences.

Rules:
- Reply in the user's language (usually Hebrew). Be brief: 1-4 short sentences or a short list.
- Change the plan only through tools, and never claim something was saved unless a tool confirmed it.
- When the user states a durable preference or decision, save it with `remember`. Canonical keys:
  preferred_study_time (morning | afternoon | evening) and max_daily_minutes (integer). Use short snake_case keys for anything else.
- Respect saved preferences when scheduling: morning = start before 12:00, afternoon = 12:00-17:00,
  evening = start at 17:00 or later. Never exceed max_daily_minutes on any single day.
- If a request contradicts a saved preference, do not act on it and do not change memory yet: point out the
  conflict in one sentence and ask which to follow. Once the user confirms a change, update the same memory key
  with `remember`, then act.
- Before scheduling sessions in a date range, call `israel_holidays` for that range. Dates marked (major) are
  unavailable; minor and modern holidays are normal study days.
- Use `list_plan` to look up plan details instead of guessing."""

DATE = {"type": "string", "description": "Date as YYYY-MM-DD"}

TOOL_SPECS = [
    {
        "name": "add_exam",
        "description": "Add an exam to the plan. Returns one confirmation line.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course": {"type": "string", "description": "Course name"},
                "date": DATE,
                "topics": {"type": "array", "items": {"type": "string"}, "description": "Exam topics"},
            },
            "required": ["course", "date"],
            "additionalProperties": False,
        },
    },
    {
        "name": "schedule_study",
        "description": "Add one study session. Returns one line including that day's total minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course": {"type": "string"},
                "date": DATE,
                "start": {"type": "string", "description": "Start time as HH:MM (24h)"},
                "minutes": {"type": "integer", "description": "Length in minutes (15-480)"},
                "topic": {"type": "string", "description": "Optional topic for the session"},
            },
            "required": ["course", "date", "start", "minutes"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_plan",
        "description": "List exams and study sessions, one compact line each, sorted by date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "until": {"type": "string", "description": "Optional last date to include (YYYY-MM-DD)"},
                "course": {"type": "string", "description": "Optional course name filter (substring)"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "israel_holidays",
        "description": "External: query the Hebcal Jewish calendar API (Israel schedule) for holidays in a date "
        "range (at most 92 days). Returns one line per holiday: date, name, (major|minor|modern).",
        "input_schema": {
            "type": "object",
            "properties": {"start": DATE, "end": DATE},
            "required": ["start", "end"],
            "additionalProperties": False,
        },
    },
    {
        "name": "remember",
        "description": "Save or update a durable user preference or decision. Saving an existing key replaces "
        "its value (the old value is kept as history).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "snake_case key, e.g. preferred_study_time"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "recall",
        "description": "Search saved memories by keyword. An empty query lists everything.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
    },
]
