# =============================================================
#  🚗 Uber Supply-Demand Gap Analysis — Streamlit Dashboard
#  Author   : Claude AI
#  Run      : streamlit run app.py
#  Requires : streamlit, pandas, numpy, matplotlib, seaborn, plotly
# =============================================================

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
import sqlite3
import warnings
import io
import os

warnings.filterwarnings("ignore")

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Uber Supply-Demand Gap Analysis",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .main { background-color: #F7F9FC; }

    /* KPI Cards */
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-top: 4px solid;
    }
    .kpi-value { font-size: 2rem; font-weight: 700; margin: 0; }
    .kpi-label { font-size: 0.85rem; color: #666; margin: 4px 0 0 0; }

    /* Section headers */
    .section-header {
        background: linear-gradient(135deg, #1F4E79, #2E75B6);
        color: white;
        padding: 10px 20px;
        border-radius: 8px;
        margin: 16px 0 12px 0;
        font-size: 1.1rem;
        font-weight: 600;
    }

    /* Insight boxes */
    .insight-box {
        background: #EBF3FB;
        border-left: 4px solid #2E75B6;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 0.92rem;
    }

    /* Warning boxes */
    .warn-box {
        background: #FFF3E0;
        border-left: 4px solid #ED7D31;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 0.92rem;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #EBF3FB;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 1.  DATA LOADING & CACHING
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Loading & cleaning data...")
def load_data(filepath: str) -> pd.DataFrame:
    """Load and preprocess the Uber dataset. Handles both mixed timestamp formats."""
    df = pd.read_csv(filepath)

    # ── Parse mixed-format timestamps ────────────────────────
    def parse_ts(series):
        fmt1 = pd.to_datetime(series, format="%d/%m/%Y %H:%M",    errors="coerce")
        fmt2 = pd.to_datetime(series, format="%d-%m-%Y %H:%M:%S", errors="coerce")
        return fmt1.fillna(fmt2)

    df["Request_ts"] = parse_ts(df["Request timestamp"])
    df["Drop_ts"]    = parse_ts(df["Drop timestamp"])

    # ── Rename for SQL/Python compatibility ──────────────────
    df.rename(columns={
        "Request id":   "Request_id",
        "Pickup point": "Pickup_point",
        "Driver id":    "Driver_id",
    }, inplace=True)

    # ── Feature Engineering ──────────────────────────────────
    df["Hour"]        = df["Request_ts"].dt.hour
    df["Day"]         = df["Request_ts"].dt.day
    df["Weekday"]     = df["Request_ts"].dt.day_name()
    df["Date"]        = df["Request_ts"].dt.date
    df["Duration_min"]= (df["Drop_ts"] - df["Request_ts"]).dt.total_seconds() / 60
    df["Unfulfilled"] = df["Status"].isin(["Cancelled", "No Cars Available"]).astype(int)

    # Time-slot buckets
    def time_slot(h):
        if   0  <= h < 5:  return "Early Morning"
        elif 5  <= h < 10: return "Morning"
        elif 10 <= h < 14: return "Afternoon"
        elif 14 <= h < 18: return "Evening"
        elif 18 <= h < 21: return "Late Night"
        else:              return "Night"

    df["Time_slot"] = df["Hour"].apply(time_slot)
    return df


@st.cache_data(show_spinner=False)
def build_sqlite(df: pd.DataFrame):
    """Load cleaned DataFrame into an in-memory SQLite DB."""
    conn = sqlite3.connect(":memory:")
    df.to_sql("uber", conn, if_exists="replace", index=False)
    return conn


# ── Colour palette ────────────────────────────────────────────
C_DARK   = "#1F4E79"
C_BLUE   = "#2E75B6"
C_LBLUE  = "#BDD7EE"
C_ORANGE = "#ED7D31"
C_GREEN  = "#70AD47"
C_RED    = "#C00000"
C_GRAY   = "#595959"
C_BG     = "#F7F9FC"
SLOT_ORDER = ["Early Morning", "Morning", "Afternoon", "Evening", "Late Night", "Night"]


# ══════════════════════════════════════════════════════════════
# HELPER: render matplotlib figure in Streamlit
# ══════════════════════════════════════════════════════════════
def render_fig(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    st.image(buf)
    plt.close(fig)


# ══════════════════════════════════════════════════════════════
# 2.  SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Uber_logo_2018.svg/200px-Uber_logo_2018.svg.png",
             width=120)
    st.markdown("## 🚗 Uber EDA Dashboard")
    st.markdown("Supply-Demand Gap Analysis")
    st.markdown("---")

    # ── File uploader ─────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload CSV",
        type=["csv"],
        help="Upload Uber_Request_Data.csv",
    )

    # ── Filters ───────────────────────────────────────────────
    st.markdown("### 🎛️ Filters")

    st.markdown("---")
    st.markdown("**Dataset Info**")
    st.info("Jul 11–15, 2016 | 6,745 requests | 5 days")

    st.markdown("---")
    st.caption("Built with ❤️ using Streamlit")


# ══════════════════════════════════════════════════════════════
# 3.  LOAD DATA
# ══════════════════════════════════════════════════════════════
# Determine data source
if uploaded is not None:
    try:
        df_full = load_data(uploaded)
        st.sidebar.success("✅ File uploaded successfully!")
    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")
        st.stop()
else:
    # Look for CSV in same directory
    default_path = os.path.join(os.path.dirname(__file__), "Uber_Request_Data.csv")
    if os.path.exists(default_path):
        df_full = load_data(default_path)
    else:
        st.markdown("## 🚗 Uber Supply-Demand Gap Analysis")
        st.info("""
        **👈 Please upload your dataset using the sidebar.**

        Expected file: `Uber_Request_Data.csv`

        Columns required:
        - `Request id`, `Pickup point`, `Driver id`, `Status`
        - `Request timestamp`, `Drop timestamp`
        """)
        st.stop()

# ── Sidebar dynamic filters ───────────────────────────────────
with st.sidebar:
    pickup_filter = st.multiselect(
        "Pickup Point",
        options=df_full["Pickup_point"].unique().tolist(),
        default=df_full["Pickup_point"].unique().tolist(),
    )
    status_filter = st.multiselect(
        "Status",
        options=df_full["Status"].unique().tolist(),
        default=df_full["Status"].unique().tolist(),
    )
    hour_range = st.slider("Hour Range", 0, 23, (0, 23))

# Apply filters
df = df_full[
    df_full["Pickup_point"].isin(pickup_filter) &
    df_full["Status"].isin(status_filter) &
    df_full["Hour"].between(hour_range[0], hour_range[1])
].copy()

conn = build_sqlite(df)


# ══════════════════════════════════════════════════════════════
# 4.  MAIN HEADER
# ══════════════════════════════════════════════════════════════
st.markdown("""
<div style='background:linear-gradient(135deg,#1F4E79,#2E75B6);
            padding:24px 32px; border-radius:14px; margin-bottom:20px;'>
  <h1 style='color:white;margin:0;font-size:2rem;'>
    🚗 Uber Supply-Demand Gap Analysis
  </h1>
  <p style='color:#BDD7EE;margin:6px 0 0 0;font-size:1rem;'>
    Exploratory Data Analysis Dashboard · Jul 11–15, 2016 · 6,745 Requests
  </p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 5.  KPI CARDS
# ══════════════════════════════════════════════════════════════
total      = len(df)
completed  = (df["Status"] == "Trip Completed").sum()
cancelled  = (df["Status"] == "Cancelled").sum()
no_car     = (df["Status"] == "No Cars Available").sum()
comp_rate  = round(completed / total * 100, 1) if total else 0
unfulfilled= cancelled + no_car
avg_dur    = df.loc[df["Status"] == "Trip Completed", "Duration_min"].mean()
peak_hour  = int(df.groupby("Hour").size().idxmax()) if total else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)

def kpi(col, value, label, color):
    col.markdown(f"""
    <div class='kpi-card' style='border-color:{color}'>
        <p class='kpi-value' style='color:{color}'>{value}</p>
        <p class='kpi-label'>{label}</p>
    </div>""", unsafe_allow_html=True)

kpi(k1, f"{total:,}",         "Total Requests",      C_BLUE)
kpi(k2, f"{completed:,}",     "Completed Trips",     C_GREEN)
kpi(k3, f"{cancelled:,}",     "Cancellations",       C_RED)
kpi(k4, f"{no_car:,}",        "No Cars Available",   C_ORANGE)
kpi(k5, f"{comp_rate}%",      "Completion Rate",     "#1F7A4C")
kpi(k6, f"{avg_dur:.1f} min" if not np.isnan(avg_dur) else "N/A",
        "Avg Trip Duration", C_DARK)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 6.  TABS
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview",
    "🕐 Time Analysis",
    "📍 Location Analysis",
    "🔬 Deep Dive",
    "🗃️ SQL Insights",
    "📋 Raw Data",
])


# ══════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown("<div class='section-header'>📊 Overall Status Distribution</div>",
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # Chart 1 — Bar + Pie
    with col1:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor=C_BG)
        status_counts = df["Status"].value_counts()
        colors_pie = [C_GREEN, C_ORANGE, C_RED]

        axes[0].bar(status_counts.index, status_counts.values,
                    color=colors_pie, edgecolor="white", linewidth=1.3)
        axes[0].set_title("Status Count", fontweight="bold", color=C_DARK)
        axes[0].set_ylabel("Requests")
        axes[0].set_facecolor(C_BG)
        axes[0].spines[["top","right"]].set_visible(False)
        for i, v in enumerate(status_counts.values):
            axes[0].text(i, v + 30, str(v), ha="center", fontweight="bold", fontsize=9)

        wedges, texts, autos = axes[1].pie(
            status_counts.values, labels=status_counts.index,
            autopct="%1.1f%%", colors=colors_pie, startangle=140,
            wedgeprops=dict(edgecolor="white", linewidth=2))
        for at in autos: at.set_fontsize(9); at.set_fontweight("bold")
        axes[1].set_title("Status Share", fontweight="bold", color=C_DARK)
        axes[1].set_facecolor(C_BG)

        fig.suptitle("Overall Request Status Distribution", fontsize=13,
                     fontweight="bold", color=C_DARK)
        plt.tight_layout()
        render_fig(fig)

    with col2:
        st.markdown("<div class='insight-box'>", unsafe_allow_html=True)
        st.markdown(f"""
**Key Insights:**
- Only **{comp_rate}%** of rides are completed — critically low for a ride-hailing platform
- **No Cars Available ({round(no_car/total*100,1)}%)** — supply-side failure, not rider behaviour
- **Cancelled ({round(cancelled/total*100,1)}%)** — near-equal to No Cars, dual failure mode
- Combined failure: **{round(unfulfilled/total*100,1)}%** of all requests unfulfilled
        """)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='warn-box'>⚠️ <b>Business Risk:</b> "
                    "46%+ failure rate signals structural supply-demand mismatch. "
                    "Every unfulfilled request = lost revenue + potential churn.</div>",
                    unsafe_allow_html=True)

    st.markdown("<div class='section-header'>📍 Pickup Point Distribution</div>",
                unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        fig, ax = plt.subplots(figsize=(7, 4), facecolor=C_BG)
        pickup_counts = df["Pickup_point"].value_counts()
        bars = ax.barh(pickup_counts.index, pickup_counts.values,
                       color=[C_ORANGE, C_BLUE], edgecolor="white", height=0.5)
        for bar, val in zip(bars, pickup_counts.values):
            ax.text(val + 30, bar.get_y() + bar.get_height()/2,
                    f"{val:,}", va="center", fontweight="bold")
        ax.set_title("Requests by Pickup Point", fontweight="bold", color=C_DARK)
        ax.set_xlabel("Number of Requests")
        ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
        plt.tight_layout(); render_fig(fig)

    with col4:
        # Status by pickup point table
        cross = pd.crosstab(df["Pickup_point"], df["Status"])
        cross_pct = cross.div(cross.sum(axis=1), axis=0).mul(100).round(1)
        st.markdown("**Completion Rate by Pickup Point:**")
        st.dataframe(
            cross_pct.style
            .background_gradient(cmap="RdYlGn", vmin=0, vmax=100)
            .format("{:.1f}%"),
            use_container_width=True
        )
        st.markdown("<div class='insight-box'>Airport completion rate is <b>~20pp lower</b> "
                    "than City — driven by chronic No Cars Available failures at Airport.</div>",
                    unsafe_allow_html=True)

    # Supply-Demand Funnel
    st.markdown("<div class='section-header'>🔻 Supply-Demand Funnel</div>",
                unsafe_allow_html=True)

    fig, ax = plt.subplots(figsize=(9, 4), facecolor=C_BG)
    labels  = ["Total Requests", "Trip Completed", "Unfulfilled"]
    values  = [total, int(completed), int(unfulfilled)]
    colors  = [C_BLUE, C_GREEN, C_RED]
    bars = ax.barh(labels, values, color=colors, edgecolor="white", height=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 50, bar.get_y() + bar.get_height()/2,
                f"{val:,}  ({val/total*100:.1f}%)", va="center", fontweight="bold")
    ax.set_title("Supply-Demand Funnel Overview", fontweight="bold", color=C_DARK)
    ax.set_xlabel("Number of Requests"); ax.set_xlim(0, total * 1.35)
    ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout(); render_fig(fig)


# ══════════════════════════════════════════════════════════════
# TAB 2 — TIME ANALYSIS
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown("<div class='section-header'>⏰ Hourly Demand Pattern</div>",
                unsafe_allow_html=True)

    hour_counts = df.groupby("Hour").size()

    fig, ax = plt.subplots(figsize=(14, 5), facecolor=C_BG)
    ax.fill_between(hour_counts.index, hour_counts.values, alpha=0.25, color=C_BLUE)
    ax.plot(hour_counts.index, hour_counts.values, "o-", color=C_BLUE,
            linewidth=2.5, markersize=7)
    ax.axvspan(5, 9.5,  alpha=0.12, color=C_ORANGE, label="Morning Rush (5–9)")
    ax.axvspan(17, 21,  alpha=0.12, color=C_RED,    label="Evening Rush (17–21)")
    peak = int(hour_counts.idxmax())
    ax.bar(peak, hour_counts[peak], color=C_ORANGE, alpha=0.6, width=0.8)
    ax.text(peak, hour_counts[peak] + 8, f"Peak: {hour_counts[peak]}",
            ha="center", color=C_ORANGE, fontweight="bold")
    ax.set_xticks(range(24)); ax.set_title("Total Requests by Hour of Day",
                                            fontweight="bold", color=C_DARK)
    ax.set_xlabel("Hour"); ax.set_ylabel("Requests")
    ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
    ax.legend(); plt.tight_layout(); render_fig(fig)

    col1, col2 = st.columns(2)

    # Hourly stacked — status breakdown
    with col1:
        st.markdown("**Hourly Status Composition (%)**")
        hs = df[df["Unfulfilled"]==1].groupby(["Hour","Status"]).size().unstack(fill_value=0)
        hs_pct = df.groupby(["Hour","Status"]).size().unstack(fill_value=0)
        hs_pct = hs_pct.div(hs_pct.sum(axis=1), axis=0) * 100

        fig, ax = plt.subplots(figsize=(12, 5), facecolor=C_BG)
        completed_col = hs_pct.get("Trip Completed", pd.Series(0, index=range(24)))
        cancelled_col = hs_pct.get("Cancelled",      pd.Series(0, index=range(24)))
        nocar_col     = hs_pct.get("No Cars Available", pd.Series(0, index=range(24)))
        ax.bar(hs_pct.index, completed_col, label="Completed",         color=C_GREEN,  edgecolor="white")
        ax.bar(hs_pct.index, cancelled_col, bottom=completed_col,      label="Cancelled", color=C_RED,    edgecolor="white")
        ax.bar(hs_pct.index, nocar_col,     bottom=completed_col+cancelled_col,
               label="No Cars Available", color=C_ORANGE, edgecolor="white")
        ax.axhline(50, color="white", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.set_title("Status Composition by Hour (%)", fontweight="bold", color=C_DARK)
        ax.set_xlabel("Hour"); ax.set_ylabel("% Share")
        ax.set_xticks(range(24)); ax.legend(loc="upper left", fontsize=8)
        ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
        plt.tight_layout(); render_fig(fig)

    # Completion rate line
    with col2:
        st.markdown("**Completion Rate by Hour**")
        comp_rate_hr = df.groupby("Hour").apply(
            lambda x: (x["Status"] == "Trip Completed").sum() / len(x) * 100)
        cancel_rate_hr = df.groupby("Hour").apply(
            lambda x: (x["Status"] == "Cancelled").sum() / len(x) * 100)
        nocar_rate_hr = df.groupby("Hour").apply(
            lambda x: (x["Status"] == "No Cars Available").sum() / len(x) * 100)

        fig, ax = plt.subplots(figsize=(12, 5), facecolor=C_BG)
        ax.plot(comp_rate_hr.index, comp_rate_hr.values, "o-", color=C_GREEN,
                linewidth=2.5, markersize=6, label="Completion %")
        ax.plot(cancel_rate_hr.index, cancel_rate_hr.values, "s-", color=C_RED,
                linewidth=2, markersize=5, label="Cancellation %")
        ax.plot(nocar_rate_hr.index, nocar_rate_hr.values, "^-", color=C_ORANGE,
                linewidth=2, markersize=5, label="No Car %")
        ax.axhline(comp_rate_hr.mean(), color=C_DARK, linestyle="--", linewidth=1,
                   label=f"Avg Completion: {comp_rate_hr.mean():.1f}%")
        ax.set_xticks(range(24))
        ax.set_title("Hourly Rate by Status", fontweight="bold", color=C_DARK)
        ax.set_xlabel("Hour"); ax.set_ylabel("Rate (%)")
        ax.set_ylim(0, 100); ax.legend(fontsize=8)
        ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
        plt.tight_layout(); render_fig(fig)

    # Time Slot Gap Bar
    st.markdown("<div class='section-header'>📦 Unfulfilled Requests by Time Slot</div>",
                unsafe_allow_html=True)

    gap_slot = df[df["Unfulfilled"]==1].groupby("Time_slot").size().reindex(SLOT_ORDER)

    col3, col4 = st.columns([2, 1])
    with col3:
        fig, ax = plt.subplots(figsize=(11, 5), facecolor=C_BG)
        bar_colors = [C_RED if v > gap_slot.mean() else C_BLUE for v in gap_slot.values]
        bars = ax.bar(gap_slot.index, gap_slot.values, color=bar_colors, edgecolor="white")
        ax.axhline(gap_slot.mean(), linestyle="--", color=C_DARK, linewidth=1.5,
                   label=f"Mean: {gap_slot.mean():.0f}")
        ax.set_title("Unfulfilled Requests by Time Slot (Red = Above Mean)",
                     fontweight="bold", color=C_DARK)
        ax.set_ylabel("Unfulfilled Count"); ax.legend()
        for bar, val in zip(bars, gap_slot.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                    str(val), ha="center", fontweight="bold", fontsize=9)
        ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
        plt.tight_layout(); render_fig(fig)

    with col4:
        st.dataframe(
            gap_slot.reset_index().rename(columns={0:"Unfulfilled","Time_slot":"Time Slot"})
            .sort_values("Unfulfilled", ascending=False),
            use_container_width=True, hide_index=True
        )

    # Day-wise demand
    st.markdown("<div class='section-header'>📅 Day-wise Demand</div>",
                unsafe_allow_html=True)

    weekday_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    wd = df.groupby("Weekday").size().reindex(weekday_order).dropna()

    fig, ax = plt.subplots(figsize=(10, 4), facecolor=C_BG)
    bar_colors = [C_ORANGE if v == wd.max() else C_BLUE for v in wd.values]
    ax.bar(wd.index, wd.values, color=bar_colors, edgecolor="white")
    for i, (d, v) in enumerate(zip(wd.index, wd.values)):
        ax.text(i, v + 5, str(v), ha="center", fontsize=9, fontweight="bold")
    ax.set_title("Requests by Day of Week", fontweight="bold", color=C_DARK)
    ax.set_ylabel("Requests")
    ax.set_ylim(wd.min() - 50, wd.max() + 80)
    ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout(); render_fig(fig)


# ══════════════════════════════════════════════════════════════
# TAB 3 — LOCATION ANALYSIS
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown("<div class='section-header'>🏙️ City vs Airport — Hourly Comparison</div>",
                unsafe_allow_html=True)

    pickup_hr = df.groupby(["Hour","Pickup_point"]).size().unstack(fill_value=0)

    fig, ax = plt.subplots(figsize=(14, 5), facecolor=C_BG)
    x = np.arange(24); w = 0.4
    ax.bar(x - w/2, pickup_hr.get("Airport", pd.Series(0, index=x)),
           w, label="Airport", color=C_ORANGE, edgecolor="white")
    ax.bar(x + w/2, pickup_hr.get("City", pd.Series(0, index=x)),
           w, label="City",    color=C_BLUE,   edgecolor="white")
    ax.set_title("City vs Airport — Requests by Hour", fontweight="bold", color=C_DARK)
    ax.set_xlabel("Hour"); ax.set_ylabel("Requests")
    ax.set_xticks(range(24)); ax.legend(fontsize=10)
    ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout(); render_fig(fig)

    col1, col2 = st.columns(2)

    # Unfulfilled heatmap — Hour × Pickup
    with col1:
        st.markdown("**Unfulfilled Heatmap: Hour × Pickup Point**")
        pivot_heat = df[df["Unfulfilled"]==1].pivot_table(
            index="Hour", columns="Pickup_point",
            values="Unfulfilled", aggfunc="sum", fill_value=0)
        fig, ax = plt.subplots(figsize=(7, 10), facecolor=C_BG)
        sns.heatmap(pivot_heat, annot=True, fmt="d", cmap="YlOrRd",
                    ax=ax, linewidths=0.5, linecolor="white")
        ax.set_title("Unfulfilled: Hour × Pickup", fontweight="bold", color=C_DARK)
        plt.tight_layout(); render_fig(fig)

    with col2:
        st.markdown("**Completion Rate: Hour × Pickup Point**")
        comp_rate_map = df.groupby(["Hour","Pickup_point"]).apply(
            lambda x: (x["Status"] == "Trip Completed").mean() * 100).unstack()
        fig, ax = plt.subplots(figsize=(7, 10), facecolor=C_BG)
        sns.heatmap(comp_rate_map, annot=True, fmt=".0f", cmap="RdYlGn",
                    ax=ax, vmin=0, vmax=100, linewidths=0.5,
                    cbar_kws={"label":"Completion %"})
        ax.set_title("Completion Rate % by Hour × Pickup", fontweight="bold", color=C_DARK)
        plt.tight_layout(); render_fig(fig)

    # Multivariate: Status × Pickup × Time Slot
    st.markdown("<div class='section-header'>📊 Status × Pickup × Time Slot</div>",
                unsafe_allow_html=True)

    mv = df.groupby(["Time_slot","Pickup_point","Status"]).size().reset_index(name="Count")
    mv["Time_slot"] = pd.Categorical(mv["Time_slot"], categories=SLOT_ORDER, ordered=True)
    mv = mv.sort_values("Time_slot")

    fig = plt.figure(figsize=(16, 6), facecolor=C_BG)
    locations = df["Pickup_point"].unique()
    for i, loc in enumerate(locations):
        ax = fig.add_subplot(1, len(locations), i+1)
        sub = mv[mv["Pickup_point"] == loc]
        pivot = sub.pivot(index="Time_slot", columns="Status", values="Count").fillna(0)
        pivot = pivot.reindex(SLOT_ORDER)
        pivot.plot(kind="bar", ax=ax,
                   color=[C_RED, C_ORANGE, C_GREEN],
                   edgecolor="white", width=0.7)
        ax.set_title(f"{loc} Pickup", fontweight="bold", color=C_DARK)
        ax.set_xlabel(""); ax.set_ylabel("Count" if i==0 else "")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right", fontsize=8)
        ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
        ax.legend(fontsize=7)
    fig.suptitle("Status × Pickup Point × Time Slot", fontsize=13,
                 fontweight="bold", color=C_DARK)
    plt.tight_layout(); render_fig(fig)

    # Supply-Demand Gap Heatmap by Pickup × Time Slot
    st.markdown("<div class='section-header'>🔥 Supply-Demand Gap Heatmap</div>",
                unsafe_allow_html=True)

    gap_pivot = df[df["Unfulfilled"]==1].pivot_table(
        index="Time_slot", columns="Pickup_point",
        values="Unfulfilled", aggfunc="sum", fill_value=0)
    gap_pivot = gap_pivot.reindex(SLOT_ORDER)

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=C_BG)
    sns.heatmap(gap_pivot, annot=True, fmt="d", cmap="Reds",
                linewidths=0.5, ax=ax)
    ax.set_title("Supply-Demand Gap: Pickup × Time Slot",
                 fontweight="bold", color=C_DARK)
    plt.tight_layout(); render_fig(fig)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("<div class='insight-box'>🛫 <b>Airport × Morning</b> is the single most "
                    "critical failure intersection — highest unfulfilled count in entire dataset."
                    "</div>", unsafe_allow_html=True)
    with col4:
        st.markdown("<div class='warn-box'>⚠️ Airport column is darker overall — "
                    "Airport is structurally underserved regardless of time slot. "
                    "Requires dedicated driver tier with earnings guarantees.</div>",
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# TAB 4 — DEEP DIVE
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown("<div class='section-header'>📐 Trip Duration Analysis</div>",
                unsafe_allow_html=True)

    completed_df = df[df["Status"] == "Trip Completed"].dropna(subset=["Duration_min"])

    col1, col2 = st.columns(2)

    with col1:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor=C_BG)
        axes[0].hist(completed_df["Duration_min"], bins=30,
                     color=C_BLUE, edgecolor="white", alpha=0.85)
        axes[0].axvline(completed_df["Duration_min"].mean(), color=C_RED,
                        linestyle="--", linewidth=1.8,
                        label=f"Mean: {completed_df['Duration_min'].mean():.1f}m")
        axes[0].axvline(completed_df["Duration_min"].median(), color=C_ORANGE,
                        linestyle="--", linewidth=1.8,
                        label=f"Median: {completed_df['Duration_min'].median():.1f}m")
        axes[0].set_title("Duration Histogram", fontweight="bold", color=C_DARK)
        axes[0].set_xlabel("Minutes"); axes[0].legend(fontsize=8)
        axes[0].set_facecolor(C_BG); axes[0].spines[["top","right"]].set_visible(False)

        axes[1].boxplot(completed_df["Duration_min"], vert=False, patch_artist=True,
                        boxprops=dict(facecolor=C_BLUE, color=C_DARK),
                        medianprops=dict(color=C_RED, linewidth=2))
        axes[1].set_title("Duration Boxplot", fontweight="bold", color=C_DARK)
        axes[1].set_xlabel("Minutes")
        axes[1].set_facecolor(C_BG); axes[1].spines[["top","right"]].set_visible(False)
        fig.suptitle("Completed Trip Duration Distribution",
                     fontweight="bold", color=C_DARK)
        plt.tight_layout(); render_fig(fig)

    with col2:
        # Duration stats table
        dur_stats = completed_df["Duration_min"].describe().round(2)
        st.markdown("**Duration Statistics:**")
        st.dataframe(dur_stats.reset_index().rename(
            columns={"index": "Metric", "Duration_min": "Value"}),
            use_container_width=True, hide_index=True)

        st.markdown("<div class='insight-box'>Near-symmetric distribution (mean ≈ median) "
                    "means trip durations are <b>predictable</b>. Wide IQR (41–64 min) "
                    "reflects both short city hops and long airport runs in same pool.</div>",
                    unsafe_allow_html=True)

    # Violin by pickup point
    st.markdown("**Trip Duration by Pickup Point**")
    col3, col4 = st.columns(2)
    with col3:
        fig, ax = plt.subplots(figsize=(8, 5), facecolor=C_BG)
        sns.violinplot(data=completed_df, x="Pickup_point", y="Duration_min",
                       palette=[C_ORANGE, C_BLUE], inner="box", ax=ax)
        ax.set_title("Duration by Pickup Point (Violin)", fontweight="bold", color=C_DARK)
        ax.set_xlabel("Pickup Point"); ax.set_ylabel("Minutes")
        ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
        plt.tight_layout(); render_fig(fig)

    with col4:
        fig, ax = plt.subplots(figsize=(8, 5), facecolor=C_BG)
        for loc, color in zip(["Airport","City"], [C_ORANGE, C_BLUE]):
            subset = completed_df.loc[completed_df["Pickup_point"]==loc, "Duration_min"]
            if len(subset):
                sns.kdeplot(subset, ax=ax, fill=True, alpha=0.3,
                            label=loc, color=color, linewidth=2)
        ax.set_title("Duration KDE by Pickup Point", fontweight="bold", color=C_DARK)
        ax.set_xlabel("Minutes"); ax.legend()
        ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
        plt.tight_layout(); render_fig(fig)

    # KDE by Status
    st.markdown("<div class='section-header'>🌊 Demand Density by Status (KDE)</div>",
                unsafe_allow_html=True)

    fig, ax = plt.subplots(figsize=(12, 5), facecolor=C_BG)
    for status, color in zip(
        ["Trip Completed","Cancelled","No Cars Available"],
        [C_GREEN, C_RED, C_ORANGE]
    ):
        sub = df[df["Status"]==status]["Hour"]
        if len(sub) > 1:
            sns.kdeplot(sub, ax=ax, fill=True, alpha=0.3,
                        label=status, color=color, linewidth=2)
    ax.set_title("KDE: Request Hour Distribution by Status",
                 fontweight="bold", color=C_DARK)
    ax.set_xlabel("Hour"); ax.set_ylabel("Density"); ax.legend()
    ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout(); render_fig(fig)

    # Demand Heatmap
    st.markdown("<div class='section-header'>🗓️ Demand Heatmap — Hour × Day</div>",
                unsafe_allow_html=True)

    hm_data = df.groupby(["Weekday","Hour"]).size().unstack(fill_value=0)
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    hm_data = hm_data.reindex([d for d in day_order if d in hm_data.index])

    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("uber", ["#EBF3FB", C_DARK])

    fig, ax = plt.subplots(figsize=(16, 5), facecolor=C_BG)
    im = ax.imshow(hm_data.values, aspect="auto", cmap=cmap)
    ax.set_xticks(range(24)); ax.set_xticklabels(range(24), fontsize=8)
    ax.set_yticks(range(len(hm_data)))
    ax.set_yticklabels(hm_data.index)
    ax.set_title("Demand Heatmap: Hour vs Day of Week",
                 fontweight="bold", color=C_DARK)
    ax.set_xlabel("Hour of Day")
    max_val = hm_data.values.max()
    for i in range(hm_data.shape[0]):
        for j in range(hm_data.shape[1]):
            v = hm_data.values[i, j]
            ax.text(j, i, str(v), ha="center", va="center", fontsize=6.5,
                    color="white" if v > max_val * 0.55 else C_DARK)
    plt.colorbar(im, ax=ax, label="Requests", shrink=0.7)
    plt.tight_layout(); render_fig(fig)

    # Supply vs Demand — Final Chart
    st.markdown("<div class='section-header'>⚖️ Supply vs Demand Gap by Time Slot</div>",
                unsafe_allow_html=True)

    demand_ts = df.groupby("Time_slot").size().reindex(SLOT_ORDER)
    supply_ts = df[df["Status"]=="Trip Completed"].groupby("Time_slot").size().reindex(SLOT_ORDER).fillna(0)

    fig, ax = plt.subplots(figsize=(13, 6), facecolor=C_BG)
    x = np.arange(len(SLOT_ORDER)); w = 0.35
    ax.bar(x - w/2, demand_ts, w, label="Demand (Total)", color=C_BLUE,  edgecolor="white")
    ax.bar(x + w/2, supply_ts, w, label="Supply (Completed)", color=C_GREEN, edgecolor="white")

    for xi, (d, s) in enumerate(zip(demand_ts.values, supply_ts.values)):
        gap = int(d - s)
        mid = s + gap / 2
        ax.annotate(f"Gap\n{gap:,}",
                    xy=(xi + w/2, s), xytext=(xi, mid + 20),
                    arrowprops=dict(arrowstyle="->", color=C_RED, lw=1.5),
                    fontsize=8, color=C_RED, ha="center")

    ax.set_xticks(x); ax.set_xticklabels(SLOT_ORDER, rotation=20, ha="right")
    ax.set_title("Supply vs Demand Gap — By Time Slot",
                 fontweight="bold", color=C_DARK, fontsize=14)
    ax.set_ylabel("Number of Requests"); ax.legend(fontsize=10)
    ax.set_facecolor(C_BG); ax.spines[["top","right"]].set_visible(False)
    plt.tight_layout(); render_fig(fig)


# ══════════════════════════════════════════════════════════════
# TAB 5 — SQL INSIGHTS
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown("<div class='section-header'>🗃️ SQL Query Results</div>",
                unsafe_allow_html=True)

    queries = {
        "Q1: Overall Status Distribution": """
            SELECT  Status,
                    COUNT(*)  AS Total_Requests,
                    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM uber), 2) AS Pct
            FROM    uber
            GROUP BY Status
            ORDER BY Total_Requests DESC;
        """,
        "Q2: Supply-Demand Gap by Time Slot": """
            SELECT  Time_slot,
                    COUNT(*)  AS Total,
                    SUM(Unfulfilled) AS Unfulfilled,
                    ROUND(SUM(Unfulfilled)*100.0/COUNT(*), 2) AS Unfulfilled_Pct
            FROM    uber
            GROUP BY Time_slot
            ORDER BY Unfulfilled DESC;
        """,
        "Q3: Cancellation Rate by Pickup Point": """
            SELECT  Pickup_point,
                    COUNT(*) AS Total_Requests,
                    SUM(CASE WHEN Status='Cancelled' THEN 1 ELSE 0 END) AS Cancelled,
                    SUM(CASE WHEN Status='No Cars Available' THEN 1 ELSE 0 END) AS No_Cars,
                    ROUND(SUM(CASE WHEN Status='Cancelled' THEN 1.0 ELSE 0 END)/COUNT(*)*100,2) AS Cancel_Pct,
                    ROUND(SUM(CASE WHEN Status='No Cars Available' THEN 1.0 ELSE 0 END)/COUNT(*)*100,2) AS NoCar_Pct
            FROM    uber
            GROUP BY Pickup_point;
        """,
        "Q4: Top-10 Peak Gap Hours": """
            SELECT  Hour,
                    COUNT(*) AS Requests,
                    SUM(Unfulfilled) AS Unfulfilled,
                    ROUND(AVG(Unfulfilled)*100, 2) AS Gap_Pct
            FROM    uber
            GROUP BY Hour
            ORDER BY Unfulfilled DESC
            LIMIT 10;
        """,
        "Q5: Avg Trip Duration by Pickup Point": """
            SELECT  Pickup_point,
                    ROUND(AVG(Duration_min), 2) AS Avg_Min,
                    ROUND(MIN(Duration_min), 2) AS Min_Min,
                    ROUND(MAX(Duration_min), 2) AS Max_Min,
                    COUNT(*) AS Completed_Trips
            FROM    uber
            WHERE   Status = 'Trip Completed'
            GROUP BY Pickup_point;
        """,
        "Q6: Daily Request Trend": """
            SELECT  Day,
                    COUNT(*) AS Total,
                    SUM(CASE WHEN Status='Trip Completed'     THEN 1 ELSE 0 END) AS Completed,
                    SUM(CASE WHEN Status='Cancelled'          THEN 1 ELSE 0 END) AS Cancelled,
                    SUM(CASE WHEN Status='No Cars Available'  THEN 1 ELSE 0 END) AS No_Cars
            FROM    uber
            GROUP BY Day
            ORDER BY Day;
        """,
        "Q7: Worst Pickup × Time-Slot Combos": """
            SELECT  Pickup_point, Time_slot,
                    COUNT(*) AS Total,
                    SUM(Unfulfilled) AS Unfulfilled,
                    ROUND(SUM(Unfulfilled)*100.0/COUNT(*),1) AS Gap_Pct
            FROM    uber
            GROUP BY Pickup_point, Time_slot
            ORDER BY Unfulfilled DESC
            LIMIT 10;
        """,
    }

    selected_query = st.selectbox("Select a SQL Query", list(queries.keys()))

    try:
        result_df = pd.read_sql(queries[selected_query], conn)
        st.dataframe(result_df.style.background_gradient(
            subset=[c for c in result_df.columns if "Pct" in c or "Rate" in c],
            cmap="RdYlGn_r"), use_container_width=True)
    except Exception as e:
        st.error(f"Query error: {e}")

    # Custom SQL
    st.markdown("---")
    st.markdown("**✍️ Write Custom SQL Query**")
    custom_sql = st.text_area(
        "Enter SQL (table name: `uber`)",
        value="SELECT Pickup_point, Hour, COUNT(*) as cnt\nFROM uber\nGROUP BY Pickup_point, Hour\nORDER BY cnt DESC\nLIMIT 20;",
        height=120
    )
    if st.button("▶️ Run Query"):
        try:
            custom_result = pd.read_sql(custom_sql, conn)
            st.dataframe(custom_result, use_container_width=True)
        except Exception as e:
            st.error(f"SQL Error: {e}")


# ══════════════════════════════════════════════════════════════
# TAB 6 — RAW DATA
# ══════════════════════════════════════════════════════════════
with tab6:
    st.markdown("<div class='section-header'>📋 Raw Dataset Explorer</div>",
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Rows", f"{len(df):,}")
    col2.metric("Total Columns", df.shape[1])
    col3.metric("Memory Usage", f"{df.memory_usage(deep=True).sum()/1024:.1f} KB")

    st.markdown("**Dataset Preview:**")
    display_cols = ["Request_id","Pickup_point","Driver_id","Status",
                    "Hour","Weekday","Time_slot","Duration_min","Unfulfilled"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols].head(100), use_container_width=True)

    # Missing values
    st.markdown("**Missing Values:**")
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if len(missing):
        st.dataframe(
            missing.reset_index().rename(columns={"index":"Column",0:"Missing Count"}),
            use_container_width=True, hide_index=True
        )
    else:
        st.success("No missing values in filtered dataset!")

    # Download
    st.markdown("---")
    csv_export = df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Filtered Data as CSV",
        data=csv_export,
        file_name="uber_filtered_data.csv",
        mime="text/csv",
    )

    # Dataset info
    st.markdown("**Column Descriptions:**")
    desc_data = {
        "Column": ["Request_id","Pickup_point","Driver_id","Status",
                   "Hour","Weekday","Time_slot","Duration_min","Unfulfilled"],
        "Type": ["int","str","float","str","int","str","str","float","int"],
        "Description": [
            "Unique ride request identifier",
            "Origin: City or Airport",
            "Assigned driver ID (NaN for No Cars Available)",
            "Trip Completed / Cancelled / No Cars Available",
            "Hour of request (0–23)",
            "Day name (Monday–Friday)",
            "Time bucket (Morning / Evening etc.)",
            "Trip duration in minutes (completed trips only)",
            "1 = Failed (Cancelled or No Cars), 0 = Completed",
        ]
    }
    st.dataframe(pd.DataFrame(desc_data), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:#888; font-size:0.85rem; padding:8px 0'>
    🚗 Uber Supply-Demand Gap Analysis Dashboard &nbsp;|&nbsp;
    Built with Streamlit &nbsp;|&nbsp;
    Dataset: Jul 11–15, 2016 &nbsp;|&nbsp;
    6,745 Requests
</div>
""", unsafe_allow_html=True)
