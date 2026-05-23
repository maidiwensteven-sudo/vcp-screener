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

SECTOR_ZH = {
    "Technology":             "科技",
    "Energy":                 "能源",
    "Financial Services":     "金融",
    "Healthcare":             "醫療",
    "Consumer Cyclical":      "非必需消費",
    "Consumer Defensive":     "必需消費",
    "Industrials":            "工業",
    "Basic Materials":        "原材料",
    "Real Estate":            "房地產",
    "Communication Services": "通訊",
    "Utilities":              "公用",
    "Unknown":                "其他",
}

def zh_sector(s):
    return SECTOR_ZH.get(s, s)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Hero ── */
.hero {
    background: linear-gradient(135deg, #080d1a 0%, #0f172a 60%, #130d2a 100%);
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 22px 28px;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.hero-title {
    font-size: 22px; font-weight: 700;
    color: #f1f5f9; letter-spacing: -0.5px;
    margin: 0 0 5px; display: flex; align-items: center; gap: 10px;
}
.hero-sub { color: #334155; font-size: 11.5px; margin: 0; }
.hero-tag {
    background: #0f172a; border: 1px solid #1e293b;
    color: #475569; font-size: 11px; font-weight: 600;
    padding: 5px 14px; border-radius: 20px; white-space: nowrap;
}
.live-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #4ade80; display: inline-block;
    box-shadow: 0 0 5px #4ade80; margin-right: 6px;
}

/* ── KPI ── */
.kpi-card {
    background: #0a0f1e;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 14px 18px;
}
.kpi-label {
    color: #334155; font-size: 9.5px; font-weight: 700;
    letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 6px;
}
.kpi-value { color: #f1f5f9; font-size: 26px; font-weight: 700; line-height: 1; }
.kpi-value.green  { color: #4ade80; }
.kpi-value.purple { color: #a78bfa; }
.kpi-value.blue   { color: #60a5fa; }

/* ── Overview Table ── */
.ov-wrap {
    background: #0a0f1e;
    border: 1px solid #1e293b;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 28px;
}
.ov-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ov-table th {
    background: #060b15;
    color: #334155; font-size: 9px; font-weight: 700;
    letter-spacing: 1.2px; text-transform: uppercase;
    padding: 9px 14px; border-bottom: 1px solid #1e293b;
    white-space: nowrap;
}
.ov-table td {
    padding: 8px 14px;
    border-bottom: 1px solid #0d1526;
    vertical-align: middle;
}
.ov-table tr:last-child td { border-bottom: none; }
.ov-table tr:hover td { background: #0f172a; }
.ov-sym {
    color: #60a5fa; font-weight: 700; font-size: 13.5px;
    font-family: 'JetBrains Mono', monospace; letter-spacing: 0.3px;
}
.ov-co  { color: #334155; font-size: 10.5px; margin-top: 1px; }
.ov-rank { color: #1e293b; font-weight: 700; font-size: 12px; }

.sb-wrap { display: flex; flex-direction: column; gap: 4px; }
.sb-num  { font-weight: 700; font-size: 13px; }
.sb-bar-bg { background: #1e293b; border-radius: 2px; height: 3px; width: 64px; }
.sb-bar    { height: 3px; border-radius: 2px; }

.d-close  { color: #4ade80; font-family: monospace; }
.d-near   { color: #facc15; font-family: monospace; }
.d-far    { color: #f87171; font-family: monospace; }

.tag-sector {
    background: #0f172a; border: 1px solid #1e293b;
    color: #64748b; font-size: 9.5px; font-weight: 600;
    padding: 2px 8px; border-radius: 8px; white-space: nowrap;
}
.tag-new {
    background: #2e1065; color: #c4b5fd;
    font-size: 8.5px; font-weight: 800;
    padding: 1px 6px; border-radius: 6px; letter-spacing: 0.8px;
    vertical-align: middle; margin-left: 5px;
}
.vol-ok   { color: #4ade80; font-size: 12px; }
.vol-warn { color: #fbbf24; font-size: 12px; }

/* ── Detail Cards ── */
.sec-title {
    font-size: 18px; font-weight: 700; color: #e2e8f0;
    margin: 0 0 18px; padding-bottom: 10px;
    border-bottom: 1px solid #1e293b;
}
.detail-grid { display: grid; grid-template-columns: 1.3fr 1fr; gap: 22px; }
.block-label {
    color: #1e293b; font-size: 9px; font-weight: 700;
    letter-spacing: 1.2px; text-transform: uppercase;
    margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 1px solid #1e293b;
}
.dr { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
.dk { color: #334155; font-size: 12px; }
.dv { color: #cbd5e1; font-size: 12px; font-weight: 600; }
.dv.g { color: #4ade80; }
.dv.y { color: #fbbf24; }
.dv.r { color: #f87171; }

.trade-panel {
    background: #060b15;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 12px;
}
.trade-label {
    color: #1e293b; font-size: 9px; font-weight: 700;
    letter-spacing: 1.2px; text-transform: uppercase;
    margin-bottom: 12px; padding-bottom: 6px;
    border-bottom: 1px solid #1e293b;
}
.tr { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; }
.tk { color: #334155; font-size: 12px; }
.tv { font-size: 15px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
.tdiv { border: none; border-top: 1px solid #1e293b; margin: 6px 0; }

.score-panel {
    background: #060b15;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 14px 18px;
    text-align: center;
}
.score-big { font-size: 40px; font-weight: 700; line-height: 1; font-family: 'JetBrains Mono', monospace; }
.score-denom { color: #1e293b; font-size: 18px; font-weight: 400; }
.score-bar-bg { background: #1e293b; border-radius: 3px; height: 5px; margin-top: 10px; }
.score-bar    { height: 5px; border-radius: 3px; }

.tag-vol-ok   { background: #052e16; color: #4ade80; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.tag-vol-warn { background: #1c1917; color: #fbbf24; padding: 2px 8px; border-radius: 4px; font-size: 11px; }

[data-testid="stSidebar"] { background: #060b15; border-right: 1px solid #0f172a; }
[data-testid="stSidebar"] .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# ─── Load Data ────────────────────────────────────────────────────────────────
RESULTS_FILE = Path("results/latest.json")
PREV_FILE    = Path("results/previous.json")

@st.cache_data(ttl=300)
def load_results():
    if not RESULTS_FILE.exists():
        return None
    with open(RESULTS_FILE) as f:
        return json.load(f)

@st.cache_data(ttl=300)
def load_prev_symbols():
    if not PREV_FILE.exists():
        return set()
    try:
        with open(PREV_FILE) as f:
            d = json.load(f)
        return {c["symbol"] for c in d.get("candidates", [])}
    except Exception:
        return set()

data         = load_results()
prev_symbols = load_prev_symbols()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🔍 篩選條件")

if data is None:
    st.warning("⚠️ 尚無掃描結果，請等待每日自動掃描。")
    st.stop()

candidates = data.get("candidates", [])
if not candidates:
    st.info("今日沒有符合條件的 VCP 候選股。")
    st.stop()

df = pd.DataFrame(candidates)
df["sector_zh"] = df["sector"].apply(zh_sector)
df["is_new"]    = ~df["symbol"].isin(prev_symbols)

sectors_zh  = sorted(df["sector_zh"].dropna().unique().tolist())
selected_zh = st.sidebar.multiselect("板塊", sectors_zh, default=sectors_zh)
min_score   = st.sidebar.slider("最低分數", 0, 100, 40)
max_dist    = st.sidebar.slider("距 Pivot 最大距離 (%)", 1, 15, 12)
vol_only    = st.sidebar.checkbox("只看量縮", value=False)
new_only    = st.sidebar.checkbox("只看今日新增 🆕", value=False)

st.sidebar.divider()
st.sidebar.markdown("""
<div style='color:#1e293b;font-size:10.5px;line-height:2.2'>
<span style='color:#334155;font-weight:700;font-size:9px;letter-spacing:1px'>篩選標準</span><br>
市值 &gt; $3億 &nbsp;·&nbsp; 股價 &gt; $15<br>
股價 &gt; SMA50 &gt; SMA200<br>
距52週高點 ≤ 15%<br>
法人持股 &gt; 10%<br>
上季營收增長 &gt; 5%<br>
成交量 &gt; 20萬<br>
VCP：2–6 次遞減收縮
</div>
""", unsafe_allow_html=True)

filtered = df[
    df["sector_zh"].isin(selected_zh) &
    (df["score"] >= min_score) &
    (df["dist_to_pivot"].abs() <= max_dist)
]
if vol_only:
    filtered = filtered[filtered["vol_dryup"] == True]
if new_only:
    filtered = filtered[filtered["is_new"] == True]
filtered = filtered.sort_values("score", ascending=False).reset_index(drop=True)

# ─── Hero ─────────────────────────────────────────────────────────────────────
scan_date = data.get("date", "—")
total     = data.get("total_scanned", "—")
vcp_count = data.get("vcp_count", len(candidates))
new_count = int(df["is_new"].sum())

st.markdown(f"""
<div class="hero">
  <div>
    <div class="hero-title">📈 VCP Screener</div>
    <div class="hero-sub">
      Volatility Contraction Pattern &nbsp;·&nbsp; Mark Minervini &nbsp;·&nbsp; @jlawstock
    </div>
  </div>
  <div class="hero-tag"><span class="live-dot"></span>更新：{scan_date}</div>
</div>
""", unsafe_allow_html=True)

# ─── KPI ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, label, val, cls in [
    (c1, "掃描股票數",  f"{total:,}" if isinstance(total, int) else str(total), ""),
    (c2, "VCP 候選股",  str(vcp_count), "green"),
    (c3, "今日新增",    str(new_count), "purple"),
    (c4, "篩選後顯示",  str(len(filtered)), "blue"),
]:
    col.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value {cls}">{val}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Sector Chart ─────────────────────────────────────────────────────────────
with st.expander("📊 板塊分布", expanded=False):
    sc = df.groupby("sector_zh").size().reset_index(name="count").sort_values("count", ascending=True)
    fig = px.bar(sc, x="count", y="sector_zh", orientation="h", text="count", color="count",
                 color_continuous_scale=[[0,"#1e293b"],[0.5,"#3b82f6"],[1.0,"#4ade80"]])
    fig.update_traces(textposition="outside", textfont_size=12, marker_line_width=0)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#64748b", family="Inter"),
        showlegend=False, coloraxis_showscale=False,
        margin=dict(l=0, r=50, t=10, b=10),
        height=max(180, len(sc) * 36),
        yaxis=dict(showgrid=False, tickfont=dict(size=12, color="#94a3b8")),
        xaxis=dict(showgrid=True, gridcolor="#0f172a", tickfont=dict(size=11)),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<hr style='border-color:#0f172a;margin:2px 0 20px'>", unsafe_allow_html=True)

# ─── Overview Table ───────────────────────────────────────────────────────────
title_suffix = f"<span style='color:#1e293b;font-size:15px;font-weight:400'>（{len(filtered)} 支）</span>"
st.markdown(f"<div style='font-size:17px;font-weight:700;color:#cbd5e1;margin-bottom:14px'>📋 候選股總覽 {title_suffix}</div>", unsafe_allow_html=True)

if filtered.empty:
    st.info("目前篩選條件下沒有符合的股票，請放寬條件。")
    st.stop()

rows_html = ""
for rank, (_, r) in enumerate(filtered.iterrows(), 1):
    symbol    = r["symbol"]
    company   = str(r.get("company", symbol))[:24]
    score     = float(r.get("score", 0))
    price     = float(r.get("current_price", 0))
    pivot     = float(r.get("pivot", 0))
    dist      = float(r.get("dist_to_pivot", 0))
    n_contra  = r.get("n_contractions", 0)
    sector_zh = r.get("sector_zh", "—")
    vol_dryup = r.get("vol_dryup", False)
    is_new    = r.get("is_new", False)

    bar_color = "#4ade80" if score >= 70 else "#fbbf24" if score >= 55 else "#f87171"
    bar_w     = int(score * 0.64)
    dist_cls  = "d-close" if dist > -3 else "d-near" if dist > -7 else "d-far"
    vol_html  = '<span class="vol-ok">✅ 量縮</span>' if vol_dryup else '<span class="vol-warn">⚠️ 未縮</span>'
    new_html  = '<span class="tag-new">NEW</span>' if is_new else ""

    rows_html += f"""<tr>
      <td><span class="ov-rank">#{rank}</span></td>
      <td>
        <span class="ov-sym">{symbol}</span>{new_html}<br>
        <span class="ov-co">{company}</span>
      </td>
      <td>
        <div class="sb-wrap">
          <span class="sb-num" style="color:{bar_color}">{score:.0f}</span>
          <div class="sb-bar-bg"><div class="sb-bar" style="width:{bar_w}px;background:{bar_color}"></div></div>
        </div>
      </td>
      <td style="font-family:monospace;color:#94a3b8">${price:.2f}</td>
      <td style="font-family:monospace;color:#64748b">${pivot:.2f}</td>
      <td class="{dist_cls}">{dist:+.1f}%</td>
      <td style="color:#475569;text-align:center">{n_contra}×</td>
      <td>{vol_html}</td>
      <td><span class="tag-sector">{sector_zh}</span></td>
    </tr>"""

st.markdown(f"""
<div class="ov-wrap">
<table class="ov-table">
  <thead><tr>
    <th>#</th><th>代碼 / 公司</th><th>VCP 分數</th>
    <th>現價</th><th>Pivot</th><th>距 Pivot</th>
    <th style="text-align:center">收縮</th><th>成交量</th><th>板塊</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</div>
""", unsafe_allow_html=True)

# ─── Detail Cards ─────────────────────────────────────────────────────────────
st.markdown("<div style='font-size:17px;font-weight:700;color:#cbd5e1;margin-bottom:18px'>🔍 個股詳情</div>", unsafe_allow_html=True)

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
    is_new     = r.get("is_new", False)

    entry  = round(pivot * 1.005, 2)
    target = round(pivot + (pivot - stop / 0.99) * 2, 2) if stop else 0
    risk   = (entry - stop) / entry * 100 if stop and entry else 0
    reward = (target - entry) / entry * 100 if target and entry else 0

    depth_str   = " → ".join(f"{d:.1f}%" for d in depths) if depths else "—"
    vol_ratio_s = f"{vol_ratio:.2f}×" if vol_ratio else "—"
    vol_tag     = '<span class="tag-vol-ok">✅ 量縮</span>' if vol_dryup else '<span class="tag-vol-warn">⚠️ 量未縮</span>'
    bar_color   = "#4ade80" if score >= 70 else "#fbbf24" if score >= 55 else "#f87171"
    dist_cls    = "g" if dist > -5 else "y"
    vs52_cls    = "g" if vs_52wh > -10 else "y"
    new_label   = "🆕 " if is_new else ""
    vol_icon    = "✅" if vol_dryup else "⚠️"

    header = f"{new_label}#{rank}  {symbol}  ·  {company[:28]}  ·  {score:.0f}分  ·  {dist:+.1f}%  ·  {n_contra}× {vol_icon}  ·  {sector_zh}"

    with st.expander(header, expanded=(rank <= 3)):
        st.markdown(f"""
<div class="detail-grid">
  <div>
    <div class="block-label">形態分析</div>
    <div class="dr"><span class="dk">收縮次數</span><span class="dv">{n_contra} 次</span></div>
    <div class="dr"><span class="dk">收縮深度</span><span class="dv" style="font-size:11px">{depth_str}</span></div>
    <div class="dr"><span class="dk">Pivot</span><span class="dv">${pivot:.2f} <span style="color:#1e293b;font-size:10px">({pivot_date})</span></span></div>
    <div class="dr"><span class="dk">現價</span><span class="dv">${price:.2f}</span></div>
    <div class="dr"><span class="dk">距 Pivot</span><span class="dv {dist_cls}">{dist:+.1f}%</span></div>
    <div class="dr"><span class="dk">成交量</span>{vol_tag}</div>
    <div class="dr"><span class="dk">量 / 均量</span><span class="dv">{vol_ratio_s}</span></div>
    <br>
    <div class="block-label">技術位置</div>
    <div class="dr"><span class="dk">SMA 50</span><span class="dv">${sma50:.0f}</span></div>
    <div class="dr"><span class="dk">SMA 150</span><span class="dv">${sma150:.0f}</span></div>
    <div class="dr"><span class="dk">SMA 200</span><span class="dv">${sma200:.0f}</span></div>
    <div class="dr"><span class="dk">距 52W 高點</span><span class="dv {vs52_cls}">{vs_52wh:+.1f}%</span></div>
    <div class="dr"><span class="dk">距 52W 低點</span><span class="dv g">{vs_52wl:+.1f}%</span></div>
  </div>
  <div>
    <div class="trade-panel">
      <div class="trade-label">交易計劃</div>
      <div class="tr"><span class="tk">進場價</span><span class="tv" style="color:#60a5fa">${entry:.2f}</span></div>
      <div class="tr"><span class="tk">止損價</span><span class="tv" style="color:#f87171">${stop:.2f}</span></div>
      <div class="tr"><span class="tk">目標價</span><span class="tv" style="color:#4ade80">${target:.2f}</span></div>
      <hr class="tdiv">
      <div class="tr"><span class="tk">最大風險</span><span class="tv" style="color:#f87171;font-size:13px">−{risk:.1f}%</span></div>
      <div class="tr"><span class="tk">潛在報酬</span><span class="tv" style="color:#4ade80;font-size:13px">+{reward:.1f}%</span></div>
      <div style="text-align:center;margin-top:10px">
        <span style="background:#0f172a;color:#3b82f6;font-size:12px;font-weight:700;padding:5px 16px;border-radius:6px;border:1px solid #1e293b">
          風報比 1 : 2
        </span>
      </div>
    </div>
    <div class="score-panel">
      <div class="block-label">VCP 評分</div>
      <div class="score-big" style="color:{bar_color}">{score:.0f}<span class="score-denom"> / 100</span></div>
      <div class="score-bar-bg">
        <div class="score-bar" style="width:{min(score,100):.0f}%;background:{bar_color}"></div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align:center;color:#0f172a;font-size:10.5px;padding-bottom:20px'>
  資料來源：Financial Modeling Prep API &nbsp;·&nbsp;
  策略：VCP（Mark Minervini）&nbsp;·&nbsp;
  每個交易日美股收盤後自動更新
</div>
""", unsafe_allow_html=True)
