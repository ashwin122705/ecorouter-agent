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
        padding-top: 0.75rem;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
        max-width: min(2200px, 98vw);
        color: {t["text"]};
      }}
      [data-testid="stAppViewContainer"] section.main > div {{
        max-width: 100%;
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
        border-radius: 22px; padding: 1.85rem 2.35rem 1.65rem; margin-bottom: 1.35rem;
        color: {t["hero_text"]};
        box-shadow: {t["hero_shadow"]};
        border: 1px solid {t["hero_border"]};
      }}
      .hero-top {{
        display: flex; flex-wrap: wrap; align-items: stretch;
        justify-content: space-between; gap: 1.5rem;
      }}
      .hero-brand {{ flex: 1 1 420px; min-width: 280px; }}
      .hero-eyebrow {{
        font-size: 0.78rem; font-weight: 700; letter-spacing: 0.14em;
        text-transform: uppercase; color: {t["hero_accent"]} !important; margin-bottom: 0.45rem;
      }}
      .ecorouter-hero h1 {{
        margin: 0; font-size: 2.65rem; font-weight: 800; letter-spacing: -0.03em;
        color: {t["hero_text"]} !important; line-height: 1.05;
      }}
      .hero-lead {{
        margin: 0.75rem 0 0; color: {t["hero_sub"]} !important;
        font-size: 1.06rem; line-height: 1.6; max-width: 52rem;
      }}
      .hero-impact {{
        display: flex; flex-wrap: wrap; gap: 10px;
        flex: 0 1 auto; align-items: stretch;
      }}
      .hero-stat {{
        background: {t["hero_stat_bg"]};
        border: 1px solid {t["hero_stat_border"]};
        border-radius: 14px; padding: 0.85rem 1rem; min-width: 118px;
        text-align: center;
      }}
      .hero-stat-num {{
        display: block; font-size: 1.55rem; font-weight: 800;
        color: {t["hero_text"]} !important; line-height: 1.1;
      }}
      .hero-stat-lbl {{
        display: block; font-size: 0.68rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.06em;
        color: {t["hero_sub"]} !important; margin-top: 4px;
      }}
      .hero-stat-highlight {{
        border-color: {t["hero_accent"]};
        box-shadow: 0 0 0 1px {t["hero_accent"]} inset;
      }}
      .hero-stat-highlight .hero-stat-num {{
        color: {t["hero_accent"]} !important;
      }}
      .hero-pills {{
        margin-top: 1.15rem; padding-top: 1rem;
        border-top: 1px solid {t["hero_divider"]};
      }}
      .ecorouter-pill {{
        display: inline-block; background: {t["pill_bg"]};
        border: 1px solid {t["pill_border"]}; border-radius: 999px;
        padding: 0.28rem 0.75rem; font-size: 0.78rem; font-weight: 600;
        margin-right: 0.45rem; margin-top: 0.5rem; color: {t["hero_text"]} !important;
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
        border: 2px solid transparent;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.28);
        filter: saturate(1.15) contrast(1.08);
      }}
      .stat-icon-green {{
        background: {t["icon_green_bg"]};
        border-color: {t["icon_green_border"]};
      }}
      .stat-icon-blue {{
        background: {t["icon_blue_bg"]};
        border-color: {t["icon_blue_border"]};
      }}
      .stat-icon-amber {{
        background: {t["icon_amber_bg"]};
        border-color: {t["icon_amber_border"]};
      }}
      .stat-icon-purple {{
        background: {t["icon_purple_bg"]};
        border-color: {t["icon_purple_border"]};
      }}
      .stat-icon-slate {{
        background: {t["icon_slate_bg"]};
        border-color: {t["icon_slate_border"]};
      }}
      .stat-icon-red {{
        background: {t["icon_red_bg"]};
        border-color: {t["icon_red_border"]};
      }}
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
      .carbon-chart-plot {{
        display: flex;
        flex-direction: column;
      }}
      .carbon-bars-row {{
        display: flex;
        align-items: flex-end;
        gap: 10px;
      }}
      .carbon-baseline {{
        height: 2px;
        background: {t["border"]};
        margin: 0 0 8px 0;
        border-radius: 999px;
      }}
      .carbon-labels-row {{
        display: flex;
        gap: 10px;
        align-items: flex-start;
      }}
      .carbon-bar-slot, .carbon-label-slot {{
        display: flex;
        flex-direction: column;
        align-items: center;
        flex-shrink: 0;
      }}
      .carbon-badge-slot {{
        min-height: 18px;
        margin-top: 3px;
        text-align: center;
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
        font-size: 0.72rem; font-weight: 700; color: {t["text"]} !important; margin-top: 0;
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
        "hero_accent": "#86efac",
        "hero_stat_bg": "rgba(255,255,255,0.1)",
        "hero_stat_border": "rgba(255,255,255,0.18)",
        "hero_divider": "rgba(255,255,255,0.14)",
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
        "icon_green_bg": "#dcfce7",
        "icon_green_border": "#15803d",
        "icon_blue_bg": "#dbeafe",
        "icon_blue_border": "#1d4ed8",
        "icon_amber_bg": "#fef3c7",
        "icon_amber_border": "#b45309",
        "icon_purple_bg": "#ede9fe",
        "icon_purple_border": "#6d28d9",
        "icon_slate_bg": "#e2e8f0",
        "icon_slate_border": "#334155",
        "icon_red_bg": "#fee2e2",
        "icon_red_border": "#b91c1c",
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
        "hero_accent": "#4ade80",
        "hero_stat_bg": "rgba(15, 23, 42, 0.55)",
        "hero_stat_border": "rgba(71, 85, 105, 0.9)",
        "hero_divider": "rgba(71, 85, 105, 0.65)",
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
        "icon_green_bg": "#064e3b",
        "icon_green_border": "#4ade80",
        "icon_blue_bg": "#1e3a8a",
        "icon_blue_border": "#60a5fa",
        "icon_amber_bg": "#78350f",
        "icon_amber_border": "#fbbf24",
        "icon_purple_bg": "#4c1d95",
        "icon_purple_border": "#c4b5fd",
        "icon_slate_bg": "#1e293b",
        "icon_slate_border": "#94a3b8",
        "icon_red_bg": "#7f1d1d",
        "icon_red_border": "#f87171",
    },
}
