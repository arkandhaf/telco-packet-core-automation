import os

import streamlit as st
from pydantic import ValidationError

from core.engines.huawei_service_v import generate_huawei_mml_script, generate_rollback_script
from core.models.payload import ProvisioningPayload
from core.parsers.mml_parser import parse_mml_script_commands
from core.services.audit_service import append_history, build_audit_log, redact_secrets
from core.services.risk_service import assess_change
from core.transports.ssh_gateway import execute_script


PRESETS = {
    "-- Manual CIQ Input --": ("internet_im3", "TikTok", "11010", "11001000", "*.tiktok.com, *.v2.tiktokcdn.com", 0, 0),
    "TikTok Zero Rating (B2C)": ("internet_im3", "TikTok", "11010", "11001000", "*.tiktok.com, *.v2.tiktokcdn.com", 0, 0),
    "Gojek Special Rate (Local App B2B)": ("b2b_corporate", "Gojek Driver", "20000", "20001000", "*.gojek.com, *.driver.gojek.co.id", 1, 0),
    "Gaming Low Latency (QCI 1)": ("internet_im3", "Mobile Legends", "30000", "30001000", "*.mobilelegends.com, *.moonton.com", 0, 2),
}


def render_manual_view():
    st.subheader("CIQ provisioning")
    preset = st.selectbox("Scenario preset", list(PRESETS))
    apn, app, rg, sid, domain, charging_index, qci_index = PRESETS[preset]
    st.caption("Presets are examples. Review every parameter against the approved work order.")
    with st.form(f"ciq_form_{preset}"):
        left, right = st.columns(2)
        with left:
            st.markdown("#### Product and charging")
            product_type = st.selectbox("Product Requirement Type", ["New Product", "Revamp", "Reguler Update"])
            user_profile = st.selectbox("User Profile", ["New", "Existing"])
            apn_name = st.text_input("APN Name", value=apn)
            charging_type = st.selectbox("Charging Profile", ["Zero Rating", "Special Rate (differentiate RG)"], index=charging_index)
            rg_val = st.text_input("Rating Group (RG ID)", value=rg)
            sid_val = st.text_input("Service ID (SID)", value=sid)
            capping_option = st.selectbox("Zero Rating Capping Allocation", ["No Capping", "20 MB/day", "35 MB/day"])
            st.markdown("#### Header enrichment")
            header_enrichment = st.radio("Is Header Enrichment required?", ["No", "Yes"])
            he_key = st.text_input("Header Enrichment Key", type="password", help="Used only when enrichment is Yes. Generated CLI contains this secret.")
            he_cipher = st.text_input("Header Enrichment Cipher", value="AES256")
        with right:
            st.markdown("#### Application and requested QoS")
            speed_limit = st.selectbox("Speed Limitation Policy", ["Full Speed", "Throttle 256kbps", "Throttle 128kbps", "Throttle 64kbps"])
            qci_val = st.selectbox("QCI Profile", ["9 (Default Internet)", "4 (Dedicated)", "1 (Voice/Low Latency)"], index=qci_index)
            st.caption("QoS, speed and capping are recorded as comments; provisioning those policies is not implemented.")
            app_category = st.radio("Apps Category", ["Well Known Apps", "Local Apps"])
            app_name = st.text_input("Apps Target Name", value=app)
            app_domain = st.text_area("Domain / IP Target Details", value=domain, height=120)
            st.caption("Provide explicit comma-separated domains. URLs with paths, ports and CLI syntax are rejected.")
        submit = st.form_submit_button("Generate and assess change", width="stretch")

    if submit:
        st.session_state.pop("generated", None)
        st.session_state.pop("execution_result", None)
        try:
            payload = ProvisioningPayload(
                product_type=product_type, user_profile=user_profile, apn_name=apn_name,
                charging_type=charging_type, rg_val=rg_val, sid_val=sid_val,
                capping_option=capping_option, header_enrichment=header_enrichment,
                he_key=he_key if header_enrichment == "Yes" else "",
                he_cipher=he_cipher if header_enrichment == "Yes" else "",
                speed_limit=speed_limit, qci_val=qci_val, app_category=app_category,
                app_name=app_name, app_domain=app_domain,
            ).to_dict()
            script = generate_huawei_mml_script(payload)
            rollback = generate_rollback_script(payload)
            assessment = assess_change(payload, script, st.session_state.get("history", []))
            entry = build_audit_log(
                "GENERATE MML", payload["apn_name"], payload["app_name"], payload,
                metadata={"assessment": assessment, "execution_mode": "generation"},
            )
            st.session_state["history"] = append_history(entry)
            st.session_state["generated"] = {
                "payload": payload, "script": script, "rollback": rollback,
                "assessment": assessment, "work_order_id": entry["WO ID"],
            }
            st.rerun()
        except ValidationError as exc:
            fields = ", ".join(".".join(map(str, error["loc"])) or "payload" for error in exc.errors())
            st.error(f"Invalid provisioning input: {fields}. Check required values, numeric IDs and domain syntax.")
        except (OSError, ValueError) as exc:
            st.error(f"Generation was not recorded: {exc}")

    generated = st.session_state.get("generated")
    if not generated:
        return
    payload = generated["payload"]
    assessment = generated["assessment"]
    st.success(f"Script generated and audited: {generated['work_order_id']}")
    st.subheader(f"Change review: {assessment['level']} · {assessment['score']}/100")
    st.caption("Rule-based review priority, not an incident probability or trained model prediction.")
    for reason in assessment["reasons"]:
        st.write(f"• {reason}")
    for blocker in assessment["live_blockers"]:
        st.warning(blocker)
    tabs = st.tabs(["Provisioning MML", "Rollback draft", "Simulation / execution", "Work order"])
    stem = f"{payload['apn_name']}_{payload['app_name']}"
    with tabs[0]:
        if payload["header_enrichment"] == "Yes":
            st.warning("This script contains a header-enrichment secret. Store downloaded artifacts securely.")
        st.code(generated["script"], language="text")
        st.download_button("Download MML script", generated["script"], file_name=f"MML_{stem}.txt", mime="text/plain")
    with tabs[1]:
        st.caption("Review against actual device state. Shared objects and profile settings are not safely restored by this draft.")
        st.code(generated["rollback"], language="text")
        st.download_button("Download rollback draft", generated["rollback"], file_name=f"ROLLBACK_{stem}.txt", mime="text/plain")
    with tabs[2]:
        mode = st.radio("Target Server Mode:", ["Simulation Mode", "Live GGSN Testbed"], horizontal=True)
        is_live = mode.startswith("Live")
        st.caption("Simulation lists commands only. It does not validate Huawei syntax, connectivity or traffic impact.")
        disabled = is_live and (bool(assessment["live_blockers"]) or os.getenv("RELPOOL_ENABLE_LIVE", "").lower() != "true")
        if st.button("Run simulation" if not is_live else "Push config to testbed", type="primary", disabled=disabled):
            # Persist intent first. If the process stops, the attempt remains visible.
            attempt = build_audit_log(
                "EXECUTION_STARTED", payload["apn_name"], payload["app_name"], payload,
                target_node=os.getenv("GGSN_TESTBED_HOST", "UNCONFIGURED") if is_live else "SIMULATION",
                status="STARTED", work_order_id=generated["work_order_id"],
                metadata={"assessment": assessment, "execution_mode": "live" if is_live else "simulation"},
            )
            try:
                st.session_state["history"] = append_history(attempt)
            except (OSError, ValueError) as exc:
                st.error(f"Execution stopped because audit persistence failed: {exc}")
                return
            with st.spinner("Processing command list..."):
                result = execute_script(parse_mml_script_commands(generated["script"]), is_live=is_live)
            st.session_state["execution_result"] = result
            entry = build_audit_log(
                "TESTBED_PUSH", payload["apn_name"], payload["app_name"], payload,
                target_node=result.target_host if is_live else "SIMULATION", status=result.status,
                work_order_id=generated["work_order_id"],
                metadata={"assessment": assessment, "execution_mode": "live" if is_live else "simulation",
                          "attempt_event_id": attempt["Event ID"], "duration_ms": result.duration_ms,
                          "commands_sent": result.commands_sent, "commands_acknowledged": result.commands_acknowledged,
                          "error_type": result.error_type},
            )
            try:
                st.session_state["history"] = append_history(entry)
                st.rerun()
            except (OSError, ValueError):
                st.error("Execution returned, but the outcome could not be persisted. Preserve the displayed logs and verify device state before retrying.")
        result = st.session_state.get("execution_result")
        if result:
            if result.failed:
                st.error(f"Execution stopped: {result.status}")
            elif result.status == "SIMULATED":
                st.info("Simulation completed; no commands were sent to a device.")
            else:
                st.warning("Commands sent; device configuration and service health are unverified.")
            st.code("\n".join(result.logs), language="text")
    with tabs[3]:
        st.json(redact_secrets(payload))
        st.caption(f"Artifact SHA-256: {assessment['script_sha256']}")