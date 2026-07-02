import pytest

from backend.rag import resolve_retrieval_mode


class TestResolveRetrievalMode:
    def test_explicit_modes_pass_through(self):
        assert resolve_retrieval_mode("anything", "hybrid") == "hybrid"
        assert resolve_retrieval_mode("anything", "semantic") == "semantic"
        assert resolve_retrieval_mode("anything", "keyword") == "keyword"

    def test_auto_routes_plain_queries_to_hybrid(self):
        assert resolve_retrieval_mode("how does self-distillation work", "auto") == "hybrid"
        assert resolve_retrieval_mode("GRPO reward hacking", "auto") == "hybrid"

    def test_auto_routes_quoted_phrases_to_keyword(self):
        assert resolve_retrieval_mode('find "on-policy distillation" clips', "auto") == "keyword"
        assert resolve_retrieval_mode('"KV cache"', "auto") == "keyword"

    def test_auto_routes_curly_quoted_phrases_to_keyword(self):
        assert resolve_retrieval_mode("find “on-policy distillation”", "auto") == "keyword"

    def test_auto_ignores_trivial_or_unbalanced_quotes(self):
        assert resolve_retrieval_mode('the "a" flag', "auto") == "hybrid"
        assert resolve_retrieval_mode('unbalanced " quote', "auto") == "hybrid"

    def test_missing_mode_defaults_to_hybrid(self):
        assert resolve_retrieval_mode("anything", None) == "hybrid"
        assert resolve_retrieval_mode("anything", "") == "hybrid"

    def test_mode_is_case_insensitive(self):
        assert resolve_retrieval_mode('find "exact words"', "AUTO") == "keyword"

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="auto, hybrid, semantic, keyword"):
            resolve_retrieval_mode("anything", "smart")
