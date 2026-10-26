"""history.py: the conversation, saved to disk append-only (one JSON line per event, never rewritten)."""
import json
from datetime import datetime
from pathlib import Path


def log(msg):
    print(f"[history.py] {msg}")


class History:
    def __init__(self, state_dir: Path, conversation_id: str | None = None):
        folder = Path(state_dir) / "history"
        folder.mkdir(parents=True, exist_ok=True)
        self.id = conversation_id or datetime.now().strftime("conv-%Y%m%d-%H%M%S-%f")
        self.path = folder / f"{self.id}.jsonl"
        self.messages: list[dict] = []
        self.pending_summary = None
        if self.path.exists():
            self._replay()
            log(f"resumed {self.id}: {len(self.messages)} messages since the last compaction")
        else:
            log(f"new conversation {self.id}")

    def _write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def append(self, message: dict) -> None:
        self.messages.append(message)
        self._write({"type": "message", "message": message})

    def compact(self, summary: str) -> None:
        """The old lines stay in the file; the model only sees what comes after this marker."""
        self._write({"type": "compaction", "summary": summary})
        log(f"compaction marker written; {len(self.messages)} messages dropped from the live context")
        self.messages = []

    def _replay(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["type"] == "compaction":
                self.messages, self.pending_summary = [], record["summary"]
            else:
                self.messages.append(record["message"])
                self.pending_summary = None

    @staticmethod
    def latest_id(state_dir: Path) -> str | None:
        files = sorted((Path(state_dir) / "history").glob("conv-*.jsonl"))
        return files[-1].stem if files else None
