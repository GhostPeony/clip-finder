from backend.category_taxonomy import (
    CATEGORY_FACETS,
    category_filter_examples,
    get_category_taxonomy,
)


def test_category_taxonomy_is_universal_across_youtube_topics():
    taxonomy = get_category_taxonomy()

    domain_examples = set(CATEGORY_FACETS["domain"]["examples"])
    task_examples = set(CATEGORY_FACETS["task_fit"]["examples"])
    tool_description = CATEGORY_FACETS["tool"]["description"]
    examples = category_filter_examples()

    assert {"cooking", "history", "home repair", "music", "fitness"}.issubset(domain_examples)
    assert {"study guide", "lesson plan", "troubleshooting", "buying decision"}.issubset(
        task_examples
    )
    assert "physical tool" in tool_description
    assert any(example.get("task_fit") == ["study guide"] for example in examples)
    assert any(example.get("task_fit") == ["troubleshooting"] for example in examples)
    assert "topic" in taxonomy["recommendedAgentFlow"][1]
