"""Backend failure handling: model-side tool-call refusals become recorded failed replies,
not crashed runs; transport errors still raise after retries."""
import pytest

from nullspace.backends import OpenAICompatBackend


class _Resp:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        outer = self

        class _Comp:
            def create(self, **kw):
                outer.calls += 1
                item = outer.script.pop(0)
                if isinstance(item, Exception):
                    raise item
                return _Resp(item)

        self.chat = type("Chat", (), {"completions": _Comp()})()


def make(script, n_clients=1):
    be = OpenAICompatBackend.__new__(OpenAICompatBackend)
    be.clients = [FakeClient(script) for _ in range(n_clients)]
    be.i, be.model, be.temperature, be.max_tokens = 0, "m", 0.7, 100
    be.retries, be.reasoning_effort, be.name = 4, None, "fake"
    be.tool_failures, be.sleep = 0, (lambda s: None)
    return be


TOOL_ERR = Exception("Error code: 400 - {'error': {'code': 'tool_use_failed', 'message': 'model called a tool'}}")


def test_tool_call_refusal_resampled_then_succeeds():
    be = make([TOOL_ERR, "ok"])
    assert be.complete("p") == "ok"
    assert be.tool_failures == 1


def test_persistent_tool_call_refusal_returns_empty_and_counts():
    be = make([TOOL_ERR] * 10)
    assert be.complete("p") == ""
    assert be.tool_failures == 3  # three samples, then give up on this reply


def test_transport_error_still_raises_after_retries():
    be = make([Exception("Error code: 500 boom")] * 10)
    with pytest.raises(RuntimeError):
        be.complete("p")
