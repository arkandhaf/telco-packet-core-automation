from html import escape

import streamlit as st

from ui.state import history_summary


def render_kpi_bento():
    summary = history_summary(st.session_state.get("history", []))
    assessment = st.session_state.get("generated", {}).get("assessment")
    risk = assessment["level"] if assessment else "NOT ASSESSED"
    cards = [
        ("Generated events", str(summary["generated"]), "Manual + batch", "pill-purple"),
        ("Simulation runs", str(summary["simulations"]), "No device connection", "pill-dark"),
        ("Latest change risk", risk, "Rule checks · not ML", "pill-yellow"),
        ("Live execution", "BLOCKED", "Pre-checks required", "pill-yellow"),
    ]
    for column, (label, value, detail, badge) in zip(st.columns(4), cards):
        with column:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{escape(label)}</div>
                <div class="metric-value">{escape(value)}</div>
                <div class="metric-detail"><span class="pill-badge {badge}">{escape(detail)}</span></div>
            </div>
            """, unsafe_allow_html=True)
    st.write("")