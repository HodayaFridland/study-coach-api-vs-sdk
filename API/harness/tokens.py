"""tokens.py: usage and cost of every model call, summed per turn."""

# $ per million tokens, Claude Opus 5.5 list prices (cache read 0.05x, 5-minute cache write 1.25x).
PRICES = {"claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20,
                              "cache_write_5m": 5.00, "cache_write_1h": 8.00}}


def log(msg):
    print(f"[tokens.py] {msg}")


class TokenMeter:
    def __init__(self, model: str):
        self.price = PRICES[model]
        self.last_context_tokens = 0  # size of the prompt on the latest call (read by compaction)
        self.turn = None

    def start_turn(self) -> None:
        self.turn = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "model_calls": 0, "cost_usd": 0.0}

    def record(self, usage, label: str = "call") -> float:
        i, o = usage.input_tokens, usage.output_tokens
        cr = usage.cache_read_input_tokens or 0
        cw = usage.cache_creation_input_tokens or 0
        split = getattr(usage, "cache_creation", None)
        cw_1h = (getattr(split, "ephemeral_1h_input_tokens", 0) or 0) if split else 0
        p = self.price
        cost = (i * p["input"] + o * p["output"] + cr * p["cache_read"]
                + (cw - cw_1h) * p["cache_write_5m"] + cw_1h * p["cache_write_1h"]) / 1e6
        for field, n in (("input", i), ("cache_read", cr), ("cache_write", cw), ("output", o)):
            self.turn[field] += n
        self.turn["model_calls"] += 1
        self.turn["cost_usd"] += cost
        self.last_context_tokens = i + cr + cw
        log(f"{label}: input={i} cache_read={cr} cache_write={cw} output={o} -> ${cost:.5f}")
        return cost

    def end_turn(self) -> dict:
        t = self.turn
        t["cost_usd"] = round(t["cost_usd"], 6)
        log(f"turn total: {t['model_calls']} calls, input={t['input']} cache_read={t['cache_read']} "
            f"cache_write={t['cache_write']} output={t['output']} -> ${t['cost_usd']:.4f}")
        return t
