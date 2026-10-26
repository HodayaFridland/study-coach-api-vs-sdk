"""The memory file format (memory.json): key -> current value + previous values. Both harnesses use it."""
import json
import re
from pathlib import Path


def normalize_key(key: str) -> str:
    return re.sub(r"\W+", "_", key.strip().lower()).strip("_") or "note"


class MemoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def all(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {}

    def _save(self, entries: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")

    def remember(self, key: str, value: str) -> str:
        """A contradicting value replaces the old one (no duplicate keys); the old value moves to `previous`."""
        key, value = normalize_key(key), str(value).strip()
        entries = self.all()
        old = entries.get(key)
        if old and old["value"] == value:
            return f"unchanged {key}: {value}"
        entries[key] = {"value": value, "previous": (old["previous"] + [old["value"]]) if old else []}
        self._save(entries)
        return f"updated {key}: {old['value']} -> {value}" if old else f"saved {key}: {value}"

    def recall(self, query: str = "") -> str:
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1]
        hits = [f"{k}: {e['value']}" for k, e in self.all().items()
                if not words or any(w in f"{k} {e['value']}".lower() for w in words)]
        return "\n".join(hits) if hits else "no matching memories"
