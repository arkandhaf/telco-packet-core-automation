import streamlit as st


def inject_custom_css():
    """
    Menginjeksikan styling Dark Tactile Bento UI (terinspirasi dari desain modern matte dark)
    langsung ke dalam komponen Streamlit native.
    """
    st.markdown("""
    <style>
        /* System fallbacks allow offline/VPN use without external font requests. */

        /* ── Base App Canvas ── */
        .stApp {
            background-color: #0B0D11 !important;
            color: #E2E8F0 !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        /* ── Top Live Status Bar ── */
        .live-bar {
            background: #15181E;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 9999px;
            padding: 8px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4),
                        inset 0 1px 1px rgba(255, 255, 255, 0.05);
        }
        .live-bar-title {
            font-weight: 700;
            font-size: 13px;
            color: #FFFFFF;
            letter-spacing: 0.3px;
            margin-left: 10px;
        }
        .live-bar-meta {
            font-size: 11px;
            color: #94A3B8;
            font-family: 'Plus Jakarta Sans', sans-serif;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .live-bar-meta b {
            color: #94A3B8;
        }

        /* ── Pill Status Badges (Matching image) ── */
        .pill-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 12px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.2px;
        }
        .pill-lime {
            background-color: #98E842;
            color: #0B0D11;
        }
        .pill-yellow {
            background-color: #F7C948;
            color: #0B0D11;
        }
        .pill-purple {
            background-color: #625DF5;
            color: #FFFFFF;
        }
        .pill-dark {
            background-color: #1E222A;
            color: #94A3B8;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        /* ── Tactile KPI Bento Cards ── */
        .metric-card {
            background: #15181E;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 18px 16px;
            text-align: center;
            box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5),
                        inset 0 1px 1px rgba(255, 255, 255, 0.04);
            transition: all 0.25s ease;
        }
        .metric-card:hover {
            border-color: rgba(255, 255, 255, 0.12);
            transform: translateY(-2px);
        }
        .metric-label {
            font-size: 10px;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .metric-value {
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.3px;
            overflow-wrap: anywhere;
        }
        .metric-detail { margin-top: 8px; }
        .live-bar-main { display: flex; align-items: center; gap: 8px; }
        .live-bar, .live-bar-meta, .live-bar-main { flex-wrap: wrap; }
        .metric-label { color: #94A3B8; }
        button:focus-visible, a:focus-visible { outline: 2px solid #98E842 !important; outline-offset: 3px; }
        @media (max-width: 768px) {
            .live-bar { border-radius: 18px; gap: 12px; padding: 16px; }
            .live-bar-title { margin-left: 0; }
            .metric-card { min-height: 120px; padding: 14px 10px; }
            div[data-testid="stForm"] { padding: 16px !important; }
            .stTabs [data-baseweb="tab-list"] { overflow-x: auto; border-radius: 14px !important; }
        }
        @media (prefers-reduced-motion: reduce) {
            .metric-card, .stButton > button, .stDownloadButton > button { transition: none !important; transform: none !important; }
        }

        /* ── Streamlit Form Container (Matte Card) ── */
        div[data-testid="stForm"] {
            background: #15181E !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-radius: 24px !important;
            padding: 28px !important;
            box-shadow: 0 12px 36px -12px rgba(0, 0, 0, 0.6),
                        inset 0 1px 1px rgba(255, 255, 255, 0.04) !important;
        }

        /* ── Form Inputs & Selectboxes (Tactile Nested Look) ── */
        .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {
            background-color: #1E222A !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 14px !important;
            color: #FFFFFF !important;
            font-size: 13px !important;
            box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3) !important;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: #625DF5 !important;
            box-shadow: 0 0 0 2px rgba(98, 93, 245, 0.2) !important;
        }

        /* ── Pill Buttons (Primary Submit: Vibrant Soft Purple) ── */
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button {
            background-color: #625DF5 !important;
            background-image: none !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 9999px !important;
            padding: 10px 24px !important;
            font-size: 13px !important;
            font-weight: 700 !important;
            letter-spacing: 0.3px !important;
            box-shadow: 0 8px 24px -4px rgba(98, 93, 245, 0.4) !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button:hover {
            background-color: #504AE3 !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 12px 28px -4px rgba(98, 93, 245, 0.5) !important;
        }

        /* ── Secondary / Download Buttons (Dark Pill) ── */
        .stDownloadButton > button,
        .stButton > button:not([kind="primary"]) {
            background-color: #1E222A !important;
            color: #CBD5E1 !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 9999px !important;
            padding: 8px 20px !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
            transition: all 0.2s ease !important;
        }
        .stDownloadButton > button:hover,
        .stButton > button:not([kind="primary"]):hover {
            background-color: #262B35 !important;
            border-color: rgba(255, 255, 255, 0.12) !important;
            color: #FFFFFF !important;
            transform: translateY(-1px) !important;
        }

        /* ── Pill Tabs (Matching image tabs) ── */
        .stTabs [data-baseweb="tab-list"] {
            background-color: #12151B !important;
            border-radius: 9999px !important;
            padding: 4px !important;
            gap: 4px !important;
            border: 1px solid rgba(255, 255, 255, 0.04) !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 9999px !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            padding: 6px 18px !important;
            color: #8E95A3 !important;
            border: none !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #222731 !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        }
        .stTabs [data-baseweb="tab-panel"] {
            background: #15181E !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-radius: 20px !important;
            padding: 20px !important;
            margin-top: 12px !important;
        }

        /* ── Code Blocks (Clean Dark Terminal) ── */
        .stCodeBlock {
            background-color: #101217 !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-radius: 16px !important;
            box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.4) !important;
        }
        .stCodeBlock pre {
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 12px !important;
            line-height: 1.65 !important;
            color: #E2E8F0 !important;
        }

        /* ── Table Styling ── */
        .stDataFrame [data-testid="stDataFrameResizable"] {
            background-color: #15181E !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-radius: 18px !important;
            overflow: hidden !important;
        }

        /* ── Expander ── */
        .streamlit-expanderHeader {
            background: #1E222A !important;
            border-radius: 14px !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            font-size: 13px !important;
            font-weight: 600 !important;
        }

        /* ── Radio Buttons ── */
        .stRadio div[role="radiogroup"] {
            gap: 12px;
        }

        /* ── Section Tag ── */
        .section-tag {
            background: #1E222A;
            color: #98E842;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 10px;
            font-weight: 700;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        /* ── Footer ── */
        .footer-bar {
            text-align: center;
            padding: 24px;
            margin-top: 40px;
            font-size: 11px;
            color: #64748B;
            border-top: 1px solid rgba(255, 255, 255, 0.04);
        }

        /* Hide Streamlit Header & Watermarks */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header[data-testid="stHeader"] {
            background: rgba(11, 13, 17, 0.8) !important;
            backdrop-filter: blur(10px);
        }
    </style>
    """, unsafe_allow_html=True)
