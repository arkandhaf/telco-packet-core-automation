import streamlit as st


def render_live_header():
    st.markdown("""
    <div class="live-bar">
        <div class="live-bar-main">
            <span class="pill-badge pill-yellow">REVIEW MODE</span>
            <span class="live-bar-title">RELPOOL | Core PCEF &amp; PCRF Automation</span>
        </div>
        <div class="live-bar-meta">
            <span class="pill-badge pill-dark">Huawei Service-V</span>
            <span class="pill-badge pill-purple">Risk checks: rules-v1</span>
        </div>
    </div>
    """, unsafe_allow_html=True)