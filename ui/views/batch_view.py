import hashlib
import io
from zipfile import BadZipFile

import pandas as pd
import streamlit as st

from core.parsers.ciq_parser import (
    MAX_BATCH_ROWS, generate_batch_zip, generate_combined_script_txt,
    get_sample_ciq_csv, map_ciq_dataframe, process_ciq_batch,
)
from core.services.audit_service import append_history_entries, build_audit_log, redact_secrets
from core.services.risk_service import assess_change

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def render_batch_view():
    st.subheader("Batch CIQ processing")
    st.caption(f"Upload CSV or XLSX, up to 5 MB and {MAX_BATCH_ROWS} rows. Required columns and every row are validated before output is published.")
    st.download_button("Download sample CIQ template", get_sample_ciq_csv(), file_name="TEMPLATE_CIQ_STANDARD.csv", mime="text/csv")
    uploaded_file = st.file_uploader("Upload CIQ (.csv / .xlsx)", type=["csv", "xlsx"])
    if uploaded_file is None:
        st.session_state.pop("batch_results", None)
        st.session_state.pop("batch_source_hash", None)
        return
    content = uploaded_file.getvalue()
    fingerprint = hashlib.sha256(content).hexdigest()
    if st.session_state.get("batch_source_hash") != fingerprint:
        st.session_state["batch_source_hash"] = fingerprint
        st.session_state.pop("batch_results", None)
    try:
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("Upload exceeds the 5 MB limit")
        if uploaded_file.name.lower().endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, nrows=MAX_BATCH_ROWS + 1)
        else:
            df_raw = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False, nrows=MAX_BATCH_ROWS + 1)
        if df_raw.empty or len(df_raw) > MAX_BATCH_ROWS:
            raise ValueError(f"File must contain 1–{MAX_BATCH_ROWS} rows")
        _, mapping_report = map_ciq_dataframe(df_raw)
        st.write(f"CIQ preview: {len(df_raw)} rows")
        # Legacy aliases for secret fields must also be hidden in previews.
        mapped_preview, _ = map_ciq_dataframe(df_raw)
        secret_cols = [column for column in mapped_preview.columns if any(
            word in str(column).lower() for word in ("key", "cipher", "password", "token", "secret")
        )]
        st.dataframe(mapped_preview.drop(columns=secret_cols).head(100), width="stretch", hide_index=True)
        with st.expander("Column mapping"):
            st.dataframe(pd.DataFrame([{"Parameter": key, "Mapping": value} for key, value in mapping_report.items()]), width="stretch", hide_index=True)
        if st.button("Validate, assess and generate batch", type="primary"):
            st.session_state.pop("batch_results", None)
            with st.spinner("Validating CIQ and assessing changes..."):
                results = process_ciq_batch(df_raw)
                batch_entry = build_audit_log(
                    "BATCH_MML_GEN", "BATCH_PROVISION", f"{len(results)}_ENTRIES",
                    {"source_sha256": fingerprint, "total_processed": len(results)},
                    status="BATCH_SUCCESS", metadata={"execution_mode": "generation"},
                )
                entries = [batch_entry]
                for item in results:
                    assessment = assess_change(item["payload"], item["mml_script"], st.session_state.get("history", []))
                    item["assessment"] = assessment
                    entries.append(build_audit_log(
                        "BATCH_ROW_GENERATED", item["apn_name"], item["app_name"], item["payload"],
                        status="SCRIPT_GENERATED", work_order_id=batch_entry["WO ID"],
                        metadata={"assessment": assessment, "execution_mode": "generation",
                                  "batch_event_id": batch_entry["Event ID"], "source_sha256": fingerprint,
                                  "row_index": item["index"]},
                    ))
                st.session_state["history"] = append_history_entries(entries)
                st.session_state["batch_results"] = results
                st.rerun()
    except (ValueError, OSError, ImportError, pd.errors.ParserError, UnicodeError, BadZipFile, EOFError) as exc:
        st.session_state.pop("batch_results", None)
        st.error(f"Batch could not be generated: {exc}")
        return

    results = st.session_state.get("batch_results")
    if not results:
        return
    st.divider()
    st.success(f"Generated and audited {len(results)} validated rows.")
    st.warning("Batch scripts may reference shared objects. They are review artifacts; live execution is blocked until device-state checks and snapshot rollback are implemented.")
    first, second, third = st.columns(3)
    first.metric("Scripts", len(results))
    second.metric("Unique APNs", len({item["apn_name"] for item in results}))
    third.metric("High review priority", sum(item["assessment"]["level"] == "HIGH" for item in results))
    left, right = st.columns(2)
    left.download_button("Download combined script", generate_combined_script_txt(results), file_name="ALL_MML_PROVISIONING_SCRIPTS.txt", mime="text/plain", width="stretch")
    right.download_button("Download complete archive", generate_batch_zip(results), file_name="RELPOOL_BATCH_PACKAGE.zip", mime="application/zip", width="stretch")
    with st.expander("Inspect a batch row"):
        index = st.selectbox("CIQ row", range(len(results)), format_func=lambda value: f"#{results[value]['index']} | {results[value]['apn_name']} | {results[value]['app_name']}")
        item = results[index]
        st.write(f"Review priority: {item['assessment']['level']} ({item['assessment']['score']}/100)")
        for reason in item["assessment"]["reasons"]:
            st.write(f"• {reason}")
        tabs = st.tabs(["Provisioning", "Rollback draft", "Payload"])
        with tabs[0]:
            if item["payload"]["header_enrichment"] == "Yes":
                st.warning("Generated CLI contains a header-enrichment secret.")
            st.code(item["mml_script"], language="text")
        with tabs[1]:
            st.code(item["rollback_script"], language="text")
        with tabs[2]:
            st.json(redact_secrets(item["payload"]))
