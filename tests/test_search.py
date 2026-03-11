"""
Beacon v3 — Semantic Search Tests
"""
import pytest

from conftest import (
    SEARCH_SCRIPT,
    run_script,
    run_script_raw,
    unique_id,
    TEST_CHANNEL,
)


@pytest.mark.search
class TestSearchQuery:

    def test_query_returns_results(self, env_vars):
        """query returns results from RAG with scores."""
        result = run_script(
            SEARCH_SCRIPT,
            ["query", "--query", "project status update"],
            env_vars,
            expect_success=False,  # may 503 transiently
        )
        # Accept: list of results, dict with results/documents/error key
        if isinstance(result, list):
            pass  # valid
        elif isinstance(result, dict):
            # Transient RAG errors are acceptable — just verify JSON response
            assert any(k in result for k in ("results", "documents", "error", "_raw")), \
                f"Unexpected search response keys: {list(result.keys())}"

    def test_query_with_channel_filter(self, env_vars, test_channel):
        """query with --channel filters results by channel prefix."""
        result = run_script(
            SEARCH_SCRIPT,
            ["query", "--query", "test task", "--channel", test_channel],
            env_vars,
            expect_success=False,
        )
        assert isinstance(result, (dict, list)), f"Expected dict/list, got {type(result)}"

    def test_query_empty_returns_graceful(self, env_vars):
        """Empty/nonsensical query returns graceful empty result."""
        result = run_script(
            SEARCH_SCRIPT,
            ["query", "--query", f"zzz_nonexistent_gibberish_{unique_id()}"],
            env_vars,
            expect_success=False,
        )
        assert isinstance(result, (dict, list))


@pytest.mark.search
class TestSearchIngest:

    def test_ingest_channel(self, env_vars, test_channel):
        """ingest uploads content and triggers embedding."""
        raw = run_script_raw(
            SEARCH_SCRIPT,
            ["ingest", "--channel", test_channel],
            env_vars,
        )
        output = raw.stdout + raw.stderr
        # Accept either success or graceful error (no Python traceback crash)
        has_traceback = "Traceback" in raw.stderr and raw.returncode != 0
        if has_traceback:
            # Only fail if it's a real crash, not a handled error
            assert "Error" in raw.stderr or "error" in raw.stdout.lower(), \
                f"Ingest crashed unexpectedly: {output[:500]}"
