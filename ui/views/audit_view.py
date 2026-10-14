import json

import pandas as pd
import streamlit as st

from core.services.audit_service import MAX_HISTORY_ENTRIES, redact_secrets
from core.services.risk_service import export_feature_jsonl

DISPLAY_COLUMNS = ["Timestamp", "WO ID", "Action", "Target Node", "APN", "App Target", "Status"]


def render_audit_view():
    st.divider()
    st.subheader("Deployment audit trail")
    history = st.session_state.get("history", [])
    if not history:
        st.info("No recorded events yet. Generate a validated script to begin.")
        return
    left, middle, right = st.columns([2, 1, 1])
    query = left.text_input("Search work orders, APNs or applications", key="audit_search").strip().casefold()
    actions = middle.multiselect("Action", sorted({str(row.get("Action", "UNKNOWN")) for row in history}), key="audit_actions")
    statuses = right.multiselect("Status", sorted({str(row.get("Status", "UNKNOWN")) for row in history}), key="audit_statuses")
    filtered = [
        row for row in history
        if (not query or query in " ".join(str(row.get(column, "")) for column in DISPLAY_COLUMNS).casefold())
        and (not actions or row.get("Action") in actions)
        and (not statuses or row.get("Status") in statuses)
    ]
    st.caption(f"{len(filtered)} matching events / {len(history)} total. Display limited to the latest {MAX_HISTORY_ENTRIES}; exports include all matching records.")
    if filtered:
        display = [{column: row.get(column, "—") for column in DISPLAY_COLUMNS} for row in filtered[:MAX_HISTORY_ENTRIES]]
        st.dataframe(pd.DataFrame(display), width="stretch", hide_index=True)
        with st.expander("Inspect an audit event"):
            index = st.selectbox(
                "Event", range(min(len(filtered), MAX_HISTORY_ENTRIES)), key="audit_event_selector",
                format_func=lambda value: f"{filtered[value].get('Timestamp', '')} | {filtered[value].get('WO ID', '?')} | {filtered[value].get('Action', '?')} | #{value + 1}",
            )
            st.json(redact_secrets(filtered[index]))
        left, right = st.columns(2)
        left.download_button("Export matching audit events", json.dumps(redact_secrets(filtered), ensure_ascii=False, indent=2), file_name="relpool_audit.json", mime="application/json")
        dataset = export_feature_jsonl(filtered)
        right.download_button("Export anomaly-detection features", dataset, file_name="relpool_features_v1.jsonl", mime="application/x-ndjson", disabled=not dataset)
        st.caption("Feature export excludes secrets, raw CLI, hostnames and legacy events without captured features. Outcomes are observations; risk labels remain unknown until independently reviewed.")
        st.caption("Keep work-order groups together when splitting datasets. Simulations and repeated attempts must not be counted as independent successful deployments.")
    else:
        st.info("No events match these filters.")
    st.markdown('<div class="footer-bar">RELPOOL Core Automation · v2.3 · MCPE Core</div>', unsafe_allow_html=True)