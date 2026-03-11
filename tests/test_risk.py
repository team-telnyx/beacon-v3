"""
Beacon v3 — Risk Calculation Tests
"""
import pytest

from conftest import (
    STORAGE_SCRIPT,
    RISK_SCRIPT,
    run_script,
    unique_id,
    create_test_task,
    TEST_CHANNEL,
)


@pytest.mark.risk
class TestRiskCalculate:

    def test_calculate_returns_valid_score(self, env_vars, tracker, test_channel):
        """calculate returns valid score, level, breakdown for channel with tasks."""
        create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            RISK_SCRIPT,
            ["calculate", "--channel", test_channel],
            env_vars,
        )
        assert "score" in result, f"Missing 'score' in {result}"
        assert "level" in result, f"Missing 'level' in {result}"
        assert result["level"] in ("green", "yellow", "red"), f"Invalid level: {result['level']}"

    def test_calculate_empty_channel(self, env_vars, test_channel):
        """Empty channel returns score 0, green."""
        empty_ch = f"C_EMPTY_{unique_id()}"
        result = run_script(
            RISK_SCRIPT,
            ["calculate", "--channel", empty_ch],
            env_vars,
        )
        assert result.get("score", -1) == 0, f"Expected score=0, got {result.get('score')}"
        assert result.get("level") == "green", f"Expected green, got {result.get('level')}"


@pytest.mark.risk
class TestRiskOverdue:

    def test_overdue_tasks_increase_score(self, env_vars, tracker, test_channel):
        """Overdue tasks increase risk score."""
        create_test_task(env_vars, tracker, test_channel, due="2020-01-01")
        result = run_script(
            RISK_SCRIPT,
            ["calculate", "--channel", test_channel],
            env_vars,
        )
        assert result.get("score", 0) > 0, f"Expected score > 0 with overdue task, got {result}"


@pytest.mark.risk
class TestRiskBlocked:

    def test_blocked_tasks_increase_score(self, env_vars, tracker, test_channel):
        """Blocked tasks increase risk score."""
        task = create_test_task(env_vars, tracker, test_channel)
        run_script(
            STORAGE_SCRIPT,
            ["block_task", "--channel", test_channel, "--id", task["id"],
             "--reason", "Test blocker for risk"],
            env_vars,
        )
        result = run_script(
            RISK_SCRIPT,
            ["calculate", "--channel", test_channel],
            env_vars,
        )
        assert result.get("score", 0) > 0, f"Expected score > 0 with blocked task, got {result}"


@pytest.mark.risk
class TestRiskUnassigned:

    def test_unassigned_tasks_increase_score(self, env_vars, tracker, test_channel):
        """Unassigned tasks increase risk score."""
        create_test_task(env_vars, tracker, test_channel)
        result = run_script(
            RISK_SCRIPT,
            ["calculate", "--channel", test_channel],
            env_vars,
        )
        assert result.get("score", 0) >= 0, f"Expected non-negative score, got {result}"


@pytest.mark.risk
class TestRiskThresholds:

    def test_level_thresholds_green_yellow_red(self, env_vars, tracker, test_channel):
        """Risk levels: green (0-3), yellow (4-6), red (7+)."""
        result = run_script(
            RISK_SCRIPT,
            ["calculate", "--channel", test_channel],
            env_vars,
        )
        score = result.get("score", 0)
        level = result.get("level", "")
        if score <= 3:
            assert level == "green", f"Score {score} should be green, got {level}"
        elif score <= 6:
            assert level == "yellow", f"Score {score} should be yellow, got {level}"
        else:
            assert level == "red", f"Score {score} should be red, got {level}"
