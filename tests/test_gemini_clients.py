import httpx

from backend import gemini_clients, ingest, knowledge, rag


class FakeEmbeddings:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_get_embeddings_client_caches_per_key_and_task_type(monkeypatch):
    monkeypatch.setattr(gemini_clients, "_embeddings_cache", {})
    monkeypatch.setattr(
        gemini_clients,
        "GoogleGenerativeAIEmbeddings",
        lambda **kwargs: FakeEmbeddings(**kwargs),
    )

    document_client = gemini_clients.get_embeddings_client("key-1", "RETRIEVAL_DOCUMENT")
    query_client = gemini_clients.get_embeddings_client("key-1", "RETRIEVAL_QUERY")

    assert document_client is gemini_clients.get_embeddings_client("key-1", "RETRIEVAL_DOCUMENT")
    assert query_client is gemini_clients.get_embeddings_client("key-1", "RETRIEVAL_QUERY")
    assert document_client is not query_client
    assert document_client.kwargs["task_type"] == "RETRIEVAL_DOCUMENT"
    assert query_client.kwargs["task_type"] == "RETRIEVAL_QUERY"
    assert gemini_clients.get_embeddings_client("key-2", "RETRIEVAL_DOCUMENT") is not (
        document_client
    )


def test_get_embeddings_client_rejects_missing_or_placeholder_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    try:
        gemini_clients.get_embeddings_client(None)
    except ValueError as exc:
        assert "No API key provided" in str(exc)
    else:
        raise AssertionError("missing API key should be rejected")

    try:
        gemini_clients.get_embeddings_client("PLACEHOLDER_API_KEY")
    except ValueError as exc:
        assert "No API key provided" in str(exc)
    else:
        raise AssertionError("placeholder API key should be rejected")


def test_module_seams_delegate_to_shared_factory(monkeypatch):
    calls = []

    def fake_factory(api_key=None, task_type="RETRIEVAL_DOCUMENT"):
        calls.append((api_key, task_type))
        return object()

    monkeypatch.setattr(ingest, "get_embeddings_client", fake_factory)
    monkeypatch.setattr(rag, "get_embeddings_client", fake_factory)
    monkeypatch.setattr(knowledge, "get_embeddings_client", fake_factory)

    ingest.get_embeddings("key")
    rag._get_embeddings("key")
    knowledge._get_source_index_embeddings("key")

    assert calls == [
        ("key", "RETRIEVAL_DOCUMENT"),
        ("key", "RETRIEVAL_QUERY"),
        ("key", "RETRIEVAL_DOCUMENT"),
    ]


def test_is_retryable_gemini_error_accepts_transport_and_quota_failures():
    assert gemini_clients.is_retryable_gemini_error(httpx.ConnectTimeout("connection timed out"))
    assert gemini_clients.is_retryable_gemini_error(
        RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded, retry in 1s")
    )
    assert gemini_clients.is_retryable_gemini_error(RuntimeError("503 Service Unavailable"))


def test_is_retryable_gemini_error_rejects_permanent_failures():
    assert not gemini_clients.is_retryable_gemini_error(
        ValueError("No API key provided. Set GEMINI_API_KEY in .env.local")
    )
    assert not gemini_clients.is_retryable_gemini_error(
        RuntimeError("400 INVALID_ARGUMENT: embedding dimensions mismatch")
    )


def test_call_with_gemini_retry_retries_transient_errors_with_backoff():
    attempts = []
    sleeps = []

    def flaky_operation():
        attempts.append(len(attempts))
        if len(attempts) < 3:
            raise RuntimeError("429 rate limit exceeded")
        return "embedded"

    result = gemini_clients.call_with_gemini_retry(
        flaky_operation,
        description="test embed",
        sleep=sleeps.append,
    )

    assert result == "embedded"
    assert len(attempts) == 3
    assert len(sleeps) == 2
    assert sleeps[0] >= 1.0
    assert sleeps[1] >= 2.0
    assert sum(sleeps) <= 10.0


def test_call_with_gemini_retry_raises_immediately_on_permanent_errors():
    attempts = []

    def broken_operation():
        attempts.append(len(attempts))
        raise ValueError("invalid request payload")

    try:
        gemini_clients.call_with_gemini_retry(
            broken_operation,
            description="test embed",
            sleep=lambda _seconds: None,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("permanent errors should not be retried")

    assert len(attempts) == 1


def test_call_with_gemini_retry_gives_up_after_max_attempts():
    attempts = []
    sleeps = []

    def always_rate_limited():
        attempts.append(len(attempts))
        raise RuntimeError("429 rate limit exceeded")

    try:
        gemini_clients.call_with_gemini_retry(
            always_rate_limited,
            description="test embed",
            sleep=sleeps.append,
        )
    except RuntimeError as exc:
        assert "429" in str(exc)
    else:
        raise AssertionError("exhausted retries should re-raise the last error")

    assert len(attempts) == gemini_clients.GEMINI_RETRY_ATTEMPTS
    assert len(sleeps) == gemini_clients.GEMINI_RETRY_ATTEMPTS - 1
