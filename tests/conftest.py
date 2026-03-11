"""
Beacon v3 Test Framework — Shared Fixtures & Helpers
"""
import json
import os
import subprocess
import uuid

import pytest

# ---------------------------------------------------------------------------
# Script paths
# ---------------------------------------------------------------------------
SCRIPTS_BASE = os.path.expanduser(
    "~/.openclaw/agents/beacon/workspace/skills"
)
STORAGE_SCRIPT = os.path.join(SCRIPTS_BASE, "tasks/scripts/storage.py")
RISK_SCRIPT = os.path.join(SCRIPTS_BASE, "risk/scripts/risk.py")
JIRA_SCRIPT = os.path.join(SCRIPTS_BASE, "jira/scripts/jira_api.py")
SEARCH_SCRIPT = os.path.join(SCRIPTS_BASE, "search/scripts/search.py")

# ---------------------------------------------------------------------------
# Environment — test channel + secrets
# ---------------------------------------------------------------------------
TEST_CHANNEL = os.environ.get("C_TEST_BEACON", "C07BFGJ6M26")


def _read_secret(name: str) -> str:
    path = os.path.expanduser(f"~/.secrets/{name}")
    with open(path) as f:
        return f.read().strip()


@pytest.fixture(scope="session")
def telnyx_api_key():
    return _read_secret("telnyx")


@pytest.fixture(scope="session")
def jira_email():
    return _read_secret("jira-email")


@pytest.fixture(scope="session")
def jira_token():
    return _read_secret("jira-token")


@pytest.fixture(scope="session")
def test_channel():
    return TEST_CHANNEL


@pytest.fixture(scope="session")
def env_vars(telnyx_api_key, jira_email, jira_token):
    """Return env dict with all required secrets for subprocess calls."""
    env = os.environ.copy()
    env["TELNYX_API_KEY"] = telnyx_api_key
    env["JIRA_EMAIL"] = jira_email
    env["JIRA_TOKEN"] = jira_token
    return env


# ---------------------------------------------------------------------------
# Subprocess helper — runs a script, parses JSON from stdout
# ---------------------------------------------------------------------------
def run_script(script: str, args: list, env: dict, expect_success: bool = True) -> dict:
    """Run a CLI script, parse JSON from stdout, ignore stderr (deprecation warnings)."""
    cmd = ["python3", script] + [str(a) for a in args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(
            f"Script failed (rc={result.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr[:500]}\n"
            f"  stdout: {result.stdout[:500]}"
        )
    # Parse JSON from stdout only
    stdout = result.stdout.strip()
    if not stdout:
        return {"_raw": "", "_returncode": result.returncode, "_stderr": result.stderr}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        # Sometimes stdout has non-JSON prefix lines; try last line
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") or line.startswith("["):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return {"_raw": stdout, "_returncode": result.returncode, "_stderr": result.stderr}


def run_script_raw(script: str, args: list, env: dict) -> subprocess.CompletedProcess:
    """Run a script and return the raw CompletedProcess (for error-path testing)."""
    cmd = ["python3", script] + [str(a) for a in args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)


# ---------------------------------------------------------------------------
# Unique ID helper for test isolation
# ---------------------------------------------------------------------------
def unique_id() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Task creation helper — unwraps nested response
# ---------------------------------------------------------------------------
def create_test_task(env_vars, tracker, test_channel, desc=None, **kwargs):
    """Create a task and register it for cleanup. Returns the task dict (unwrapped)."""
    desc = desc or f"[TEST] pytest-{unique_id()}"
    args = ["create_task", "--channel", test_channel, "--description", desc]
    for k, v in kwargs.items():
        args.extend([f"--{k.replace('_', '-')}", str(v)])
    result = run_script(STORAGE_SCRIPT, args, env_vars)
    # Unwrap: create_task returns {"status": "created", "task": {...}}
    task = result.get("task", result)
    if "id" in task:
        tracker.add_task(task["id"])
    return task


# ---------------------------------------------------------------------------
# Task cleanup tracker
# ---------------------------------------------------------------------------
class TaskTracker:
    """Tracks task IDs created during tests for cleanup."""

    def __init__(self):
        self.task_ids: list[str] = []
        self.jira_keys: list[str] = []

    def add_task(self, task_id: str):
        self.task_ids.append(task_id)

    def add_jira(self, key: str):
        self.jira_keys.append(key)


@pytest.fixture(scope="session")
def tracker():
    return TaskTracker()


@pytest.fixture(autouse=True, scope="session")
def cleanup_test_data(tracker, env_vars, test_channel):
    """Session-scoped cleanup: dismiss all test tasks and delete test JIRA issues after all tests."""
    yield
    # --- cleanup tasks ---
    for task_id in tracker.task_ids:
        try:
            run_script(
                STORAGE_SCRIPT,
                ["dismiss_task", "--channel", test_channel, "--id", task_id],
                env_vars,
                expect_success=False,
            )
        except Exception:
            pass
    # --- cleanup jira issues ---
    for jira_key in tracker.jira_keys:
        try:
            # Delete via JIRA REST API directly (jira_api.py has no delete command)
            import urllib.request

            jira_email = env_vars.get("JIRA_EMAIL", "")
            jira_token = env_vars.get("JIRA_TOKEN", "")
            import base64

            creds = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
            req = urllib.request.Request(
                f"https://telnyx.atlassian.net/rest/api/3/issue/{jira_key}",
                method="DELETE",
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/json",
                },
            )
            urllib.request.urlopen(req, timeout=15)
        except Exception:
            pass
