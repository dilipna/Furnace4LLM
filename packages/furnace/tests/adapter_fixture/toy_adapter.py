"""Deterministic adapter for protocol tests. No learned parameters; not a model."""


class Reverser:
    def __init__(self):
        self.seen: list[str] = []
        self.loaded = False

    def load(self, weights_dir):
        self.loaded = True

    def reset(self):
        # Recurrent/session state must not leak between requests.
        self.seen.clear()

    def generate(self, messages, max_tokens, temperature):
        text = messages[-1]["content"]
        self.seen.append(text)
        if text == "fail":
            raise RuntimeError("PRIVATE ADAPTER DETAIL")
        reply = f"reversed:{text[::-1]} state={len(self.seen)}"
        if len(reply) > max_tokens:
            return reply[:max_tokens], "length"
        return reply, "stop"


class Broken:
    def load(self, weights_dir):
        raise RuntimeError("cannot load")

    def generate(self, messages, max_tokens, temperature):
        raise AssertionError("never called")
