"""FakeLLM: allowed ONLY in unit tests. The app always calls Gemini live."""
from skeptic.agent import LLMResponse


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, *, model, input, system_instruction, previous_interaction_id, thinking_level, response_schema, timeout):
        self.calls.append({"model": model, "input": input, "previous": previous_interaction_id, "schema": response_schema})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LLMResponse(interaction_id=f"fake_{len(self.calls)}", text=reply, usage={"input_tokens": 1}, model=model)
