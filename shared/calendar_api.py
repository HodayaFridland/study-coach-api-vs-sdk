"""The external tool: Jewish/Israeli holidays from the public Hebcal API (no key needed)."""
import json
import urllib.error
import urllib.parse
import urllib.request

from shared.planner import ToolError, parse_date

HEBCAL_URL = "https://www.hebcal.com/hebcal"
MAX_DAYS = 92
MAX_LINES = 20


def http_get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "study-coach/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise ToolError(f"calendar service unavailable: {e}")


def israel_holidays(start: str, end: str, fetch=http_get_json) -> str:
    first, last = parse_date(start, "start"), parse_date(end, "end")
    if last < first:
        raise ToolError("end is before start")
    if (last - first).days > MAX_DAYS:
        raise ToolError(f"range too long (max {MAX_DAYS} days); split it")
    query = urllib.parse.urlencode({"v": 1, "cfg": "json", "maj": "on", "min": "on", "mod": "on",
                                    "i": "on", "start": start, "end": end})
    data = fetch(f"{HEBCAL_URL}?{query}")
    # Token optimization: keep 3 fields per holiday instead of Hebcal's full JSON (~15 fields each).
    lines = [f"{item['date'][:10]} {item['title']} ({item.get('subcat', 'other')})"
             for item in data.get("items", []) if item.get("category") == "holiday"]
    if not lines:
        return f"no holidays between {start} and {end}"
    extra = len(lines) - MAX_LINES
    return "\n".join(lines[:MAX_LINES] + ([f"+{extra} more"] if extra > 0 else []))
