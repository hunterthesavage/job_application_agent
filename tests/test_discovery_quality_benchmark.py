from pathlib import Path


def test_build_report_summary_includes_validation_metrics():
    from scripts.run_local_discovery_debug import _build_report_summary

    summary = _build_report_summary(
        {
            "status": "completed",
            "url_count": 12,
            "providers": {"search": 12},
            "next_gen_seed_urls": ["https://jobs.example.com/1"],
            "next_gen_supported_seeds_scanned": 2,
            "next_gen_unsupported_seeds_skipped": 1,
            "drop_summary": {"search": {"blocked_domain": 3}},
        },
        label="demo",
        source_layer_mode="next_gen",
        use_ai_title_expansion=False,
        report_dir=Path("/tmp/demo"),
        validation_result={
            "accepted_jobs": 4,
            "seen_urls": 10,
            "skipped_count": 5,
            "skipped_title_prefilter_count": 2,
            "skipped_duplicate_batch_count": 1,
            "error_count": 1,
            "seeded_accepted_jobs": 1,
            "legacy_accepted_jobs": 3,
            "skip_summary": {"stale_ats_posting": 1},
            "build_seconds": 1.25,
            "ingest_seconds": 0.75,
        },
    )

    assert summary["accepted_jobs"] == 4
    assert summary["validation_skipped_count"] == 5
    assert summary["validation_skip_summary"] == {"stale_ats_posting": 1}
    assert summary["validation_build_seconds"] == 1.25
    assert summary["drop_summary"] == {"search": {"blocked_domain": 3}}


def test_quality_benchmark_group_summary_flags_variant_sensitivity():
    from scripts.run_discovery_quality_benchmark import _overall_summary, _summarize_groups

    rows = [
        {
            "group": "it_director_variants",
            "variant": "director",
            "title": "Director of IT",
            "normalized_urls": ["https://jobs.example.com/1", "https://jobs.example.com/2"],
            "accepted_jobs": 4,
            "broken_url_count": 0,
            "url_count": 2,
            "seen_urls": 2,
            "blocked_domain_drop_count": 0,
            "weak_title_match_count": 0,
        },
        {
            "group": "it_director_variants",
            "variant": "dir",
            "title": "Dir of IT",
            "normalized_urls": ["https://jobs.example.com/2", "https://jobs.example.com/3"],
            "accepted_jobs": 1,
            "broken_url_count": 2,
            "url_count": 2,
            "seen_urls": 2,
            "blocked_domain_drop_count": 1,
            "weak_title_match_count": 1,
        },
    ]

    groups = _summarize_groups(rows)
    overall = _overall_summary(rows, groups)

    assert groups == [
        {
            "group": "it_director_variants",
            "variants": ["dir", "director"],
            "titles": ["Dir of IT", "Director of IT"],
            "shared_url_count": 1,
            "union_url_count": 3,
            "overlap_rate": 33.3,
            "accepted_gap": 3,
            "broken_gap": 2,
        }
    ]
    assert overall["variant_sensitive_group_count"] == 1
    assert overall["variant_sensitive_groups"] == ["it_director_variants"]


def test_compare_quality_benchmark_markdown_reports_deltas():
    from scripts.compare_discovery_quality_benchmarks import _render_markdown

    markdown = _render_markdown(
        {
            "overall": {
                "total_urls": 10,
                "total_accepted_jobs": 4,
                "overall_acceptance_rate": 40.0,
                "total_broken_urls": 2,
                "total_blocked_domain_drops": 1,
                "total_weak_title_matches": 3,
            },
            "rows": [
                {
                    "title": "Director of IT",
                    "url_count": 6,
                    "accepted_jobs": 3,
                    "broken_url_count": 1,
                    "blocked_domain_drop_count": 1,
                    "weak_title_match_count": 2,
                }
            ],
            "groups": [
                {
                    "group": "it_director_variants",
                    "overlap_rate": 70.0,
                    "accepted_gap": 1,
                    "broken_gap": 0,
                }
            ],
        },
        {
            "overall": {
                "total_urls": 14,
                "total_accepted_jobs": 5,
                "overall_acceptance_rate": 35.7,
                "total_broken_urls": 3,
                "total_blocked_domain_drops": 2,
                "total_weak_title_matches": 1,
            },
            "rows": [
                {
                    "title": "Director of IT",
                    "url_count": 8,
                    "accepted_jobs": 4,
                    "broken_url_count": 2,
                    "blocked_domain_drop_count": 2,
                    "weak_title_match_count": 0,
                }
            ],
            "groups": [
                {
                    "group": "it_director_variants",
                    "overlap_rate": 55.0,
                    "accepted_gap": 2,
                    "broken_gap": 1,
                }
            ],
        },
    )

    assert "Total discovered URLs: 14 (+4)" in markdown
    assert "| Director of IT | +2 | +1 | +1 | +1 | -2 |" in markdown
    assert "| it_director_variants | -15.0 | +1 | +1 |" in markdown
