"""compaction.py: past a token threshold, summarize the whole conversation and continue from the summary only."""
from API.harness import caching

SUMMARY_PROMPT = (
    "Summarize this conversation so it can continue without the transcript. Keep: every exam and study "
    "session with ids, dates and times; the user's preferences and decisions (and which ones changed); "
    "any open question or pending request. At most 150 words, plain text.")


def log(msg):
    print(f"[compaction.py] {msg}")


class Compactor:
    def __init__(self, threshold_tokens: int):
        self.threshold = threshold_tokens

    def needed(self, context_tokens: int) -> bool:
        """Checked only between turns, never in the middle of a tool round."""
        return context_tokens > self.threshold

    def summarize(self, create, params: dict, messages: list[dict], meter) -> str:
        log(f"context reached {meter.last_context_tokens} tokens > {self.threshold}: summarizing {len(messages)} messages")
        ask = {"role": "user", "content": [{"type": "text", "text": SUMMARY_PROMPT}]}
        # Same model, system and tools as the conversation, so the cached prefix is reused; tool_choice none = text only.
        response = create(**params, tool_choice={"type": "none"},
                          messages=caching.with_message_breakpoint(messages + [ask]))
        meter.record(response.usage, "compaction")
        summary = "".join(b.text for b in response.content if b.type == "text").strip()
        log(f"summary: {len(summary)} chars replaces the transcript")
        return summary
