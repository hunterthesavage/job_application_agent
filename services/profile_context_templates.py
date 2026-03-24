from __future__ import annotations


EXECUTIVE_TECH_PROFILE_TEMPLATE = {
    "resume_text": """Paste the longer-form resume evidence here.

Recommended content:
- headline and contact block
- recent roles and scope
- major transformations led
- measurable outcomes
- core systems, platforms, and operating experience
""",
    "profile_summary": (
        "Executive technology leader focused on enterprise IT, operations, transformation, "
        "and customer-impacting platform execution."
    ),
    "strengths_to_highlight": (
        "Enterprise IT leadership\n"
        "Digital transformation\n"
        "Operating model improvement\n"
        "AI and automation programs\n"
        "Platform modernization\n"
        "Cost optimization\n"
        "Cross-functional executive leadership"
    ),
    "cover_letter_voice": (
        "Direct, executive, credible, and specific. Emphasize business outcomes, leadership scope, "
        "and practical transformation impact."
    ),
}


def get_profile_context_template() -> dict[str, str]:
    return dict(EXECUTIVE_TECH_PROFILE_TEMPLATE)
