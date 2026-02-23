from src.eva_platform.monitoring_service import (
    classify_http_status,
    classify_issue_severity,
    compute_streaks,
)


def test_classify_http_status():
    assert classify_http_status(200) == "up"
    assert classify_http_status(302) == "up"
    assert classify_http_status(429) == "degraded"
    assert classify_http_status(500) == "down"


def test_compute_streaks_success_resets_failures():
    failures, successes = compute_streaks(3, 0, "up")
    assert failures == 0
    assert successes == 1


def test_compute_streaks_failure_resets_successes():
    failures, successes = compute_streaks(1, 5, "down")
    assert failures == 2
    assert successes == 0


def test_classify_issue_severity():
    assert classify_issue_severity("down", True) == "critical"
    assert classify_issue_severity("degraded", True) == "high"
    assert classify_issue_severity("down", False) == "high"
    assert classify_issue_severity("degraded", False) == "medium"
    assert classify_issue_severity("up", False) == "low"
