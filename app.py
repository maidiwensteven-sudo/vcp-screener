import streamlit as st
import json
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="VCP Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sector Translation ───────────────────────────────────────────────────────
SECTOR_ZH = {
    "Technology":             "科技",
    "Energy":                 "能源",
    "Financial Services":     "金融服務",
    "Healthcare":             "醫療保健",
    "Consumer Cyclical":      "非必需消費",
    "Consumer Defensive":     "必需消費",
    "Industrials":            "工業",
    "Basic Materials":        "原材料",
    "Real Estate":            "房地產",
    "Communication Services": "通訊服務",
    "Utilities":              "公用事業",
    "Unknown":                "其他",
}

def zh_sector(s):
    return SECTOR_ZH.get(s, s)

# ─── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 28px 32px 20px;
    margin-bottom: 24px;
}
.hero-title {
    font-size: 28px; font-weight: 700;
    color: #f1f5f9; letter-spacing: -0.5px;
    margin: 0 0 4px;
}
.hero-sub { color: #64748b; font-size: 13px; margin: 0; }

.kpi-grid { display: flex; gap: 12px; margin-bottom: 24px; }
.kpi-card {
    flex: 1;
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 16px 20px;
}
.kpi-label { color: #64748b; font-size: 11px; font-weight: 600;
             letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 8px; }
.kpi-value { color: #f1f5f9; font-size: 26px; font-weight: 700; }
.kpi-value.green { color: #4ade80; }

.stock-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.stock-card:hover { border-color: #334155; }

.stock-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.stock-rank {
    background: #1e293b; color: #64748b;
    font-size: 11px; font-weight: 700;
    padding: 3px 8px; border-radius: 6px;
    min-width: 28px; text-align: center;
}
.stock-symbol { color: #f1f5f9; font-size: 18px; font-weight: 700; }
.stock-name   { color: #64748b; font-size: 13px; }
.stock-sector {
    margin-left: auto;
    background: #1e293b; color: #94a3b8;
    font-size: 11px; font-weight: 600;
    padding: 4px 10px; border-radius: 20px;
}

.score-badge {
    display: inline-block;
    padding: 3px 10px; border-radius: 20px;
    font-size: 12px; font-weight: 700;
}
.score-high { background: #052e16; color: #4ade80; }
.score-mid  { background: #1c1917; color: #fbbf24; }
.score-low  { background: #1c0a00; color: #fb923c; }

.data-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.data-block { }
.data-block-title {
    color: #475569; font-size: 10px; font-weight: 700;
    letter-spacing: 0.8px; text-transform: uppercase;
    margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 1px solid #1e293b;
}
.data-row { display: flex; justify-content: space-between;
            align-items: center; padding: 4px 0; }
.data-key   { color: #64748b; font-size: 12px; }
.data-val   { color: #e2e8f0; font-size: 12px; font-weight: 600; }
.data-val.green  { color: #4ade80; }
.data-val.red    { color: #f87171; }
.data-val.yellow { color: #fbbf24; }

.trade-box {
    background: #020617;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 12px 16px;
}
.trade-row { display: flex; justify-content: space-between; padding: 3px 0; }
.trade-key { color: #475569; font-size: 12px; }
.trade-val { color: #e2e8f0; font-size: 12px; font-weight: 600; }

.divider { border: none; border-top: 1px solid #1e293b; margin: 8px 0; }

.tag-vol-ok   { background: #052e16; color: #4ade80;
                padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.tag-vol-warn { background: #1c1917; color: #fbbf24;
                padding: 2px 8px; border-radius: 4px; font-size: 11px; }

[data-testid="stSidebar"] { background: #0a0f1e; }
[data-testid="stSidebar"] .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ─── Load Data ────────────────────────────────────────────────────────────────
RESULTS_FILE = Path("results/latest.json")

@st.cache_data(ttl=300)
def load_results():
    if not RESULTS_FILE.exists():
        return None
    with open(RESULTS_FILE) as f:
        return json.load(f)

data = load_results()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("### 🔍 篩選條件")

if data is None:
    st.warning("⚠️ 尚無掃描結果，請等待每日自動掃描。")
    st.stop()

candidates = data.get("candidates", [])
if not candidates:
    st.info("今日沒有符合條件的 VCP 候選股。")
    st.stop()

df = pd.DataFrame(candidates)
df["sector_zh"] = df["sector"].apply(zh_sector)

sectors_zh = sorted(df["sector_zh"].dropna().unique().tolist())
selected_zh = st.sidebar.multiselect("板塊", sectors_zh, default=sectors_zh)
min_score   = st.sidebar.slider("最低分數", 0, 100, 40)
max_dist    = st.sidebar.slider("距 Pivot 最大距離 (%)", 1, 15, 12)
vol_only    = st.sidebar.checkbox("只看量縮股票", value=False)

st.sidebar.divider()
st.sidebar.markdown("""
<div style='color:#475569;font-size:11px;line-height:1.8'>
<b style='color:#64748b'>篩選標準（影片 8 條件）</b><br>
• 市值 > $3億<br>
• 股價 > $15<br>
• 股價 > SMA50 > SMA200<br>
• 距52週高點 ≤ 15%<br>
• 法人持股 > 10%<br>
• 上季營收增長 > 5%<br>
• 成交量 > 20萬<br>
• VCP：2–6 次遞減收縮
</div>
""", unsafe_allow_html=True)

filtered = df[
    df["sector_zh"].isin(selected_zh) &
    (df["score"] >= min_score) &
    (df["dist_to_pivot"].abs() <= max_dist)
]
if vol_only:
    filtered = filtered[filtered["vol_dryup"] == True]
filtered = filtered.sort_values("score", ascending=False).reset_index(drop=True)

# ─── Hero ─────────────────────────────────────────────────────────────────────
scan_date = data.get("date", "—")
total     = data.get("total_scanned", "—")
vcp_count = data.get("vcp_count", len(candidates))

st.markdown(f"""
<div class="hero">
  <div class="hero-title">📈 VCP Screener</div>
  <div class="hero-sub">Volatility Contraction Pattern &nbsp;·&nbsp; @jlawstock 影片標準 &nbsp;·&nbsp; Mark Minervini 方法論 &nbsp;·&nbsp; 最後更新：{scan_date}</div>
</div>
""", unsafe_allow_html=True)

# ─── KPI Cards ────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, label, value, green in [
    (c1, "掃描股票數",  f"{total:,}" if isinstance(total, int) else total, False),
    (c2, "VCP 候選股",  str(vcp_count), True),
    (c3, "篩選後顯示",  str(len(filtered)), False),
    (c4, "掃描日期",    scan_date, False),
]:
    cls = "green" if green else ""
    col.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value {cls}">{value}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Sector Chart ─────────────────────────────────────────────────────────────
sector_counts = (
    df.groupby("sector_zh").size()
    .reset_index(name="count")
    .sort_values("count", ascending=True)
)

fig = px.bar(
    sector_counts, x="count", y="sector_zh", orientation="h",
    text="count", color="count",
    color_continuous_scale=[[0, "#1e293b"], [0.5, "#3b82f6"], [1.0, "#4ade80"]],
)
fig.update_traces(textposition="outside", textfont_size=13, marker_line_width=0)
fig.update_layout(
    title=dict(text="板塊 Setup 分布", font=dict(size=14, color="#94a3b8"), x=0),
    paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
    font=dict(color="#94a3b8", family="Inter"),
    showlegend=False, coloraxis_showscale=False,
    margin=dict(l=0, r=50, t=40, b=10),
    height=max(220, len(sector_counts) * 44),
    yaxis=dict(showgrid=False, tickfont=dict(size=13, color="#cbd5e1")),
    xaxis=dict(showgrid=True, gridcolor="#1e293b", tickfont=dict(size=11)),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("<hr style='border-color:#1e293b;margin:8px 0 24px'>", unsafe_allow_html=True)

# ─── Candidate Cards ──────────────────────────────────────────────────────────
st.markdown(f"### 🏆 VCP 候選股 &nbsp;<span style='color:#475569;font-size:16px;font-weight:400'>({len(filtered)} 支)</span>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

if filtered.empty:
    st.info("目前篩選條件下沒有符合的股票，請放寬條件。")
else:
    for rank, (_, r) in enumerate(filtered.iterrows(), 1):
        symbol     = r["symbol"]
        company    = r.get("company", symbol)
        score      = float(r.get("score", 0))
        price      = float(r.get("current_price", 0))
        pivot      = float(r.get("pivot", 0))
        dist       = float(r.get("dist_to_pivot", 0))
        depths     = r.get("depths", [])
        n_contra   = r.get("n_contractions", 0)
        sector_zh  = r.get("sector_zh", "—")
        stop       = float(r.get("stop_loss", 0))
        sma50      = float(r.get("sma50", 0))
        sma150     = float(r.get("sma150", 0))
        sma200     = float(r.get("sma200", 0))
        vs_52wh    = float(r.get("price_vs_52wh", 0))
        vs_52wl    = float(r.get("price_vs_52wl", 0))
        vol_ratio  = r.get("vol_ratio")
        vol_dryup  = r.get("vol_dryup", False)
        pivot_date = r.get("pivot_date", "—")

        entry  = round(pivot * 1.005, 2)
        target = round(pivot + (pivot - stop / 0.99) * 2, 2) if stop else 0
        risk   = (entry - stop) / entry * 100 if stop and entry else 0
        reward = (target - entry) / entry * 100 if target and entry else 0

        depth_str  = " → ".join(f"{d:.1f}%" for d in depths) if depths else "—"
        vol_ratio_s = f"{vol_ratio:.2f}x" if vol_ratio else "—"
        vol_tag = '<span class="tag-vol-ok">✅ 量縮</span>' if vol_dryup else '<span class="tag-vol-warn">⚠️ 量未縮</span>'

        if score >= 70:   score_cls = "score-high"
        elif score >= 55: score_cls = "score-mid"
        else:             score_cls = "score-low"

        dist_cls  = "green" if dist > -5 else "yellow"
        vs52_cls  = "green" if vs_52wh > -10 else "yellow"

        with st.expander(f"#{rank}  {symbol}  —  {company}  ·  分數 {score:.0f}  ·  距Pivot {dist:+.1f}%  ·  {sector_zh}", expanded=(rank <= 3)):
            st.markdown(f"""
<div class="data-grid">
  <div class="data-block">
    <div class="data-block-title">形態資訊</div>
    <div class="data-row"><span class="data-key">收縮次數</span><span class="data-val">{n_contra} 次</span></div>
    <div class="data-row"><span class="data-key">收縮深度</span><span class="data-val" style="font-size:11px">{depth_str}</span></div>
    <div class="data-row"><span class="data-key">Pivot 價</span><span class="data-val">${pivot:.2f}</span></div>
    <div class="data-row"><span class="data-key">Pivot 日期</span><span class="data-val">{pivot_date}</span></div>
    <div class="data-row"><span class="data-key">現價</span><span class="data-val">${price:.2f}</span></div>
    <div class="data-row"><span class="data-key">距 Pivot</span><span class="data-val {dist_cls}">{dist:+.1f}%</span></div>
    <div class="data-row"><span class="data-key">成交量狀況</span>{vol_tag}</div>
    <div class="data-row"><span class="data-key">量比均值</span><span class="data-val">{vol_ratio_s}</span></div>
  </div>
  <div class="data-block">
    <div class="data-block-title">均線 / 位置</div>
    <div class="data-row"><span class="data-key">SMA 50</span><span class="data-val">${sma50:.0f}</span></div>
    <div class="data-row"><span class="data-key">SMA 150</span><span class="data-val">${sma150:.0f}</span></div>
    <div class="data-row"><span class="data-key">SMA 200</span><span class="data-val">${sma200:.0f}</span></div>
    <div class="data-row"><span class="data-key">距52週高點</span><span class="data-val {vs52_cls}">{vs_52wh:+.1f}%</span></div>
    <div class="data-row"><span class="data-key">距52週低點</span><span class="data-val green">{vs_52wl:+.1f}%</span></div>
    <div class="data-row"><span class="data-key">VCP 分數</span><span class="score-badge {score_cls}">{score:.0f} / 100</span></div>
  </div>
  <div class="data-block">
    <div class="data-block-title">交易計劃</div>
    <div class="trade-box">
      <div class="trade-row"><span class="trade-key">進場價</span><span class="trade-val" style="color:#60a5fa">${entry}</span></div>
      <div class="trade-row"><span class="trade-key">止損價</span><span class="trade-val" style="color:#f87171">${stop}</span></div>
      <div class="trade-row"><span class="trade-key">目標價</span><span class="trade-val" style="color:#4ade80">${target:.2f}</span></div>
      <hr class="divider">
      <div class="trade-row"><span class="trade-key">最大風險</span><span class="trade-val" style="color:#f87171">-{risk:.1f}%</span></div>
      <div class="trade-row"><span class="trade-key">潛在報酬</span><span class="trade-val" style="color:#4ade80">+{reward:.1f}%</span></div>
      <div class="trade-row"><span class="trade-key">風報比</span><span class="trade-val">1 : 2</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Full Table ───────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
with st.expander("📋 完整資料表", expanded=False):
    display_cols = {
        "symbol": "代碼", "company": "公司", "sector_zh": "板塊",
        "score": "分數", "current_price": "現價", "pivot": "Pivot",
        "dist_to_pivot": "距Pivot%", "n_contractions": "收縮次數",
        "vol_ratio": "量比", "price_vs_52wh": "距52高%",
    }
    table = filtered[[c for c in display_cols if c in filtered.columns]].copy()
    table.columns = [display_cols[c] for c in table.columns]
    st.dataframe(table, use_container_width=True, height=400)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<div style='color:#1e293b;font-size:11px;text-align:center'>資料來源：Financial Modeling Prep API　·　策略：VCP（Mark Minervini）　·　每個交易日自動更新</div>", unsafe_allow_html=True)
