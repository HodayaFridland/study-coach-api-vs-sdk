"""A fake Anthropic client: scripted responses, no network, no key."""
from types import SimpleNamespace


class Block(SimpleNamespace):
    def model_dump(self, mode=None, exclude_none=False):
        return {k: v for k, v in vars(self).items() if not (exclude_none and v is None)}


def text(t):
    return Block(type="text", text=t)


def tool_use(name, args, id_):
    return Block(type="tool_use", id=id_, name=name, input=args)


def usage(input_tokens=100, output_tokens=20, cache_read=0, cache_write=0):
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens,
                           cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_write,
                           cache_creation=None)


def response(*blocks, stop_reason="end_turn", u=None):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, usage=u or usage(),
                           model="claude-opus-5-5")


class FakeClient:
    """client.beta.messages.create(...) returns the next scripted response and records the request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **request):
        self.requests.append(request)
        return self.responses.pop(0)
