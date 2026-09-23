"""Tests for chunking stability and BM25 sanity."""

from inbox_agent.retrieval import build_index, chunk_markdown


def test_policy_chunk_ids_are_stable():
    ids = [c.chunk_id for c in chunk_markdown("corpus/exec_preferences.md")]
    assert "exec_preferences#1-calendar-rules" in ids
    assert "exec_preferences#3-delegation-rules" in ids
    assert "exec_preferences#4-confidentiality" in ids


def test_search_returns_relevant_section_first():
    index = build_index("corpus")
    top = index.search("who handles invoices and billing", k=1)[0][0]
    assert top.chunk_id == "exec_preferences#3-delegation-rules"


def test_search_handles_unknown_terms():
    index = build_index("corpus")
    results = index.search("zzz qqq xyzzy", k=3)
    assert len(results) == 3  # degrades gracefully, no crash
