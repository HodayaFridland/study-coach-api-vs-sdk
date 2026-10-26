"""tools.py: JSON schemas for the API, dispatch by name, and errors returned to the model as is_error."""
from shared.planner import ToolError
from shared.specs import TOOL_SPECS

MAX_RESULT_CHARS = 1500  # token optimization: no tool may flood the context


def log(msg):
    print(f"[tools.py] {msg}")


class ToolRegistry:
    def __init__(self, handlers: dict):
        self.handlers = handlers
        # Fixed order and content on every request, so the tools stay in the cached prefix.
        self.schemas = [{"name": s["name"], "description": s["description"], "input_schema": s["input_schema"]}
                        for s in TOOL_SPECS]
        self.calls: list[str] = []

    def execute(self, block) -> dict:
        self.calls.append(block.name)
        is_error = True
        try:
            output = self.handlers[block.name](**block.input)
            is_error = False
        except KeyError:
            output = f"error: unknown tool {block.name!r}"
        except ToolError as e:
            output = f"error: {e}"
        except TypeError as e:
            output = f"error: bad arguments: {e}"
        except Exception as e:  # any crash goes back to the model instead of killing the loop
            output = f"error: {type(e).__name__}: {e}"
        if len(output) > MAX_RESULT_CHARS:
            output = output[:MAX_RESULT_CHARS] + f"...[truncated {len(output) - MAX_RESULT_CHARS} chars]"
        log(f"{block.name}({block.input}) -> {'ERROR ' if is_error else ''}{output.splitlines()[0][:90]}")
        result = {"type": "tool_result", "tool_use_id": block.id, "content": output}
        if is_error:
            result["is_error"] = True
        return result
