import streamlit as st


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(59,130,246,0.10), transparent 28%),
                    radial-gradient(circle at top right, rgba(168,85,247,0.08), transparent 24%),
                    linear-gradient(180deg, #050914 0%, #090d18 100%);
            }

            .block-container {
                padding-top: 2.6rem;
                padding-bottom: 2.75rem;
                max-width: 1520px;
            }

            h1, h2, h3 {
                letter-spacing: -0.03em;
            }

            .hero-wrap {
                padding: 0.5rem 0 1.0rem 0;
                margin-bottom: 0.25rem;
            }

            .st-key-hero_close_application_button button {
                min-height: 3.25rem;
                border-radius: 18px;
                border: 1px solid rgba(248,113,113,0.42);
                background:
                    linear-gradient(180deg, rgba(127,29,29,0.96) 0%, rgba(69,10,10,0.98) 100%);
                color: rgba(255,244,244,0.98);
                font-weight: 800;
                letter-spacing: 0.01em;
                box-shadow:
                    0 12px 30px rgba(127,29,29,0.24),
                    inset 0 1px 0 rgba(255,255,255,0.06);
            }

            .st-key-hero_close_application_button button:hover {
                border-color: rgba(252,165,165,0.62);
                background:
                    linear-gradient(180deg, rgba(153,27,27,0.98) 0%, rgba(91,15,15,0.99) 100%);
                color: white;
            }

            .st-key-hero_close_application_button button:focus,
            .st-key-hero_close_application_button button:focus-visible {
                box-shadow:
                    0 0 0 0.18rem rgba(248,113,113,0.18),
                    0 14px 32px rgba(127,29,29,0.22);
            }

            .hero-title {
                display: flex;
                align-items: flex-end;
                gap: 0.7rem;
                flex-wrap: wrap;
                margin-bottom: 0.32rem;
            }

            .hero-title-main {
                font-family: "Copperplate Gothic", "Copperplate", "Copperplate Gothic Light", "Palatino Linotype", serif;
                font-size: 3.0rem;
                font-weight: 700;
                line-height: 0.98;
                letter-spacing: 0.02em;
                text-transform: none;
                color: rgba(255,255,255,0.985);
                text-shadow:
                    0 0 18px rgba(255,255,255,0.04),
                    0 10px 28px rgba(0,0,0,0.28);
            }

            .hero-title-version {
                font-size: 1.5rem;
                font-weight: 700;
                line-height: 1.0;
                letter-spacing: -0.02em;
                color: rgba(255,255,255,0.72);
                padding-bottom: 0.18rem;
            }

            .hero-subtle {
                color: rgba(255,255,255,0.62);
                font-size: 1.02rem;
                font-weight: 500;
                font-style: italic;
                letter-spacing: 0.01em;
                margin-left: 0.08rem;
            }

            .openai-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                padding: 0.55rem 0.85rem;
                border-radius: 999px;
                font-size: 0.92rem;
                font-weight: 700;
                border: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.92);
                box-shadow: 0 8px 20px rgba(0,0,0,0.16);
            }

            .openai-badge.validated {
                border-color: rgba(16,185,129,0.42);
                background: rgba(16,185,129,0.12);
                color: rgba(209,250,229,0.98);
            }

            .openai-badge.saved {
                border-color: rgba(245,158,11,0.36);
                background: rgba(245,158,11,0.12);
                color: rgba(254,243,199,0.98);
            }

            .openai-badge.not-configured {
                border-color: rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.04);
                color: rgba(255,255,255,0.88);
            }

            .app-busy-banner {
                margin-top: 0.7rem;
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.55rem 0.82rem;
                border-radius: 14px;
                background: rgba(59,130,246,0.10);
                border: 1px solid rgba(59,130,246,0.24);
                color: rgba(219,234,254,0.96);
                font-size: 0.93rem;
                font-weight: 650;
            }

            .kpi-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 1rem;
                margin: 0.9rem 0 1.25rem 0;
            }

            .kpi-card {
                position: relative;
                overflow: hidden;
                border-radius: 18px;
                padding: 1rem 1.05rem;
                min-height: 110px;
                background: linear-gradient(180deg, rgba(17,24,39,0.96) 0%, rgba(10,14,24,0.98) 100%);
                border: 1px solid rgba(255,255,255,0.07);
                border-top-width: 3px;
                box-shadow:
                    0 10px 24px rgba(0,0,0,0.18),
                    inset 0 1px 0 rgba(255,255,255,0.02);
            }

            .kpi-card::after {
                content: "";
                position: absolute;
                inset: 0;
                pointer-events: none;
                background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0));
            }

            .kpi-card.blue {
                border-top-color: rgba(59,130,246,0.95);
            }

            .kpi-card.green {
                border-top-color: rgba(34,197,94,0.92);
            }

            .kpi-card.orange {
                border-top-color: rgba(249,115,22,0.92);
            }

            .kpi-label {
                color: rgba(255,255,255,0.76);
                font-size: 0.96rem;
                font-weight: 620;
                margin-bottom: 0.42rem;
                text-transform: none;
            }

            .kpi-value {
                color: white;
                font-size: 2rem;
                font-weight: 800;
                line-height: 1.0;
                letter-spacing: -0.02em;
            }

            .filters-shell {
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 18px;
                background: linear-gradient(180deg, rgba(13,18,30,0.94), rgba(9,13,22,0.96));
                box-shadow: 0 10px 26px rgba(0,0,0,0.16);
                padding: 0.95rem 1rem 0.25rem 1rem;
                margin-bottom: 1.3rem;
            }

            .filters-heading {
                font-size: 1rem;
                font-weight: 700;
                color: rgba(255,255,255,0.92);
                margin-bottom: 0.2rem;
            }

            .filters-subtle {
                font-size: 0.9rem;
                color: rgba(255,255,255,0.64);
                margin-bottom: 0.85rem;
            }

            .job-card {
                position: relative;
                background: linear-gradient(180deg, rgba(16,22,36,0.96) 0%, rgba(11,16,28,0.96) 100%);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 20px;
                padding: 1.2rem 1.2rem 0.95rem 1.2rem;
                box-shadow: 0 14px 40px rgba(0,0,0,0.24);
                margin-bottom: 1rem;
                overflow: hidden;
            }

            .job-card::before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                bottom: 0;
                width: 4px;
                background: linear-gradient(180deg, rgba(59,130,246,0.95), rgba(168,85,247,0.85));
            }

            .job-title {
                font-size: 1.24rem;
                font-weight: 760;
                line-height: 1.35;
                margin-bottom: 0.7rem;
                color: rgba(255,255,255,0.98);
            }

            .meta-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.55rem;
                margin-bottom: 0.05rem;
            }

            .meta-pill {
                display: inline-flex;
                align-items: center;
                border-radius: 14px;
                padding: 0.48rem 0.82rem;
                font-size: 0.84rem;
                font-weight: 680;
                line-height: 1;
                color: rgba(255,255,255,0.94);
                border: 1px solid rgba(255,255,255,0.09);
                background: linear-gradient(180deg, rgba(18,24,36,0.94), rgba(12,16,26,0.98));
                box-shadow:
                    0 6px 16px rgba(0,0,0,0.14),
                    inset 0 1px 0 rgba(255,255,255,0.02);
            }

            .meta-pill.location {
                border-left: 3px solid rgba(148,163,184,0.72);
                padding-left: 0.7rem;
            }

            .meta-pill.fit {
                border-left: 3px solid rgba(59,130,246,0.88);
                padding-left: 0.7rem;
            }

            .meta-pill.comp {
                border-left: 3px solid rgba(168,85,247,0.88);
                padding-left: 0.7rem;
            }

            .section-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin: 1.1rem 0 0.75rem 0;
            }

            .section-title {
                font-size: 1.95rem;
                font-weight: 780;
                line-height: 1.0;
                color: rgba(255,255,255,0.98);
            }

            .section-kicker {
                font-size: 0.78rem;
                font-weight: 780;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                color: rgba(96,165,250,0.92);
                margin-bottom: 0.28rem;
            }

            .section-meta {
                font-size: 0.98rem;
                font-weight: 650;
                color: rgba(255,255,255,0.72);
                margin-top: 0.38rem;
            }

            .section-meta-right {
                text-align: right;
                margin-top: 0.5rem;
            }

            .soft-control-label {
                font-size: 0.88rem;
                font-weight: 650;
                color: rgba(255,255,255,0.72);
                margin-bottom: 0.25rem;
                text-align: right;
            }

            .queue-toolbar {
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 20px;
                background:
                    radial-gradient(circle at top right, rgba(59,130,246,0.12), transparent 34%),
                    linear-gradient(180deg, rgba(14,20,33,0.96), rgba(9,13,23,0.97));
                box-shadow: 0 14px 36px rgba(0,0,0,0.18);
                padding: 1rem 1rem 0.9rem 1rem;
                margin: 1.2rem 0 0.9rem 0;
            }

            .bottom-controls-wrap {
                margin-top: 1.35rem;
                margin-bottom: 0.4rem;
            }

            .pagination-summary {
                text-align: center;
                font-weight: 700;
                font-size: 1rem;
                margin-bottom: 0.9rem;
            }

            .jobs-per-page-label {
                text-align: center;
                font-weight: 650;
                margin-top: 0.85rem;
                margin-bottom: 0.3rem;
                color: rgba(255,255,255,0.88);
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 10px 28px rgba(0,0,0,0.18);
            }

            div[data-testid="stButton"] > button {
                border-radius: 14px;
                min-height: 48px;
                font-weight: 760;
                transition: all 0.18s ease;
                box-shadow: none;
            }

            div[data-testid="stButton"] > button:hover {
                transform: translateY(-1px);
            }


            div[data-testid="stButton"] > button[kind="tertiary"] {
                border-radius: 14px;
                min-height: 48px;
                font-weight: 760;
                border: 1px solid rgba(96,165,250,0.42);
                background: linear-gradient(180deg, rgba(59,130,246,0.92) 0%, rgba(37,99,235,0.92) 100%);
                color: rgba(255,255,255,0.98);
                box-shadow:
                    0 10px 24px rgba(37,99,235,0.22),
                    inset 0 1px 0 rgba(255,255,255,0.10);
            }

            div[data-testid="stButton"] > button[kind="tertiary"]:hover {
                transform: translateY(-1px);
                border-color: rgba(147,197,253,0.72);
                background: linear-gradient(180deg, rgba(96,165,250,0.98) 0%, rgba(37,99,235,0.95) 100%);
            }

            div[data-testid="stButton"] > button[kind="tertiary"]:focus:not(:active) {
                border-color: rgba(147,197,253,0.82);
                box-shadow:
                    0 0 0 0.2rem rgba(59,130,246,0.20),
                    0 10px 24px rgba(37,99,235,0.22);
            }

            div[data-baseweb="select"] > div,
            div[data-testid="stSelectbox"] > div {
                border-radius: 14px;
            }

            .ai-button-chip-wrap {
                position: relative;
                z-index: 2;
                display: flex;
                justify-content: flex-end;
                pointer-events: none;
                margin-bottom: -0.8rem;
                padding-right: 0.45rem;
            }

            .ai-button-chip {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 1.8rem;
                height: 1.2rem;
                padding: 0 0.38rem;
                border-radius: 999px;
                border: 1px solid rgba(125, 211, 252, 0.28);
                background: linear-gradient(180deg, rgba(22, 78, 99, 0.92), rgba(15, 52, 67, 0.96));
                color: rgba(224, 242, 254, 0.92);
                font-size: 0.62rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                box-shadow:
                    0 6px 14px rgba(6, 24, 31, 0.22),
                    inset 0 1px 0 rgba(255,255,255,0.06);
            }

            .control-label {
                font-size: 0.92rem;
                font-weight: 650;
                color: rgba(255,255,255,0.78);
                margin-bottom: 0.25rem;
            }

            .job-actions-label {
                font-size: 0.82rem;
                font-weight: 760;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.58);
                text-align: right;
                margin-bottom: 0.45rem;
            }

            @media (max-width: 1200px) {
                .kpi-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }

            @media (max-width: 740px) {
                .hero-title-main {
                    font-size: 2.15rem;
                }

                .hero-title-version {
                    font-size: 1.05rem;
                }

                .hero-subtle {
                    font-size: 0.95rem;
                }

                .kpi-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
