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
                padding-top: 1.6rem;
                padding-bottom: 2.75rem;
                max-width: 1520px;
            }

            h1, h2, h3 {
                letter-spacing: -0.03em;
            }

            .hero-wrap {
                padding: 0.18rem 0 1.0rem 0;
                margin-bottom: 0.25rem;
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
                border: 1px solid rgba(255,255,255,0.10);
                box-shadow: 0 14px 38px rgba(0,0,0,0.22);
                min-height: 110px;
            }

            .kpi-card.blue {
                background: linear-gradient(135deg, rgba(20,28,48,0.98), rgba(30,58,138,0.60));
            }

            .kpi-card.green {
                background: linear-gradient(135deg, rgba(17,34,35,0.98), rgba(22,163,74,0.42));
            }

            .kpi-card.orange {
                background: linear-gradient(135deg, rgba(42,27,18,0.98), rgba(249,115,22,0.40));
            }

            .kpi-label {
                color: rgba(255,255,255,0.84);
                font-size: 0.98rem;
                font-weight: 600;
                margin-bottom: 0.35rem;
            }

            .kpi-value {
                color: white;
                font-size: 2rem;
                font-weight: 800;
                line-height: 1.0;
            }

            .filters-shell {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 18px;
                background: linear-gradient(180deg, rgba(16,22,36,0.92), rgba(10,14,24,0.92));
                box-shadow: 0 12px 30px rgba(0,0,0,0.18);
                padding: 0.95rem 1rem 0.25rem 1rem;
                margin-bottom: 1.3rem;
            }

            .filters-heading {
                font-size: 1rem;
                font-weight: 700;
                color: rgba(255,255,255,0.92);
                margin-bottom: 0.75rem;
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
                gap: 0.5rem;
                margin-bottom: 0.05rem;
            }

            .meta-pill {
                display: inline-block;
                border-radius: 999px;
                padding: 0.35rem 0.78rem;
                font-size: 0.84rem;
                font-weight: 650;
                color: rgba(255,255,255,0.97);
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.05);
            }

            .meta-pill.location {
                background: rgba(255,255,255,0.06);
            }

            .meta-pill.fit {
                background: rgba(37,99,235,0.18);
                border-color: rgba(59,130,246,0.36);
            }

            .meta-pill.comp {
                background: rgba(147,51,234,0.18);
                border-color: rgba(168,85,247,0.36);
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

            .section-meta {
                font-size: 1rem;
                font-weight: 650;
                color: rgba(255,255,255,0.82);
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

            div[data-baseweb="select"] > div,
            div[data-testid="stSelectbox"] > div {
                border-radius: 14px;
            }

            .control-label {
                font-size: 0.92rem;
                font-weight: 650;
                color: rgba(255,255,255,0.78);
                margin-bottom: 0.25rem;
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
