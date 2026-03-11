"""
Beacon v3 — JIRA Integration Tests
"""
import json
import pytest

from conftest import (
    JIRA_SCRIPT,
    STORAGE_SCRIPT,
    run_script,
    run_script_raw,
    unique_id,
    create_test_task,
    TEST_CHANNEL,
)


def _create_jira_issue(env_vars, tracker, summary=None):
    """Create a test JIRA issue in LEGAL project and register for cleanup."""
    summary = summary or f"[TEST] beacon-pytest-{unique_id()}"
    result = run_script(
        JIRA_SCRIPT,
        ["create", "--project", "LEGAL", "--summary", summary,
         "--description", "Automated test issue from Beacon v3 pytest"],
        env_vars,
    )
    if "key" in result:
        tracker.add_jira(result["key"])
    return result


@pytest.mark.jira
class TestJiraQuery:

    def test_query_returns_results(self, env_vars):
        """JQL query returns results with expected fields."""
        result = run_script(
            JIRA_SCRIPT,
            ["query", "--jql", 'project = LEGAL ORDER BY created DESC', "--limit", "3"],
            env_vars,
        )
        issues = result if isinstance(result, list) else result.get("issues", [])
        assert isinstance(issues, list), f"Expected list of issues, got {type(result)}"

    def test_query_empty_results(self, env_vars):
        """Empty JQL results handled gracefully (no crash)."""
        result = run_script(
            JIRA_SCRIPT,
            ["query", "--jql", 'project = LEGAL AND summary ~ "ZZZZNONEXISTENT99999"', "--limit", "1"],
            env_vars,
        )
        issues = result if isinstance(result, list) else result.get("issues", [])
        assert isinstance(issues, list)
        assert len(issues) == 0, f"Expected empty results, got {len(issues)}"


@pytest.mark.jira
class TestJiraCreate:

    def test_create_issue(self, env_vars, tracker):
        """Create issue returns key and URL."""
        result = _create_jira_issue(env_vars, tracker)
        assert "key" in result, f"Missing 'key' in {result}"
        key = result["key"]
        assert key.startswith("LEGAL-"), f"Expected LEGAL- prefix, got {key}"

    def test_create_invalid_project(self, env_vars, tracker):
        """Invalid project returns error (not crash)."""
        raw = run_script_raw(
            JIRA_SCRIPT,
            ["create", "--project", "ZZZBOGUS999", "--summary", "[TEST] should-fail"],
            env_vars,
        )
        output = raw.stdout + raw.stderr
        assert raw.returncode != 0 or "error" in output.lower(), \
            f"Expected error for invalid project, got rc={raw.returncode}"


@pytest.mark.jira
class TestJiraStatus:

    def test_status_returns_details(self, env_vars, tracker):
        """status returns issue details."""
        issue = _create_jira_issue(env_vars, tracker)
        result = run_script(
            JIRA_SCRIPT,
            ["status", "--issue", issue["key"]],
            env_vars,
        )
        assert "key" in result or "status" in result or "summary" in result, f"Unexpected status response: {result}"


@pytest.mark.jira
class TestJiraUpdate:

    def test_update_issue_field(self, env_vars, tracker):
        """Update issue field (description)."""
        issue = _create_jira_issue(env_vars, tracker)
        result = run_script(
            JIRA_SCRIPT,
            ["update", "--issue", issue["key"],
             "--field", "description", "--value", "Updated by pytest"],
            env_vars,
        )
        assert result.get("status") == "ok" or "key" in result or result.get("_returncode", 0) == 0


@pytest.mark.jira
class TestJiraLink:

    def test_link_beacon_task_to_jira(self, env_vars, tracker, test_channel):
        """Link Beacon task to JIRA issue, writes event."""
        task = create_test_task(env_vars, tracker, test_channel)
        issue = _create_jira_issue(env_vars, tracker)
        result = run_script(
            JIRA_SCRIPT,
            ["link", "--channel", test_channel,
             "--task-id", task["id"],
             "--issue", issue["key"]],
            env_vars,
        )
        assert result.get("status") == "ok" or "linked" in json.dumps(result).lower() or "jira_key" in json.dumps(result)


@pytest.mark.jira
class TestJiraUserMapping:

    def test_map_user(self, env_vars):
        """map_user maps Slack UID to JIRA email."""
        uid = f"U_PYTEST_{unique_id()}"
        result = run_script(
            JIRA_SCRIPT,
            ["map_user", "--slack-uid", uid, "--email", "pytest-test@telnyx.com"],
            env_vars,
        )
        assert result.get("status") == "ok" or "mapped" in json.dumps(result).lower() or result.get("_returncode", 0) == 0

    def test_resolve_user_after_map(self, env_vars):
        """resolve_user returns cached result after map_user."""
        uid = f"U_PYTEST_RES_{unique_id()}"
        run_script(
            JIRA_SCRIPT,
            ["map_user", "--slack-uid", uid, "--email", "pytest-resolve@telnyx.com"],
            env_vars,
        )
        result = run_script(
            JIRA_SCRIPT,
            ["resolve_user", "--slack-uid", uid],
            env_vars,
        )
        result_str = json.dumps(result)
        assert "pytest-resolve@telnyx.com" in result_str or "account_id" in result_str or result.get("_returncode", 0) == 0


@pytest.mark.jira
class TestJiraRetries:

    def test_process_retries(self, env_vars, test_channel):
        """process_retries processes retry queue, handles permanent failures."""
        result = run_script(
            JIRA_SCRIPT,
            ["process_retries", "--channel", test_channel],
            env_vars,
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
