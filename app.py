import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import datetime

st.set_page_config(
    page_title="VCP Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 8px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-label { color: #a6adc8; font-size: 13px; margin-bottom: 4px; }
    .metric-value { color: #cdd6f4; font-size: 28px; font-weight: 700; }
    .score-high   { color: #a6e3a1; font-weight: 700; }
    .score-mid    { color: #f9e2af; font-weight: 700; }
    .score-low    { color: #fab387; font-weight: 700; }
    .vol-ok       { color: #a6e3a1; }
    .vol-warn     { color: #f9e2af; }
    .stExpander > div > div { background: #1e1e2e !important; }
</style>
""", unsafe_allow_html=True)

RESULTS_FILE = Path("results/latest.json")

@st.cache_data(ttl=300)
def load_results():
    if not RESULTS_FILE.exists():
        return None
    with open(RESULTS_FILE) as f:
        return json.load(f)

def score_color(score):
    if score >= 70:   return "score-high"
    elif score >= 55: return "score-mid"
    return "score-low"

def vol_label(vol_ratio):
    if vol_ratio is None: return "N/A", ""
    label = f"{vol_ratio:.2f}x"
    cls = "vol-ok" if vol_ratio < 0.90 else "vol-warn"
    icon = "✅" if vol_ratio < 0.90 else "⚠️"
    return f"{icon} {label}", cls

# ─── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.title("🔍 篩選條件")

data = load_results()

if data is None:
    st.warning("⚠️ 尚無掃描結果，請等待每日自動掃描（每個交易日收盤後執行）。")
    st.stop()

candidates = data.get("candidates", [])

if not candidates:
    st.info("今日沒有符合條件的 VCP 候選股。")
    st.stop()

df = pd.DataFrame(candidates)

# Sidebar filters
sectors = sorted(df["sector"].dropna().unique().tolist())
selected_sectors = st.sidebar.multiselect("板塊", sectors, default=sectors)

min_score = st.sidebar.slider("最低分數", 0, 100, 40)
max_dist  = st.sidebar.slider("距 Pivot 最大距離 (%)", 1, 15, 12)
vol_only  = st.sidebar.checkbox("只看量縮股票", value=False)

filtered = df[
    df["sector"].isin(selected_sectors) &
    (df["score"] >= min_score) &
    (df["dist_to_pivot"].abs() <= max_dist)
]
if vol_only:
    filtered = filtered[filtered["vol_dryup"] == True]

filtered = filtered.sort_values("score", ascending=False).reset_index(drop=True)

# ─── Header ─────────────────────────────────────────────────────────────────
st.title("📈 VCP Screener")
st.caption("Volatility Contraction Pattern — @jlawstock 影片標準 ✦ Mark Minervini 方法論")

scan_date = data.get("date", "—")
total     = data.get("total_scanned", "—")
vcp_count = data.get("vcp_count", len(candidates))

c1, c2, c3, c4 = st.columns(4)
for col, label, value in [
    (c1, "掃描日期",   scan_date),
    (c2, "掃描股票數", f"{total:,}" if isinstance(total, int) else total),
    (c3, "VCP 候選股", str(vcp_count)),
    (c4, "篩選後顯示", str(len(filtered))),
]:
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Sector Chart ────────────────────────────────────────────────────────────
sector_counts = df.groupby("sector").size().reset_index(name="count").sort_values("count", ascending=True)

fig = px.bar(
    sector_counts, x="count", y="sector", orientation="h",
    text="count", color="count",
    color_continuous_scale=[[0, "#313244"], [0.5, "#89b4fa"], [1.0, "#a6e3a1"]],
    labels={"count": "Setup 數量", "sector": "板塊"},
)
fig.update_traces(textposition="outside", textfont_size=13)
fig.update_layout(
    title="板塊 Setup 分布",
    paper_bgcolor="#181825", plot_bgcolor="#181825",
    font_color="#cdd6f4",
    showlegend=False, coloraxis_showscale=False,
    margin=dict(l=0, r=40, t=40, b=0),
    height=max(250, len(sector_counts) * 42),
    yaxis=dict(showgrid=False),
    xaxis=dict(showgrid=True, gridcolor="#313244"),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ─── Candidate Cards ─────────────────────────────────────────────────────────
st.subheader(f"🏆 VCP 候選股（{len(filtered)} 支）")

if filtered.empty:
    st.info("目前篩選條件下沒有符合的股票，請放寬條件。")
else:
    for rank, (_, r) in enumerate(filtered.iterrows(), 1):
        symbol    = r["symbol"]
        company   = r.get("company", symbol)
        score     = r.get("score", 0)
        price     = r.get("current_price", 0)
        pivot     = r.get("pivot", 0)
        dist      = r.get("dist_to_pivot", 0)
        depths    = r.get("depths", [])
        n_contra  = r.get("n_contractions", 0)
        sector    = r.get("sector", "—")
        stop      = r.get("stop_loss", 0)
        sma50     = r.get("sma50", 0)
        sma150    = r.get("sma150", 0)
        sma200    = r.get("sma200", 0)
        vs_52wh   = r.get("price_vs_52wh", 0)
        vs_52wl   = r.get("price_vs_52wl", 0)
        vol_ratio = r.get("vol_ratio")
        vol_dryup = r.get("vol_dryup", False)
        pivot_date = r.get("pivot_date", "—")

        entry  = round(pivot * 1.005, 2)
        target = round(pivot + (pivot - stop / 0.99) * 2, 2) if stop else 0
        risk   = (entry - stop) / entry * 100 if stop and entry else 0
        reward = (target - entry) / entry * 100 if target and entry else 0

        depth_str = " → ".join(f"{d:.1f}%" for d in depths) if depths else "—"
        vol_text, _ = vol_label(vol_ratio)
        sc = score_color(score)

        header_text = f"#{rank}  **{symbol}** — {company}   |   分數 {score:.0f}/100   |   距 Pivot {dist:+.1f}%   |   {sector}"

        with st.expander(header_text, expanded=(rank <= 3)):
            left, mid, right = st.columns([1.2, 1, 1])

            with left:
                st.markdown("**📍 形態資訊**")
                st.markdown(f"- 收縮次數：**{n_contra} 次**")
                st.markdown(f"- 收縮深度：`{depth_str}`")
                st.markdown(f"- Pivot：**${pivot:.2f}**（{pivot_date}）")
                st.markdown(f"- 現價：**${price:.2f}**（距 pivot {dist:+.1f}%）")
                st.markdown(f"- 成交量：{vol_text}")

            with mid:
                st.markdown("**📊 均線 / 位置**")
                st.markdown(f"- SMA50：${sma50:.0f}")
                st.markdown(f"- SMA150：${sma150:.0f}")
                st.markdown(f"- SMA200：${sma200:.0f}")
                st.markdown(f"- 距52週高點：{vs_52wh:+.1f}%")
                st.markdown(f"- 距52週低點：{vs_52wl:+.1f}%")

            with right:
                st.markdown("**🎯 交易計劃**")
                st.markdown(f"- 進場：**${entry}**（突破 pivot +0.5%）")
                st.markdown(f"- 止損：**${stop}**（整固低點 -1%）")
                st.markdown(f"- 目標：**${target:.2f}**（2:1 R/R）")
                st.markdown(f"- 風險：**-{risk:.1f}%**")
                st.markdown(f"- 報酬：**+{reward:.1f}%**")

        st.markdown("")

# ─── Full Table ──────────────────────────────────────────────────────────────
st.divider()
with st.expander("📋 完整資料表（可排序/下載）", expanded=False):
    display_cols = {
        "symbol": "代碼", "company": "公司", "sector": "板塊",
        "score": "分數", "current_price": "現價", "pivot": "Pivot",
        "dist_to_pivot": "距Pivot%", "n_contractions": "收縮次數",
        "vol_ratio": "量比", "price_vs_52wh": "距52高%",
    }
    table = filtered[[c for c in display_cols if c in filtered.columns]].copy()
    table.columns = [display_cols[c] for c in table.columns]
    st.dataframe(table, use_container_width=True, height=400)

st.caption(f"資料來源：Financial Modeling Prep API ｜ 策略：VCP（Mark Minervini）｜ 每個交易日自動更新")
