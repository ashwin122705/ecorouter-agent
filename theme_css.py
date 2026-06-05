"""Dynamic light / dark theme styles for the EcoRouter Streamlit dashboard."""

from __future__ import annotations


def build_theme_css(theme: str) -> str:
    dark = theme == "dark"
    t = _TOKENS["dark" if dark else "light"]

    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');
      html, body, [class*="css"] {{ font-family: 'DM Sans', system-ui, sans-serif; }}

      .stApp {{
        background-color: {t["app_bg"]};
        color: {t["text"]};
      }}
      .main .block-container {{
        padding-top: 1rem;
        max-width: 1400px;
        color: {t["text"]};
      }}

      /* --- Sidebar --- */
      [data-testid="stSidebar"] {{
        background-color: {t["sidebar_bg"]};
        border-right: 1px solid {t["border"]};
      }}
      [data-testid="stSidebar"] .stMarkdown h3,
      [data-testid="stSidebar"] .stMarkdown p,
      [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
      [data-testid="stSidebar"] label {{
        color: {t["sidebar_text"]} !important;
        font-weight: 600;
      }}
      [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        color: {t["text_muted"]} !important;
      }}

      /* Theme toggle — visible track + label in both modes */
      [data-testid="stSidebar"] [data-testid="stToggle"] [data-testid="stWidgetLabel"] p {{
        color: {t["sidebar_text"]} !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
      }}
      [data-testid="stSidebar"] [data-testid="stToggle"] [role="switch"] {{
        background-color: {t["toggle_track_off"]} !important;
        border: 2px solid {t["toggle_border"]} !important;
      }}
      [data-testid="stSidebar"] [data-testid="stToggle"] [role="switch"][aria-checked="true"] {{
        background-color: {t["toggle_track_on"]} !important;
        border-color: {t["toggle_track_on"]} !important;
      }}
      [data-testid="stSidebar"] [data-testid="stToggle"] [data-baseweb="thumb"] {{
        background-color: {t["toggle_thumb"]} !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.35) !important;
      }}

      .ecorouter-hero {{
        background: {t["hero_bg"]};
        border-radius: 20px; padding: 1.75rem 2.25rem; margin-bottom: 1.5rem;
        color: {t["hero_text"]};
        box-shadow: {t["hero_shadow"]};
        border: 1px solid {t["hero_border"]};
      }}
      .ecorouter-hero h1 {{ margin: 0; font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; color: {t["hero_text"]} !important; }}
      .ecorouter-hero p {{ margin: 0.5rem 0 0; color: {t["hero_sub"]} !important; font-size: 1.02rem; line-height: 1.55; }}
      .ecorouter-pill {{
        display: inline-block; background: {t["pill_bg"]};
        border: 1px solid {t["pill_border"]}; border-radius: 999px;
        padding: 0.28rem 0.75rem; font-size: 0.78rem; font-weight: 600;
        margin-right: 0.45rem; margin-top: 0.65rem; color: {t["hero_text"]} !important;
      }}

      .section-title {{
        font-size: 1.12rem; font-weight: 700; color: {t["text"]} !important;
        margin: 0 0 0.75rem 0; letter-spacing: -0.01em;
      }}
      .tab-intro {{
        background: {t["intro_bg"]};
        border-left: 4px solid {t["accent_green"]};
        padding: 0.8rem 1.1rem; border-radius: 0 12px 12px 0;
        font-size: 0.93rem; color: {t["intro_text"]} !important;
        margin-bottom: 1.2rem; line-height: 1.55;
      }}
      .tab-intro, .tab-intro * {{
        color: {t["intro_text"]} !important;
      }}
      .panel-card {{
        background: {t["surface"]}; border: 1px solid {t["border"]}; border-radius: 14px;
        padding: 1rem 1.15rem; margin-bottom: 1rem;
        box-shadow: {t["card_shadow"]}; color: {t["text"]} !important;
      }}
      .panel-card, .panel-card * {{
        color: {t["text"]} !important;
      }}
      .panel-card .panel-muted {{
        color: {t["text_muted"]} !important;
      }}

      /* Big icon summary stat cards */
      .stat-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
        gap: 12px;
        margin-bottom: 1.25rem;
      }}
      .stat-card {{
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid {t["border"]};
        background: {t["surface"]};
        box-shadow: {t["card_shadow"]};
        min-height: 88px;
      }}
      .stat-icon-wrap {{
        width: 56px;
        height: 56px;
        min-width: 56px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.85rem;
        line-height: 1;
        box-shadow: inset 0 -2px 0 rgba(0,0,0,0.12);
      }}
      .stat-icon-green {{ background: {t["icon_green"]}; }}
      .stat-icon-blue {{ background: {t["icon_blue"]}; }}
      .stat-icon-amber {{ background: {t["icon_amber"]}; }}
      .stat-icon-purple {{ background: {t["icon_purple"]}; }}
      .stat-icon-slate {{ background: {t["icon_slate"]}; }}
      .stat-icon-red {{ background: {t["icon_red"]}; }}
      .stat-body {{ flex: 1; min-width: 0; }}
      .stat-label {{
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: {t["text_muted"]} !important;
        margin-bottom: 4px;
        line-height: 1.2;
      }}
      .stat-value {{
        font-size: 1.45rem;
        font-weight: 800;
        color: {t["text"]} !important;
        line-height: 1.15;
        word-break: break-word;
      }}
      .stat-delta {{
        font-size: 0.78rem;
        font-weight: 700;
        color: {t["accent_green"]} !important;
        margin-top: 3px;
      }}

      .carbon-scroll-hint {{
        font-size: 0.8rem; color: {t["text_muted"]} !important; margin-bottom: 0.5rem; font-weight: 600;
      }}
      .carbon-chart-scroll {{
        overflow-x: auto; overflow-y: hidden;
        border: 1px solid {t["border"]}; border-radius: 14px;
        padding: 14px 12px 10px; background: {t["chart_scroll_bg"]};
        scrollbar-width: thin; scrollbar-color: {t["scroll_thumb"]} {t["scroll_track"]};
      }}
      .carbon-chart-scroll::-webkit-scrollbar {{ height: 12px; }}
      .carbon-chart-scroll::-webkit-scrollbar-track {{
        background: {t["scroll_track"]}; border-radius: 8px;
      }}
      .carbon-chart-scroll::-webkit-scrollbar-thumb {{
        background: {t["scroll_thumb"]}; border-radius: 8px;
        border: 2px solid {t["border"]};
      }}
      .carbon-chart-inner {{
        display: flex; align-items: flex-end; gap: 10px; padding-bottom: 4px;
      }}
      .carbon-bar-col {{
        display: flex; flex-direction: column; align-items: center; flex-shrink: 0;
      }}
      .carbon-bar-value {{
        font-size: 0.82rem; font-weight: 700; color: {t["text"]} !important; margin-bottom: 6px;
        white-space: nowrap;
      }}
      .carbon-bar-wrap {{
        width: 100%; display: flex; align-items: flex-end; justify-content: center;
        background: {t["bar_track"]}; border-radius: 8px 8px 4px 4px; padding: 4px 4px 0;
        border: 1px solid {t["border"]};
      }}
      .carbon-bar-fill {{
        width: 100%; min-height: 4px; border-radius: 6px 6px 2px 2px;
        box-shadow: {t["bar_shadow"]}; transition: height 0.25s ease;
        border: 1px solid rgba(0,0,0,0.12);
      }}
      .carbon-bar-region {{
        font-size: 0.72rem; font-weight: 700; color: {t["text"]} !important; margin-top: 8px;
        text-align: center; line-height: 1.2; word-break: break-all;
      }}
      .carbon-bar-label {{ font-size: 0.65rem; color: {t["text_muted"]} !important; text-align: center; margin-top: 2px; }}
      .carbon-bar-tariff {{
        font-size: 0.68rem; font-weight: 600; color: {t["accent_blue"]} !important; margin-top: 2px;
      }}
      .bar-badge-green {{
        display: inline-block; background: {t["badge_green_bg"]}; color: {t["badge_green_text"]} !important;
        font-size: 0.6rem; font-weight: 700; padding: 1px 5px; border-radius: 4px; margin-top: 3px;
      }}
      .carbon-legend {{
        margin-top: 0.75rem; font-size: 0.78rem; font-weight: 600; color: {t["text_muted"]} !important;
      }}
      .gradient-legend-bar {{
        height: 14px; border-radius: 8px; margin: 6px 0 4px;
        background: linear-gradient(90deg,
          #ecfdf5 0%, #86efac 18%, #fde047 40%, #fb923c 62%, #dc2626 82%, #450a0a 100%);
        border: 1px solid {t["border"]};
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.15);
      }}
      .gradient-legend-labels {{
        display: flex; justify-content: space-between; font-size: 0.72rem; color: {t["text_muted"]} !important;
      }}
      .gradient-legend-labels span {{ color: {t["text_muted"]} !important; }}
      .compare-baseline {{
        color: {t["baseline_text"]} !important; background: {t["baseline_bg"]};
        padding: 2px 6px; border-radius: 4px; font-weight: 600;
      }}
      .compare-eco {{
        color: {t["eco_text"]} !important; background: {t["eco_bg"]};
        padding: 2px 6px; border-radius: 4px; font-weight: 600;
      }}
      .compact-grid-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 0.8rem; color: {t["text"]} !important; }}
      .compact-grid-track {{
        flex: 1; height: 10px; background: {t["bar_track"]};
        border-radius: 999px; overflow: hidden; border: 1px solid {t["border"]};
      }}

      div[data-testid="stMetric"] {{
        background: {t["surface"]}; border: 1px solid {t["border"]}; border-radius: 12px;
        padding: 0.65rem 0.85rem; box-shadow: {t["card_shadow"]};
      }}
      div[data-testid="stMetric"] label,
      div[data-testid="stMetric"] [data-testid="stMetricLabel"] {{
        font-size: 0.78rem !important; font-weight: 600 !important; color: {t["text_muted"]} !important;
      }}
      div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        font-size: 1.15rem !important; font-weight: 700 !important; color: {t["text"]} !important;
      }}
      div[data-testid="stMetric"] [data-testid="stMetricValue"] * {{
        color: {t["text"]} !important;
      }}
      div[data-testid="stMetric"] [data-testid="stMetricDelta"] {{
        color: {t["text_muted"]} !important;
      }}

      [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
        border: 1px solid {t["border"]};
        border-radius: 12px;
        overflow: hidden;
      }}
      [data-testid="stDataFrame"] th {{
        background-color: {t["table_head"]} !important;
        color: {t["text"]} !important;
      }}

      [data-testid="stArrowVegaLiteChart"], [data-testid="stVegaLiteChart"] {{
        background-color: {t["chart_bg"]} !important;
        border: 1px solid {t["border"]};
        border-radius: 12px;
        padding: 0.5rem;
      }}

      [data-testid="stExpander"] {{
        background: {t["surface"]};
        border: 1px solid {t["border"]};
        border-radius: 12px;
      }}
      [data-testid="stExpander"] summary,
      [data-testid="stExpander"] summary * {{
        color: {t["text"]} !important;
      }}

      div[data-baseweb="tab-list"] {{
        background-color: {t["surface"]};
        border-radius: 12px;
        padding: 4px;
        border: 1px solid {t["border"]};
      }}
      .stTabs [data-baseweb="tab"] {{
        font-weight: 600; font-size: 0.92rem;
        color: {t["text_muted"]} !important;
      }}
      .stTabs [aria-selected="true"] {{
        background-color: {t["tab_active"]} !important;
        color: {t["text"]} !important;
        border-radius: 8px;
      }}

      div[data-testid="stAlert"] {{ border-radius: 10px !important; }}

      div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: {t["surface"]};
        border-color: {t["border"]} !important;
        color: {t["text"]};
      }}
      div[data-testid="stVerticalBlockBorderWrapper"] p,
      div[data-testid="stVerticalBlockBorderWrapper"] span,
      div[data-testid="stVerticalBlockBorderWrapper"] label {{
        color: {t["text"]} !important;
      }}

      .main .stSelectbox label, .main .stSlider label, .main .stRadio label,
      .main .stNumberInput label, .main .stTextArea label {{
        color: {t["text"]} !important;
      }}
      [data-baseweb="select"] > div, [data-baseweb="input"] > div {{
        background-color: {t["input_bg"]} !important;
        color: {t["text"]} !important;
        border-color: {t["border"]} !important;
      }}

      div.stButton > button {{
        background: {t["btn_secondary_bg"]};
        color: {t["text"]} !important;
        border: 1px solid {t["border"]};
        border-radius: 10px;
      }}
      div.stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, #16a34a, #15803d);
        border: none; color: white !important; font-weight: 700; border-radius: 12px; width: 100%;
        box-shadow: 0 4px 14px rgba(22, 163, 74, 0.35);
      }}

      .main [data-testid="stCaptionContainer"] {{
        color: {t["text_muted"]} !important;
      }}
      .main h3, .main h4 {{
        color: {t["text"]} !important;
      }}
      code, pre {{
        background: {t["code_bg"]} !important;
        color: {t["text"]} !important;
        border: 1px solid {t["border"]};
        border-radius: 8px;
      }}
    </style>
    """


_ASSIGNMENT_PALETTES = {
    "light": {
        "improved": ("#ecfdf5", "#14532d"),
        "changed": ("#fff7ed", "#9a3412"),
        "saved": ("#f0fdf4", "#166534"),
        "neutral": ("#f8fafc", "#334155"),
        "pos": "#15803d",
        "neg": "#b91c1c",
        "zero": "#64748b",
    },
    "dark": {
        "improved": ("#064e3b", "#a7f3d0"),
        "changed": ("#78350f", "#fed7aa"),
        "saved": ("#14532d", "#bbf7d0"),
        "neutral": ("#1e293b", "#e2e8f0"),
        "pos": "#4ade80",
        "neg": "#f87171",
        "zero": "#94a3b8",
    },
}


def assignment_row_colors(theme: str) -> dict[str, tuple[str, str] | str]:
    return _ASSIGNMENT_PALETTES["dark" if theme == "dark" else "light"]


_TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "app_bg": "#f8fafc",
        "sidebar_bg": "#ffffff",
        "sidebar_text": "#0f172a",
        "surface": "#ffffff",
        "text": "#0f172a",
        "text_muted": "#475569",
        "border": "#cbd5e1",
        "toggle_track_off": "#94a3b8",
        "toggle_track_on": "#15803d",
        "toggle_thumb": "#ffffff",
        "toggle_border": "#64748b",
        "hero_bg": "linear-gradient(135deg, #0c1222 0%, #14532d 45%, #064e3b 100%)",
        "hero_text": "#f8fafc",
        "hero_sub": "#cbd5e1",
        "hero_border": "transparent",
        "hero_shadow": "0 12px 40px rgba(15, 23, 42, 0.18)",
        "pill_bg": "rgba(255,255,255,0.14)",
        "pill_border": "rgba(255,255,255,0.22)",
        "intro_bg": "#ecfdf5",
        "intro_text": "#14532d",
        "accent_green": "#15803d",
        "accent_blue": "#0369a1",
        "card_shadow": "0 2px 8px rgba(15, 23, 42, 0.06)",
        "chart_scroll_bg": "linear-gradient(180deg, #ffffff 0%, #e2e8f0 55%, #94a3b8 100%)",
        "scroll_track": "#e2e8f0",
        "scroll_thumb": "linear-gradient(90deg, #86efac, #450a0a)",
        "bar_track": "linear-gradient(180deg, #f1f5f9 0%, #64748b 100%)",
        "bar_shadow": "0 3px 10px rgba(15, 23, 42, 0.25)",
        "badge_green_bg": "#dcfce7",
        "badge_green_text": "#166534",
        "baseline_bg": "#fef2f2",
        "baseline_text": "#991b1b",
        "eco_bg": "#ecfdf5",
        "eco_text": "#15803d",
        "chart_bg": "#ffffff",
        "table_head": "#f1f5f9",
        "tab_active": "#dcfce7",
        "input_bg": "#ffffff",
        "btn_secondary_bg": "#f1f5f9",
        "code_bg": "#f1f5f9",
        "icon_green": "#16a34a",
        "icon_blue": "#2563eb",
        "icon_amber": "#d97706",
        "icon_purple": "#7c3aed",
        "icon_slate": "#475569",
        "icon_red": "#dc2626",
    },
    "dark": {
        "app_bg": "#0b1120",
        "sidebar_bg": "#111827",
        "sidebar_text": "#f1f5f9",
        "surface": "#1e293b",
        "text": "#f8fafc",
        "text_muted": "#94a3b8",
        "border": "#475569",
        "toggle_track_off": "#475569",
        "toggle_track_on": "#22c55e",
        "toggle_thumb": "#f8fafc",
        "toggle_border": "#64748b",
        "hero_bg": "linear-gradient(135deg, #020617 0%, #064e3b 50%, #0f172a 100%)",
        "hero_text": "#f8fafc",
        "hero_sub": "#cbd5e1",
        "hero_border": "#334155",
        "hero_shadow": "0 12px 40px rgba(0, 0, 0, 0.45)",
        "pill_bg": "rgba(255,255,255,0.08)",
        "pill_border": "rgba(255,255,255,0.16)",
        "intro_bg": "#064e3b",
        "intro_text": "#ecfdf5",
        "accent_green": "#4ade80",
        "accent_blue": "#38bdf8",
        "card_shadow": "0 2px 12px rgba(0, 0, 0, 0.35)",
        "chart_scroll_bg": "linear-gradient(180deg, #1e293b 0%, #334155 55%, #0f172a 100%)",
        "scroll_track": "#334155",
        "scroll_thumb": "linear-gradient(90deg, #4ade80, #7f1d1d)",
        "bar_track": "linear-gradient(180deg, #334155 0%, #0f172a 100%)",
        "bar_shadow": "0 3px 10px rgba(0, 0, 0, 0.5)",
        "badge_green_bg": "#064e3b",
        "badge_green_text": "#6ee7b7",
        "baseline_bg": "#450a0a",
        "baseline_text": "#fecaca",
        "eco_bg": "#064e3b",
        "eco_text": "#6ee7b7",
        "chart_bg": "#1e293b",
        "table_head": "#334155",
        "tab_active": "#064e3b",
        "input_bg": "#1e293b",
        "btn_secondary_bg": "#334155",
        "code_bg": "#0f172a",
        "icon_green": "#22c55e",
        "icon_blue": "#3b82f6",
        "icon_amber": "#f59e0b",
        "icon_purple": "#a78bfa",
        "icon_slate": "#64748b",
        "icon_red": "#ef4444",
    },
}
