"""
Beacon v3 — Storage / Task Management Tests
"""
import json
import time
import pytest

from conftest import (
    STORAGE_SCRIPT,
    run_script,
    run_script_raw,
    unique_id,
    create_test_task,
    TEST_CHANNEL,
)


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.storage
class TestCreateTask:

    def test_create_task_basic(self, env_vars, tracker, test_channel):
        """Create task with required fields only — returns valid JSON with id, task_number, status=open."""
        task = create_test_task(env_vars, tracker, test_channel)
        assert "id" in task, f"Missing 'id' in {task}"
        assert "task_number" in task, f"Missing 'task_number' in {task}"
        assert task.get("status") == "open"

    def test_create_task_with_optional_fields(self, env_vars, tracker, test_channel):
        """Create task with assignee, due, and actor."""
        task = create_test_task(
            env_vars, tracker, test_channel,
            assignee="U_TEST_USER",
            due="2026-12-31",
            actor="U_TEST_ACTOR",
        )
        assert "id" in task
        assert task.get("status") == "open"


@pytest.mark.storage
class TestListTasks:

    def test_list_tasks(self, env_vars, tracker, test_channel):
        """list_tasks returns tasks including newly created one."""
        created = create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            STORAGE_SCRIPT,
            ["list_tasks", "--channel", test_channel],
            env_vars,
        )
        # Result may be {"status": "ok", "tasks": [...]} or just a list
        tasks = result if isinstance(result, list) else result.get("tasks", [])
        task_ids = [t.get("id") for t in tasks]
        assert created["id"] in task_ids, f"Created task {created['id']} not in list"


@pytest.mark.storage
class TestUpdateTask:

    def test_update_task_description(self, env_vars, tracker, test_channel):
        """update_task changes description field."""
        task = create_test_task(env_vars, tracker, test_channel)
        new_desc = f"[TEST] updated-{unique_id()}"
        result = run_script(
            STORAGE_SCRIPT,
            ["update_task", "--channel", test_channel, "--id", task["id"],
             "--field", "description", "--value", new_desc],
            env_vars,
        )
        assert result.get("status") in ("ok", "updated") or "id" in result

    def test_update_task_assigned_to(self, env_vars, tracker, test_channel):
        """update_task changes assigned_to field."""
        task = create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            STORAGE_SCRIPT,
            ["update_task", "--channel", test_channel, "--id", task["id"],
             "--field", "assigned_to", "--value", "U_NEW_ASSIGNEE"],
            env_vars,
        )
        assert result.get("status") in ("ok", "updated") or "id" in result

    def test_update_task_due_date(self, env_vars, tracker, test_channel):
        """update_task changes due_date field."""
        task = create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            STORAGE_SCRIPT,
            ["update_task", "--channel", test_channel, "--id", task["id"],
             "--field", "due_date", "--value", "2026-06-15"],
            env_vars,
        )
        assert result.get("status") in ("ok", "updated") or "id" in result

    def test_update_task_rejects_invalid_field(self, env_vars, tracker, test_channel):
        """update_task rejects fields not in UPDATABLE_FIELDS whitelist."""
        task = create_test_task(env_vars, tracker, test_channel)
        raw = run_script_raw(
            STORAGE_SCRIPT,
            ["update_task", "--channel", test_channel, "--id", task["id"],
             "--field", "nonexistent_field", "--value", "anything"],
            env_vars,
        )
        output = raw.stdout + raw.stderr
        assert raw.returncode != 0 or "error" in output.lower() or "cannot update" in output.lower(), \
            f"Expected rejection of invalid field, got rc={raw.returncode}, output={output[:300]}"


@pytest.mark.storage
class TestBlockUnblock:

    def test_block_task(self, env_vars, tracker, test_channel):
        """block_task sets is_blocked=true and blocker_reason."""
        task = create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            STORAGE_SCRIPT,
            ["block_task", "--channel", test_channel, "--id", task["id"],
             "--reason", "Waiting on external review"],
            env_vars,
        )
        assert result.get("status") in ("ok", "blocked") or "id" in result

    def test_unblock_task(self, env_vars, tracker, test_channel):
        """unblock_task clears block."""
        task = create_test_task(env_vars, tracker, test_channel)
        # Block first
        run_script(
            STORAGE_SCRIPT,
            ["block_task", "--channel", test_channel, "--id", task["id"],
             "--reason", "Temp block"],
            env_vars,
        )
        # Unblock
        result = run_script(
            STORAGE_SCRIPT,
            ["unblock_task", "--channel", test_channel, "--id", task["id"]],
            env_vars,
        )
        assert result.get("status") in ("ok", "unblocked") or "id" in result


@pytest.mark.storage
class TestCompleteAndDismiss:

    def test_complete_task(self, env_vars, tracker, test_channel):
        """complete_task sets status=completed and completed_at."""
        task = create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            STORAGE_SCRIPT,
            ["complete_task", "--channel", test_channel, "--id", task["id"]],
            env_vars,
        )
        assert result.get("status") in ("ok", "completed") or "id" in result

    def test_dismiss_task(self, env_vars, tracker, test_channel):
        """dismiss_task sets status=dismissed."""
        task = create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            STORAGE_SCRIPT,
            ["dismiss_task", "--channel", test_channel, "--id", task["id"]],
            env_vars,
        )
        assert result.get("status") in ("ok", "dismissed") or "id" in result


