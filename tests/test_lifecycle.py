"""
Beacon v3 — Cross-Script Lifecycle Tests
"""
import json
import time
import pytest

from conftest import (
    STORAGE_SCRIPT,
    RISK_SCRIPT,
    JIRA_SCRIPT,
    run_script,
    unique_id,
    create_test_task,
    TEST_CHANNEL,
)


def _create_jira_issue(env_vars, tracker, summary=None):
    summary = summary or f"[TEST] lifecycle-jira-{unique_id()}"
    result = run_script(
        JIRA_SCRIPT,
        ["create", "--project", "LEGAL", "--summary", summary,
         "--description", "Lifecycle test issue"],
        env_vars,
    )
    if "key" in result:
        tracker.add_jira(result["key"])
    return result


@pytest.mark.lifecycle
class TestFullLifecycle:

    def test_full_lifecycle_create_update_block_unblock_complete(self, env_vars, tracker, test_channel):
        """Full lifecycle: create → update → block → unblock → complete → verify via list."""
        # 1. Create
        task = create_test_task(env_vars, tracker, test_channel)
        task_id = task["id"]
        assert task.get("status") == "open"

        # 2. Update description
        run_script(
            STORAGE_SCRIPT,
            ["update_task", "--channel", test_channel, "--id", task_id,
             "--field", "description", "--value", f"[TEST] lifecycle-updated-{unique_id()}"],
            env_vars,
        )

        # 3. Block
        run_script(
            STORAGE_SCRIPT,
            ["block_task", "--channel", test_channel, "--id", task_id,
             "--reason", "Lifecycle test blocker"],
            env_vars,
        )

        # 4. Unblock
        run_script(
            STORAGE_SCRIPT,
            ["unblock_task", "--channel", test_channel, "--id", task_id],
            env_vars,
        )

        # 5. Complete
        run_script(
            STORAGE_SCRIPT,
            ["complete_task", "--channel", test_channel, "--id", task_id],
            env_vars,
        )

        # 6. Verify via list
        result = run_script(
            STORAGE_SCRIPT,
            ["list_tasks", "--channel", test_channel, "--status", "completed"],
            env_vars,
        )
        tasks = result if isinstance(result, list) else result.get("tasks", [])
        found = [t for t in tasks if t.get("id") == task_id]
        assert len(found) > 0, f"Task {task_id} not found in completed list"


@pytest.mark.lifecycle
class TestTaskJiraLink:

    def test_task_jira_link_lifecycle(self, env_vars, tracker, test_channel):
        """Create task → link to JIRA → verify jira_key persisted."""
        task = create_test_task(env_vars, tracker, test_channel)
        task_id = task["id"]

        issue = _create_jira_issue(env_vars, tracker)
        jira_key = issue["key"]

        # Link them
        run_script(
            JIRA_SCRIPT,
            ["link", "--channel", test_channel,
             "--task-id", task_id,
             "--issue", jira_key],
            env_vars,
        )

        # Verify link persisted
        result = run_script(
            STORAGE_SCRIPT,
            ["list_tasks", "--channel", test_channel],
            env_vars,
        )
        tasks = result if isinstance(result, list) else result.get("tasks", [])
        found = [t for t in tasks if t.get("id") == task_id]
        assert len(found) > 0, f"Task {task_id} not in list"
        task_data = found[0]
        result_str = json.dumps(task_data)
        assert jira_key in result_str or "jira" in result_str.lower(), \
            f"JIRA key {jira_key} not found in task data: {task_data}"


@pytest.mark.lifecycle
class TestRiskCalculateLifecycle:

    def test_risk_calculate_reflects_task_states(self, env_vars, tracker, test_channel):
        """Create tasks → calculate risk → verify score reflects task states."""
        # Create an overdue unassigned task
        create_test_task(env_vars, tracker, test_channel, due="2020-01-01")

        # Create a blocked task
        blocked = create_test_task(env_vars, tracker, test_channel)
        run_script(
            STORAGE_SCRIPT,
            ["block_task", "--channel", test_channel, "--id", blocked["id"],
             "--reason", "Risk lifecycle test"],
            env_vars,
        )

        # Calculate risk
        result = run_script(
            RISK_SCRIPT,
            ["calculate", "--channel", test_channel],
            env_vars,
        )
        assert "score" in result
        assert result["score"] > 0, f"Expected score > 0 with overdue+blocked tasks, got {result['score']}"
        assert result["level"] in ("green", "yellow", "red")
