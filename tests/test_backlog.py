def test_backlog_summary_contains_expected_priority_buckets():
    from services.backlog import get_backlog_summary

    summary = get_backlog_summary()

    assert summary["soft_launch_percent"] >= 0
    assert set(summary["counts"].keys()) == {"High", "Medium", "Low"}
    assert set(summary["items_by_priority"].keys()) == {"High", "Medium", "Low"}
    assert len(summary["items_by_priority"]["High"]) >= 1
    assert len(summary["recently_completed"]) >= 1