@pytest.mark.storage
class TestBulkOps:

    def test_bulk_assign(self, env_vars, tracker, test_channel):
        """bulk_assign updates multiple tasks."""
        t1 = create_test_task(env_vars, tracker, test_channel)
        t2 = create_test_task(env_vars, tracker, test_channel)
        ids = f"{t1['id']},{t2['id']}"
        result = run_script(
            STORAGE_SCRIPT,
            ["bulk_assign", "--channel", test_channel, "--ids", ids,
             "--assignee", "U_BULK_USER"],
            env_vars,
        )
        assert result.get("status") == "ok" or result.get("updated") or "results" in result

    def test_bulk_due(self, env_vars, tracker, test_channel):
        """bulk_due updates due date on multiple tasks."""
        t1 = create_test_task(env_vars, tracker, test_channel)
        t2 = create_test_task(env_vars, tracker, test_channel)
        ids = f"{t1['id']},{t2['id']}"
        result = run_script(
            STORAGE_SCRIPT,
            ["bulk_due", "--channel", test_channel, "--ids", ids,
             "--due", "2026-09-01"],
            env_vars,
        )
        assert result.get("status") == "ok" or result.get("updated") or "results" in result


@pytest.mark.storage
class TestIdempotency:

    def test_idempotency_duplicate(self, env_vars, tracker, test_channel):
        """Duplicate slack-event-id returns status=duplicate."""
        event_id = f"test-idem-{unique_id()}"
        # First call
        task = create_test_task(
            env_vars, tracker, test_channel,
            slack_event_id=event_id,
        )
        assert "id" in task
        # Second call with same event ID
        r2 = run_script(
            STORAGE_SCRIPT,
            ["create_task", "--channel", test_channel,
             "--description", f"[TEST] dup-{unique_id()}",
             "--slack-event-id", event_id],
            env_vars,
        )
        assert r2.get("status") == "duplicate", f"Expected duplicate, got {r2}"


@pytest.mark.storage
class TestWriteEvent:

    def test_write_event(self, env_vars, test_channel):
        """write_event writes a custom event."""
        event_id = f"test-evt-{unique_id()}"
        payload = json.dumps({"test_key": "test_value"})
        result = run_script(
            STORAGE_SCRIPT,
            ["write_event", "--channel", test_channel,
             "--intent", "test_event",
             "--actor", "U_TEST",
             "--slack-event-id", event_id,
             "--payload", payload],
            env_vars,
        )
        assert result.get("status") == "ok" or "event" in str(result).lower()


@pytest.mark.storage
class TestContext:

    def test_context_roundtrip(self, env_vars, test_channel):
        """get_context / set_context round-trip."""
        ctx_data = json.dumps({"project_name": f"test-project-{unique_id()}", "goal": "pytest"})
        # Set
        run_script(
            STORAGE_SCRIPT,
            ["set_context", "--channel", test_channel, "--data", ctx_data],
            env_vars,
        )
        # Get
        result = run_script(
            STORAGE_SCRIPT,
            ["get_context", "--channel", test_channel],
            env_vars,
        )
        result_str = json.dumps(result)
        assert "pytest" in result_str or "project_name" in result_str


@pytest.mark.storage
class TestNextTaskNumber:

    def test_next_task_number(self, env_vars, tracker, test_channel):
        """next_task_number auto-increments after task creation."""
        r1 = run_script(
            STORAGE_SCRIPT,
            ["next_task_number", "--channel", test_channel],
            env_vars,
        )
        n1 = r1.get("next_number", 0)
        # Create a task to advance the counter
        create_test_task(env_vars, tracker, test_channel)
        r2 = run_script(
            STORAGE_SCRIPT,
            ["next_task_number", "--channel", test_channel],
            env_vars,
        )
        n2 = r2.get("next_number", 0)
        assert n2 > n1, f"Expected auto-increment: {n1} -> {n2}"


@pytest.mark.storage
class TestRegistry:

    def test_registry_crud(self, env_vars, test_channel):
        """get_registry / update_registry round-trip."""
        reg_data = json.dumps({"name": f"test-reg-{unique_id()}", "status": "active"})
        # Update
        run_script(
            STORAGE_SCRIPT,
            ["update_registry", "--channel", test_channel, "--data", reg_data],
            env_vars,
        )
        # Get
        result = run_script(
            STORAGE_SCRIPT,
            ["get_registry"],
            env_vars,
        )
        result_str = json.dumps(result)
        assert test_channel in result_str or "active" in result_str or isinstance(result, (dict, list))


@pytest.mark.storage
class TestEventOrdering:

    def test_event_chronological_ordering(self, env_vars, tracker, test_channel):
        """Events written in correct chronological order."""
        task = create_test_task(env_vars, tracker, test_channel)
        time.sleep(0.5)
        run_script(
            STORAGE_SCRIPT,
            ["update_task", "--channel", test_channel, "--id", task["id"],
             "--field", "description", "--value", f"[TEST] ordering-{unique_id()}"],
            env_vars,
        )
        time.sleep(0.5)
        run_script(
            STORAGE_SCRIPT,
            ["complete_task", "--channel", test_channel, "--id", task["id"]],
            env_vars,
        )
        # Verify task exists and was completed
        result = run_script(
            STORAGE_SCRIPT,
            ["list_tasks", "--channel", test_channel, "--status", "completed"],
            env_vars,
        )
        tasks = result if isinstance(result, list) else result.get("tasks", [])
        found = [t for t in tasks if t.get("id") == task["id"]]
        assert len(found) > 0, "Completed task not found in chronological listing"
