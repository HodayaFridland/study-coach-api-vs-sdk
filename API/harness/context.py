"""context.py: what goes into each turn. Only new, relevant facts - never the full plan (that is fetched by tools)."""


def log(msg):
    print(f"[context.py] {msg}")


class ContextBuilder:
    def __init__(self, memory, planner, today: str):
        self.memory, self.planner, self.today = memory, planner, today
        self.reset()

    def reset(self):
        """A new (or compacted) conversation has seen nothing yet."""
        self.shown: set[tuple[str, str]] = set()
        self.last_plan = None
        self.sent_today = False

    def user_content(self, text: str, summary: str | None = None) -> list[dict]:
        lines = []
        if not self.sent_today:
            lines.append(f"today: {self.today}")
            self.sent_today = True
        new = [kv for kv in self.memory.relevant(text) if kv not in self.shown]
        if new:
            lines.append("memory:")
            lines += [f"- {k}: {v}" for k, v in new]
            self.shown.update(new)
        plan = self.planner.summary()
        if plan != self.last_plan:
            lines.append(f"plan: {plan}")
            self.last_plan = plan

        blocks = []
        if summary:
            blocks.append({"type": "text", "text": f"<conversation_summary>\n{summary}\n</conversation_summary>"})
        if lines:
            blocks.append({"type": "text", "text": "<context>\n" + "\n".join(lines) + "\n</context>"})
        blocks.append({"type": "text", "text": text})
        extra_chars = sum(len(b["text"]) for b in blocks[:-1])
        log(f"injected {len(new)} memories, plan line={'yes' if 'plan: ' + plan in lines else 'no (unchanged)'}, "
            f"summary={'yes' if summary else 'no'}, ~{extra_chars // 4} tokens of context")
        return blocks
