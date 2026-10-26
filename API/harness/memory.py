"""memory.py: where memory lives (state/memory.json) and how it is retrieved (only the relevant entries)."""
import re
from pathlib import Path

from shared.memory_store import MemoryStore

TOP_K = 5


def log(msg):
    print(f"[memory.py] {msg}")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 2}


class Memory:
    def __init__(self, state_dir: Path):
        self.store = MemoryStore(Path(state_dir) / "memory.json")
        log(f"loaded {len(self.store.all())} entries from {self.store.path.name}")

    def remember(self, key: str, value: str) -> str:
        result = self.store.remember(key, value)
        log(result)
        return result

    def recall(self, query: str = "") -> str:
        log(f"recall {query!r}")
        return self.store.recall(query)

    def relevant(self, text: str, k: int = TOP_K) -> list[tuple[str, str]]:
        """Up to k entries, ranked by word overlap with the user's message (all of them when there are few)."""
        entries = [(key, e["value"]) for key, e in self.store.all().items()]
        if len(entries) > k:
            words = _words(text)
            entries.sort(key=lambda kv: len(words & _words(f"{kv[0].replace('_', ' ')} {kv[1]}")), reverse=True)
        return entries[:k]
