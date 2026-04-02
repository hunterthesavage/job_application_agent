from __future__ import annotations

from collections import Counter


SOFT_LAUNCH_PERCENT = 91


BACKLOG_ITEMS: list[dict[str, str]] = [
    {
        "lane": "Now",
        "title": "Run one external friend test without hand-holding",
        "detail": "Use the current Windows package and README flow, then watch for where the tester gets stuck without extra explanation.",
    },
    {
        "lane": "Now",
        "title": "Complete the with-AI acceptance pass",
        "detail": "Run the first-time flow with a real OpenAI key and confirm title expansion, scoring, scrub, and cover letters all work end to end.",
    },
    {
        "lane": "Now",
        "title": "Fix only launch blockers from real-user feedback",
        "detail": "Use the next tester and acceptance passes to close broken install steps, confusing UI, persistence issues, and obvious workflow gaps before adding new product scope.",
    },
    {
        "lane": "Now",
        "title": "Improve legacy search quality with the new benchmarks",
        "detail": "Treat Legacy as the V1 engine and use the title matrix plus real-job profile scoring to reduce weak adjacent matches and improve what appears first in New Roles.",
    },
    {
        "lane": "Now",
        "title": "Review long-run busy and reset behavior",
        "detail": "Double-check how discovery and rescoring communicate progress, long waits, and recovery when a run takes longer than expected.",
    },
    {
        "lane": "Next",
        "title": "Clarify combined AI toggle behavior in Pipeline",
        "detail": "The single run-level AI toggle is simpler, but the page still needs clearer wording for actions like Find Job Links Only that only use part of it.",
    },
    {
        "lane": "Next",
        "title": "Match the Setup Wizard Profile Context flow to Settings",
        "detail": "Bring the same step-driven 1-2-3 visual treatment into the wizard so profile setup feels consistent everywhere.",
    },
    {
        "lane": "Next",
        "title": "Decide whether environment-key fallback should stay",
        "detail": "The app now explains saved versus environment keys clearly, but public users may still benefit from an even simpler saved-local-key-only model.",
    },
    {
        "lane": "Next",
        "title": "Validate the Windows package on one more real machine",
        "detail": "The packaging path is much healthier now, but one more real-machine pass would further de-risk broader sharing.",
    },
    {
        "lane": "Later",
        "title": "Sign and notarize the Mac desktop package",
        "detail": "Use Apple Developer ID signing, notarization, and stapling so the desktop app stops showing the unidentified developer/security friction on first launch.",
    },
    {
        "lane": "Later",
        "title": "Surface OpenAI usage, token, and cost visibility",
        "detail": "Add a read-only app view that shows OpenAI usage for the configured key, including token consumption, cost, and links back to billing or usage pages.",
    },
    {
        "lane": "Later",
        "title": "Add a Fortune 500 career-site registry and filter",
        "detail": "Use the curated registry as a trusted seed lane and optional ranking/filter signal only after V1 search quality is stable.",
    },
    {
        "lane": "Later",
        "title": "Expand discovery beyond the Fortune 500 seed set",
        "detail": "Build broader employer and ATS endpoint coverage once the V1 engine and review experience are stable enough to benefit from more source expansion.",
    },
    {
        "lane": "Later",
        "title": "Add direct API integrations for more discovery sources",
        "detail": "Evaluate API-based discovery expansion only after the shipped legacy path is validated and the ROI is clearer than it is today.",
    },
    {
        "lane": "Later",
        "title": "Tighten internal docs after launch hardening",
        "detail": "Refresh architecture, current-state, and settings-reference docs so they reflect the current app instead of earlier build phases.",
    },
    {
        "lane": "Later",
        "title": "Clean up remaining packaging and dependency rough edges",
        "detail": "Keep reviewing setup assumptions, optional dependencies, and platform notes after the soft-launch path is proven.",
    },
    {
        "lane": "Later",
        "title": "Revisit orchestration boundaries after soft launch",
        "detail": "Session state, view code, and runtime services still carry some operator complexity that is acceptable now but will be a future scaling constraint.",
    },
]


DONE_OR_STALE: list[dict[str, str]] = [
    {
        "title": "Fix inaccurate duration timing in run results",
        "detail": "This appears addressed already and should no longer be treated as active launch work unless new evidence shows the Duration display is still wrong.",
    },
    {
        "title": "Decide the V1 search engine",
        "detail": "Settled: Legacy is the engine for V1, while direct-source stays internal-only.",
    },
]


RECENTLY_COMPLETED: list[str] = [
    "Documented the V1 search decision and moved direct-source to internal-only status",
    "Added the title-matrix and real-job profile scoring benchmarks",
    "Defaulted New Roles review ordering to Highest Fit Score",
    "Recovered and clarified the Windows installer path with screenshot-driven README guidance",
    "Made Broader Search the default visible search strategy",
]


def get_backlog_summary() -> dict[str, object]:
    lane_order = ("Now", "Next", "Later")
    counter = Counter(item["lane"] for item in BACKLOG_ITEMS)
    grouped = {
        lane: [item for item in BACKLOG_ITEMS if item["lane"] == lane]
        for lane in lane_order
    }

    return {
        "soft_launch_percent": SOFT_LAUNCH_PERCENT,
        "counts": {lane: counter.get(lane, 0) for lane in lane_order},
        "items_by_lane": grouped,
        "done_or_stale": list(DONE_OR_STALE),
        "recently_completed": list(RECENTLY_COMPLETED),
    }
