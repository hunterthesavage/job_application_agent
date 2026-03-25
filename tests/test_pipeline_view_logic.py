from views.pipeline import _wizard_first_run_has_results


def test_wizard_first_run_has_results_for_net_new_jobs():
    result = {
        "ingest": {
            "summary": {
                "inserted_count": 2,
                "updated_count": 0,
                "net_new_count": 2,
                "rediscovered_count": 0,
            }
        }
    }

    assert _wizard_first_run_has_results(result) is True


def test_wizard_first_run_has_results_for_rediscovered_jobs():
    result = {
        "ingest": {
            "summary": {
                "inserted_count": 0,
                "updated_count": 1,
                "net_new_count": 0,
                "rediscovered_count": 1,
            }
        }
    }

    assert _wizard_first_run_has_results(result) is True


def test_wizard_first_run_has_results_false_when_nothing_changed():
    result = {
        "ingest": {
            "summary": {
                "inserted_count": 0,
                "updated_count": 0,
                "net_new_count": 0,
                "rediscovered_count": 0,
            }
        }
    }

    assert _wizard_first_run_has_results(result) is False
