from backend import answers


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, reply: str):
        self.reply = reply
        self.last_prompt = None

    def invoke(self, prompt: str):
        self.last_prompt = prompt
        return FakeResponse(self.reply)


def make_clip(i: int, start: int = 200) -> dict:
    return {
        "id": f"clip_{i}",
        "videoId": f"vid{i}",
        "title": f"Video {i}",
        "channelName": "chan",
        "startSeconds": start,
        "endSeconds": start + 60,
        "content": f"transcript text {i}",
        "thumbnailUrl": "",
    }


def test_generates_answer_with_clip_context(monkeypatch):
    fake = FakeLLM("The speaker explains X [[clip_0]].")
    monkeypatch.setattr(answers, "_get_llm", lambda api_key: fake)
    result = answers.generate_answer("what is X", [make_clip(0)], api_key="k")
    assert result == "The speaker explains X [[clip_0]]."
    assert "transcript text 0" in fake.last_prompt
    assert "[clip_0]" in fake.last_prompt
    assert "what is X" in fake.last_prompt


def test_returns_empty_string_on_llm_failure(monkeypatch):
    def boom(api_key):
        raise RuntimeError("llm down")

    monkeypatch.setattr(answers, "_get_llm", boom)
    assert answers.generate_answer("q", [make_clip(0)], api_key="k") == ""


def test_returns_empty_string_for_no_clips():
    assert answers.generate_answer("q", [], api_key="k") == ""
