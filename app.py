import streamlit as st
from core.services.audit_service import load_history
from ui.styles import inject_custom_css
from ui.components import render_live_header, render_kpi_bento, render_sidebar
from ui.views import render_manual_view, render_batch_view, render_audit_view

# ═══════════════════════════════════════════════════════════════════════════════
# RELPOOL CORE AUTOMATION COMMAND CENTER
# Group Core Planning & Engineering - MCPE Core 2026
# ═══════════════════════════════════════════════════════════════════════════════

# 1. Page Configuration
st.set_page_config(
    page_title="RELPOOL - Core Automation Command Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inject Cyberpunk NOC Dark Theme CSS
inject_custom_css()

# 3. Persistent History State Initialization
try:
    st.session_state["history"] = load_history()
except (OSError, ValueError) as exc:
    st.error(f"Audit history is unavailable. Provisioning is stopped: {exc}")
    st.stop()

# 4. Render Sidebar Component
render_sidebar()

# 5. Render Top Header & KPI Bento Grid
render_live_header()
render_kpi_bento()

# 6. Mode Input Provisioning Selector
input_mode = st.radio(
    "Pilih Mode Input Provisioning:",
    ["⚙️ Manual Form Input", "📁 Batch Processing (Upload CIQ Excel/CSV)"],
    horizontal=True
)
st.divider()

# 7. Render Sub-Views
if "Manual Form" in input_mode:
    render_manual_view()
else:
    render_batch_view()

# 8. Render Audit Trail & Payload Inspector
render_audit_view()
