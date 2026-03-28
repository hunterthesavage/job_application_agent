from __future__ import annotations

from collections import Counter


SOFT_LAUNCH_PERCENT = 91


BACKLOG_ITEMS: list[dict[str, str]] = [
    {
        "priority": "High",
        "title": "Validate Windows install on a real machine",
        "detail": "The Windows launchers exist, but they still need a real runtime install and launch pass instead of only code review.",
    },
    {
        "priority": "High",
        "title": "Complete the with-AI acceptance pass",
        "detail": "Run a full first-time flow with a real OpenAI key and confirm title expansion, scoring, scrub, and cover letters all behave as expected.",
    },
    {
        "priority": "High",
        "title": "Run one external friend test without hand-holding",
        "detail": "Have one tester install, onboard, run discovery, review roles, and report confusion points without extra explanation from you.",
    },
    {
        "priority": "High",
        "title": "Fix only launch blockers from real-user feedback",
        "detail": "Use the next tester pass to close confusion loops, persistence bugs, or broken install steps instead of adding new product scope.",
    },
    {
        "priority": "Medium",
        "title": "Match the Setup Wizard Profile Context flow to Settings",
        "detail": "Bring the same step-driven 1-2-3 visual treatment into the wizard so profile setup feels consistent everywhere.",
    },
    {
        "priority": "Medium",
        "title": "Review long-run busy and reset behavior",
        "detail": "Double-check how discovery and rescoring communicate progress, long waits, and recovery when a run takes longer than expected.",
    },
    {
        "priority": "Medium",
        "title": "Clarify combined AI toggle behavior in Pipeline",
        "detail": "The single run-level AI toggle is simpler, but the page may still need clearer wording for actions like Find Job Links Only that only use part of it.",
    },
    {
        "priority": "Medium",
        "title": "Fix inaccurate duration timing in run results",
        "detail": "The Duration timer is not always reflecting real elapsed time. This should be tightened so Pipeline results and status views feel trustworthy.",
    },
    {
        "priority": "Medium",
        "title": "Add a Fortune 500 career-site registry and filter",
        "detail": "Integrate a curated Fortune 500 URL list for company career sites, use it as a higher-signal discovery source similar to ATS seed sources, let it act as a ranking signal for trusted enterprise employers, and add user-facing controls such as Prefer Fortune 500 and Only show Fortune 500 jobs.",
    },
    {
        "priority": "Medium",
        "title": "Expand discovery beyond the Fortune 500 seed set",
        "detail": "Build broader employer and ATS endpoint coverage beyond the Fortune 500 list so discovery does not overfit to only large public companies. Treat the Fortune 500 registry as one high-signal seed lane, not the whole source universe.",
    },
    {
        "priority": "Medium",
        "title": "Add direct API integrations for more discovery sources",
        "detail": "Evaluate direct API integrations that can pull additional job URLs into the pipeline so the app can score more high-quality roles without depending only on search and current ATS-source coverage.",
    },
    {
        "priority": "Medium",
        "title": "Decide whether environment-key fallback should stay",
        "detail": "The app now explains saved versus environment keys clearly, but public users may still benefit from an even simpler saved-local-key-only model.",
    },
    {
        "priority": "Medium",
        "title": "Surface OpenAI usage, token, and cost visibility",
        "detail": "Add a read-only app view that shows OpenAI usage for the configured key, including token consumption, cost, and helpful links back to OpenAI billing or usage pages. This may also apply to the related source-layer project if both products rely on the same key-management expectations.",
    },
    {
        "priority": "Low",
        "title": "Tighten internal docs after launch hardening",
        "detail": "Refresh architecture, current-state, and settings-reference docs so they reflect the current app instead of earlier build phases.",
    },
    {
        "priority": "Low",
        "title": "Clean up remaining packaging and dependency rough edges",
        "detail": "Keep reviewing setup assumptions, optional dependencies, and platform notes after the soft-launch path is proven.",
    },
    {
        "priority": "Low",
        "title": "Revisit orchestration boundaries after soft launch",
        "detail": "Session state, view code, and runtime services still carry some operator complexity that is acceptable now but will be a future scaling constraint.",
    },
]


RECENTLY_COMPLETED: list[str] = [
    "Public experimental repo prep and README install cleanup",
    "Pipeline split into calmer subpages with clearer run, results, and research flows",
    "Settings cleanup with a dedicated System Status section",
    "Resume-driven Profile Context generation with AI gating",
    "Improved API key source handling for saved local keys versus environment keys",
    "AI scrub visibility, correction summaries, and rescore improvements",
]


def get_backlog_summary() -> dict[str, object]:
    priority_order = ("High", "Medium", "Low")
    counter = Counter(item["priority"] for item in BACKLOG_ITEMS)
    grouped = {
        priority: [item for item in BACKLOG_ITEMS if item["priority"] == priority]
        for priority in priority_order
    }

    return {
        "soft_launch_percent": SOFT_LAUNCH_PERCENT,
        "counts": {priority: counter.get(priority, 0) for priority in priority_order},
        "items_by_priority": grouped,
        "recently_completed": list(RECENTLY_COMPLETED),
    }
