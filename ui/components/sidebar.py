import streamlit as st

from ui.state import history_summary


def render_sidebar():
    with st.sidebar:
        st.markdown("### ⚡ RELPOOL")
        st.caption("CORE AUTOMATION ENGINE")
        st.divider()
        st.caption("RECORDED ACTIVITY")
        summary = history_summary(st.session_state.get("history", []))
        first, second = st.columns(2)
        first.metric("Work orders", summary["work_orders"])
        second.metric("Events today", summary["today"], help="Calendar day in Asia/Jakarta")
        first, second = st.columns(2)
        first.metric("Live attempts", summary["live_attempts"])
        second.metric("Failed / unknown", summary["failures"])
        if st.button("Refresh history", width="stretch"):
            st.rerun()
        st.divider()
        st.caption("EXECUTION READINESS")
        st.warning("Live execution blocked")
        st.caption("Device snapshots, ownership checks and verified rollback must be implemented before enabling live changes.")
        st.divider()
        st.caption("ANOMALY DETECTION")
        st.write("Explainable rule checks")
        st.caption("No trained model is active. Export versioned features from the audit view to prepare an offline dataset.")
        st.caption("Timezone: Asia/Jakarta · Audit stored in UTC")