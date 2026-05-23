"""
VCP Screener — Volatility Contraction Pattern
==============================================
Strategy: Mark Minervini + @jlawstock (超績投資客) 方法論
Built with FMP API

篩選邏輯（對齊影片 8 個條件）:
  1. 市值 > $3億                  (排除微型股)
  2. 股價 > $15                   (Minervini $12, O'Neil $20，取中間)
  3. 價格 > SMA50                 (Stage 2 趨勢)
  4. SMA50 > SMA200               (均線排列向上)
  5. 距52周高點 ≤ 15%             (越接近越好，影片標準10%)
  6. 上季營收增長 > 5%            (基本面質素)
  7. 法人持股 > 10%               (機構認可，透過 screener 前置過濾)
  8. 成交量 > 20萬                (流動性保障，比影片5萬更嚴格)

  + VCP 形態：2-6 次遞減收縮，成交量萎縮，現價在 pivot ±12%

Usage:
  export FMP_API_KEY=your_key
  python3 vcp_screener.py --broad              # 掃全部大中型美股
  python3 vcp_screener.py --index              # 掃 S&P500 + Nasdaq100
  python3 vcp_screener.py --limit 200          # 掃前200大型股
  python3 vcp_screener.py --watchlist AAPL,MSFT,NVDA
"""

import os
import sys
import time
import json
import math
import argparse
import datetime
import requests
from pathlib import Path
from dataclasses import dataclass, field

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

FMP_KEY    = os.environ.get("FMP_API_KEY", "")
BASE       = "https://financialmodelingprep.com/api"
BASE_STABLE = "https://financialmodelingprep.com/stable"

# ─── Config ──────────────────────────────────────────────────────────────────

CFG = {
    "min_market_cap":                300_000_000,  # $3億（影片條件1）
    "min_avg_volume":                200_000,      # 20萬股（比影片5萬更嚴格）
    "min_price":                     15.0,         # $15（影片條件2，Minervini $12 / O'Neil $20）
    "history_days":                  300,          # 拉 ~14 個月確保算 SMA200
    "swing_window":                  5,
    "min_contractions":              2,
    "max_contractions":              6,
    "depth_tolerance":               1.15,
    "first_contraction_min_depth":   8.0,
    "buy_zone_max":                  0.12,         # pivot 下方最多 12%
    "buy_zone_min":                 -0.02,         # pivot 上方最多 2%（已突破則排除）
    "vol_dryup_ratio":               0.90,
    "max_dist_from_52wh":           -15.0,         # 距52周高點 ≤ 15%（影片條件5，原始為10%）
    "min_revenue_growth":            0.05,         # 上季營收增長 > 5%（影片條件6）
    "apply_fundamental_filter":      True,         # 是否對 VCP 候選股做基本面二次過濾
}


# ─── API ─────────────────────────────────────────────────────────────────────

def api_stable(endpoint: str, params: dict = {}) -> list | dict:
    p = dict(params)
    p["apikey"] = FMP_KEY
    r = requests.get(f"{BASE_STABLE}{endpoint}", params=p, timeout=20)
    r.raise_for_status()
    return r.json()


def get_universe(limit: int = 80) -> list[dict]:
    return api_stable("/company-screener", {
        "exchange":          "NYSE,NASDAQ",
        "marketCapMoreThan": CFG["min_market_cap"],
        "volumeMoreThan":    CFG["min_avg_volume"],
        "priceMoreThan":     CFG["min_price"],
        "isActivelyTrading": "true",
        "isEtf":             "false",
        "limit":             limit,
    })


def get_index_universe() -> list[dict]:
    """取得 S&P 500 + 納斯達克 100 成分股（合併去重）"""
    sp500   = api_stable("/sp500-constituent")
    nasdaq  = api_stable("/nasdaq-constituent")
    seen, result = set(), []
    for stock in sp500 + nasdaq:
        sym = stock.get("symbol", "")
        if sym and sym not in seen:
            seen.add(sym)
            result.append({
                "symbol":      sym,
                "companyName": stock.get("name", sym),
                "sector":      stock.get("sector", ""),
            })
    return result


def get_broad_universe() -> list[dict]:
    """取得美股大中型股（市值 > $3億，已含法人持股 > 10% 前置過濾）"""
    raw = api_stable("/company-screener", {
        "marketCapMoreThan":          CFG["min_market_cap"],
        "volumeMoreThan":             CFG["min_avg_volume"],
        "priceMoreThan":              CFG["min_price"],
        "institutionalOwnershipMoreThan": 10,   # 法人持股 > 10%（影片條件7）
        "isActivelyTrading":          "true",
        "isEtf":                      "false",
        "limit":                      10000,
    })
    seen, result = set(), []
    for s in raw:
        sym = s.get("symbol", "")
        ex  = s.get("exchangeShortName", "")
        if sym and ex in ("NYSE", "NASDAQ", "AMEX") and sym not in seen:
            seen.add(sym)
            result.append({
                "symbol":      sym,
                "companyName": s.get("companyName", sym),
                "sector":      s.get("sector", ""),
            })
    return result


def get_revenue_growth(symbol: str) -> float | None:
    """取得最近一季的營收增長率，回傳小數（0.05 = 5%），失敗回傳 None"""
    try:
        data = api_stable("/income-statement-growth", {
            "symbol": symbol,
            "period": "quarter",
            "limit":  2,
        })
        if data and isinstance(data, list):
            return data[0].get("growthRevenue", None)
    except Exception:
        pass
    return None


def get_ohlcv(symbol: str, days: int = 180) -> list[dict]:
    to_d   = datetime.date.today().isoformat()
    from_d = (datetime.date.today() - datetime.timedelta(days=days + 30)).isoformat()
    data = api_stable("/historical-price-eod/full", {
        "symbol": symbol,
        "from":   from_d,
        "to":     to_d,
    })
    hist = data if isinstance(data, list) else []
    # API returns newest-first, reverse to oldest-first and take last N days
    hist_sorted = list(reversed(hist))
    return hist_sorted[-days:]


# ─── Technical Helpers ────────────────────────────────────────────────────────

def sma(series: list[float], n: int) -> float | None:
    if len(series) < n:
        return None
    return sum(series[-n:]) / n


def find_swing_highs(highs: list[float], lows: list[float], window: int = 5) -> list[tuple]:
    """Returns list of (index, value) for swing highs."""
    result = []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i - window: i + window + 1]):
            result.append((i, highs[i]))
    return result


def find_swing_lows(highs: list[float], lows: list[float], window: int = 5) -> list[tuple]:
    """Returns list of (index, value) for swing lows."""
    result = []
    for i in range(window, len(lows) - window):
        if lows[i] == min(lows[i - window: i + window + 1]):
            result.append((i, lows[i]))
    return result


def alternating_hl(swing_highs: list, swing_lows: list) -> list[tuple]:
    """
    Build alternating H→L→H→L sequence from swing points.
    Returns list of (index, value, 'H'|'L')
    """
    events = [(i, v, "H") for i, v in swing_highs] + [(i, v, "L") for i, v in swing_lows]
    events.sort(key=lambda x: x[0])
    seq = []
    for idx, val, typ in events:
        if not seq or seq[-1][2] != typ:
            seq.append([idx, val, typ])
        else:
            if typ == "H" and val > seq[-1][1]:
                seq[-1] = [idx, val, typ]
            elif typ == "L" and val < seq[-1][1]:
                seq[-1] = [idx, val, typ]
    return [tuple(x) for x in seq]


# ─── VCP Detection ────────────────────────────────────────────────────────────

@dataclass
class VCPResult:
    symbol:          str  = ""
    company:         str  = ""
    sector:          str  = ""
    is_vcp:          bool = False
    score:           float = 0.0

    current_price:   float = 0.0
    pivot:           float = 0.0
    pivot_date:      str   = ""
    dist_to_pivot:   float = 0.0    # negative = below pivot (buy zone)
    last_low:        float = 0.0
    stop_loss:       float = 0.0    # suggested stop = last contraction low - 1%

    n_contractions:  int   = 0
    depths:          list  = field(default_factory=list)   # % depth of each contraction
    vol_dryup:       bool  = False
    vol_ratio:       float = 0.0    # recent vol / 50d avg (< 1 = drying up)

    sma50:           float = 0.0
    sma150:          float = 0.0
    sma200:          float = 0.0
    price_vs_52wh:   float = 0.0    # % below 52W high
    price_vs_52wl:   float = 0.0    # % above 52W low
    trend_aligned:   bool  = False

    reject_reason:   str   = ""


def analyze_vcp(symbol: str, company: str, sector: str, ohlcv: list[dict]) -> VCPResult:
    res = VCPResult(symbol=symbol, company=company, sector=sector)

    if len(ohlcv) < 60:
        res.reject_reason = "insufficient_data"
        return res

    closes  = [d["close"]  for d in ohlcv]
    highs   = [d["high"]   for d in ohlcv]
    lows    = [d["low"]    for d in ohlcv]
    volumes = [d["volume"] for d in ohlcv]
    dates   = [d["date"]   for d in ohlcv]
    n       = len(ohlcv)

    # ── Moving averages ──────────────────────────────────────────────
    res.sma50  = sma(closes, 50)  or 0
    res.sma150 = sma(closes, 150) or 0
    res.sma200 = sma(closes, 200) or 0
    res.current_price = closes[-1]

    # ── Trend alignment (Stage 2) ────────────────────────────────────
    price = closes[-1]
    s50, s150, s200 = res.sma50, res.sma150, res.sma200

    # 必要條件：price > SMA50（最低要求）
    if s50 <= 0 or price <= s50:
        res.reject_reason = "no_stage2_uptrend"
        return res

    # 可選條件：有 SMA150 才比較
    if s150 > 0:
        if price < s150:
            res.reject_reason = "no_stage2_uptrend"
            return res
        if s50 < s150 * 0.97:          # SMA50 明顯低於 SMA150 = 下降趨勢
            res.reject_reason = "no_stage2_uptrend"
            return res

    # 可選條件：有 SMA200 才比較
    if s200 > 0:
        if price < s200 * 0.97:        # 允許 3% 容差（剛收復 SMA200）
            res.reject_reason = "no_stage2_uptrend"
            return res

    res.trend_aligned = True

    # ── 52W range ────────────────────────────────────────────────────
    w52 = min(252, n)
    high52 = max(highs[-w52:])
    low52  = min(lows[-w52:])
    res.price_vs_52wh = (price - high52) / high52 * 100   # negative = below high
    res.price_vs_52wl = (price - low52)  / low52  * 100   # positive = above low

    if res.price_vs_52wh < CFG["max_dist_from_52wh"]:   # 距52W高點超過門檻（影片條件5）
        res.reject_reason = "too_far_from_52wh"
        return res
    if res.price_vs_52wl < 30:    # not far enough above lows
        res.reject_reason = "too_close_to_52wl"
        return res

    # ── Swing detection ──────────────────────────────────────────────
    w = CFG["swing_window"]
    sw_highs = find_swing_highs(highs, lows, window=w)
    sw_lows  = find_swing_lows(highs, lows, window=w)
    seq      = alternating_hl(sw_highs, sw_lows)

    if len(seq) < 4:
        res.reject_reason = "not_enough_swings"
        return res

    # ── Extract H→L contractions ─────────────────────────────────────
    contractions = []
    for j in range(len(seq) - 1):
        if seq[j][2] == "H" and seq[j + 1][2] == "L":
            hi_i, hi_v = seq[j][0],     seq[j][1]
            lo_i, lo_v = seq[j + 1][0], seq[j + 1][1]
            depth   = (hi_v - lo_v) / hi_v * 100
            dur     = lo_i - hi_i
            seg_vol = sum(volumes[hi_i: lo_i + 1]) / max(dur, 1)
            contractions.append({
                "hi_i": hi_i, "lo_i": lo_i,
                "hi":   hi_v, "lo":   lo_v,
                "hi_date": dates[hi_i], "lo_date": dates[lo_i],
                "depth": depth, "duration": dur,
                "avg_vol": seg_vol,
            })

    if len(contractions) < CFG["min_contractions"]:
        res.reject_reason = "not_enough_contractions"
        return res

    # ── Use only the most recent contraction sequence ─────────────────
    # Walk backwards to find the longest valid sequence from the end
    valid_seq = [contractions[-1]]
    for k in range(len(contractions) - 2, -1, -1):
        prev = contractions[k]
        curr = valid_seq[0]
        if curr["depth"] <= prev["depth"] * CFG["depth_tolerance"]:
            valid_seq.insert(0, prev)
        else:
            break

    if len(valid_seq) < CFG["min_contractions"]:
        res.reject_reason = "depths_not_contracting"
        return res
    if len(valid_seq) > CFG["max_contractions"]:
        valid_seq = valid_seq[-CFG["max_contractions"]:]

    # First contraction must be meaningful (not a tiny wiggle)
    if valid_seq[0]["depth"] < CFG["first_contraction_min_depth"]:
        res.reject_reason = "first_contraction_too_small"
        return res

    res.n_contractions = len(valid_seq)
    res.depths         = [round(c["depth"], 1) for c in valid_seq]

    # ── Pivot = high of the last contraction ─────────────────────────
    last_c     = valid_seq[-1]
    res.pivot      = last_c["hi"]
    res.pivot_date = last_c["hi_date"]
    res.last_low   = last_c["lo"]
    res.stop_loss  = round(last_c["lo"] * 0.99, 2)

    # Distance from current price to pivot
    res.dist_to_pivot = (price - res.pivot) / res.pivot * 100

    # ── Buy zone check ───────────────────────────────────────────────
    # Must be below pivot (not broken out) or within 2% above pivot
    in_buy_zone = (-CFG["buy_zone_max"] * 100 <= res.dist_to_pivot <= CFG["buy_zone_min"] * 100)
    if not in_buy_zone:
        if res.dist_to_pivot > CFG["buy_zone_min"] * 100:
            res.reject_reason = "already_broken_out"
        else:
            res.reject_reason = "too_far_from_pivot"
        return res

    # Price must be above last contraction low (inside the base, not broken below)
    if price < last_c["lo"]:
        res.reject_reason = "below_last_low"
        return res

    # ── Volume dry-up ─────────────────────────────────────────────────
    vol50      = sum(volumes[-50:]) / 50 if n >= 50 else sum(volumes) / n
    # Use the last contraction window for recent volume
    lo_i       = last_c["lo_i"]
    hi_i_prev  = valid_seq[-2]["hi_i"] if len(valid_seq) >= 2 else max(0, lo_i - 20)
    recent_vol = sum(volumes[hi_i_prev: n]) / max(n - hi_i_prev, 1)

    res.vol_ratio  = recent_vol / vol50 if vol50 > 0 else 1.0
    res.vol_dryup  = res.vol_ratio < CFG["vol_dryup_ratio"]

    # ── Scoring (0–100) ──────────────────────────────────────────────
    score = 0.0

    # Contraction quality (max 35 pts)
    score += min(res.n_contractions * 8, 32)       # 2c=16, 3c=24, 4c=32
    depth_ratio = valid_seq[-1]["depth"] / valid_seq[0]["depth"]
    if depth_ratio < 0.40:  score += 3             # very tight last contraction
    elif depth_ratio < 0.60: score += 2

    # Volume dry-up (max 20 pts)
    if res.vol_dryup:
        score += 20
    elif res.vol_ratio < 1.0:
        score += 10

    # Proximity to pivot (max 25 pts): tighter = better
    proximity = abs(res.dist_to_pivot)             # 0 = at pivot
    if proximity <= 2:   score += 25
    elif proximity <= 5: score += 20
    elif proximity <= 8: score += 14
    else:                score += 7

    # Trend alignment quality (max 10 pts)
    if s50 > 0 and s200 > 0:
        sma_sep = (s50 - s200) / s200 * 100
        score += min(sma_sep * 0.5, 10)

    # 52W position (max 10 pts): near highs = stronger base
    if res.price_vs_52wh > -5:   score += 10
    elif res.price_vs_52wh > -10: score += 7
    elif res.price_vs_52wh > -15: score += 5
    elif res.price_vs_52wh > -25: score += 2

    res.score  = round(min(score, 100), 1)
    res.is_vcp = True
    return res


# ─── Screener Runner ─────────────────────────────────────────────────────────

def run_screener(symbols: list[str] | None = None, limit: int = 80, use_index: bool = False, use_broad: bool = False) -> list[VCPResult]:
    if not FMP_KEY:
        print("ERROR: set FMP_API_KEY environment variable first.")
        sys.exit(1)

    today = datetime.date.today().isoformat()
    print(f"\n{'═'*64}")
    print(f"  VCP Screener  —  {today}")
    print(f"{'═'*64}\n")

    # Build candidate list
    if symbols:
        candidates = [{"symbol": s, "companyName": s, "sector": ""} for s in symbols]
    elif use_index:
        print("  Fetching S&P 500 + Nasdaq 100 constituents...")
        candidates = get_index_universe()
        print(f"  → {len(candidates)} unique stocks (S&P500 + NDX100 combined)\n")
    elif use_broad:
        print("  Fetching US large + mid cap stocks (market cap > $1B)...")
        candidates = get_broad_universe()
        print(f"  → {len(candidates)} stocks | 預計掃描時間 ~{len(candidates)//240} 分鐘\n")
    else:
        print("  Fetching universe from FMP screener...")
        raw = get_universe(limit)
        seen, candidates = set(), []
        for c in raw:
            nm = c.get("companyName", c["symbol"])
            if nm not in seen:
                seen.add(nm)
                candidates.append(c)
        print(f"  → {len(candidates)} unique candidates\n")

    results: list[VCPResult] = []
    total = len(candidates)

    for i, c in enumerate(candidates):
        sym  = c["symbol"]
        name = c.get("companyName", sym)
        sec  = c.get("sector", "")
        print(f"  [{i+1:>3}/{total}] {sym:<8}", end="  ", flush=True)

        try:
            ohlcv = get_ohlcv(sym, days=CFG["history_days"])
            res   = analyze_vcp(sym, name, sec, ohlcv)

            if res.is_vcp:
                tag = f"✅ SCORE {res.score:>5.1f} | pivot ${res.pivot:.2f} | {res.dist_to_pivot:+.1f}% | {res.n_contractions}c {res.depths}"
            else:
                tag = f"✗  {res.reject_reason}"
            print(tag)
            results.append(res)

        except Exception as e:
            print(f"✗  error: {e}")

        time.sleep(0.25)   # rate-limit buffer

    # ── 基本面二次過濾（只對 VCP 候選股，影片條件6：上季營收增長 > 5%）──
    if CFG["apply_fundamental_filter"]:
        vcp_found = [r for r in results if r.is_vcp]
        if vcp_found:
            print(f"\n  基本面過濾：對 {len(vcp_found)} 支 VCP 候選股查詢上季營收增長...\n")
            for res in vcp_found:
                growth = get_revenue_growth(res.symbol)
                if growth is not None and growth < CFG["min_revenue_growth"]:
                    res.is_vcp = False
                    res.reject_reason = f"rev_growth_low({growth*100:.1f}%)"
                    print(f"    {res.symbol:<8} ✗  上季營收 {growth*100:.1f}% < {CFG['min_revenue_growth']*100:.0f}%")
                else:
                    g_str = f"{growth*100:.1f}%" if growth is not None else "無數據(保留)"
                    print(f"    {res.symbol:<8} ✅ 上季營收 {g_str}")
                time.sleep(0.2)

    return results


# ─── Report ──────────────────────────────────────────────────────────────────

def print_report(results: list[VCPResult]):
    vcps = sorted([r for r in results if r.is_vcp], key=lambda x: x.score, reverse=True)

    print(f"\n{'═'*64}")
    print(f"  VCP Candidates Found: {len(vcps)}")
    print(f"{'═'*64}\n")

    if not vcps:
        print("  No VCP setups found today.\n")
        return

    # ── Sector breakdown ─────────────────────────────────────────────
    from collections import Counter
    sector_counts = Counter(r.sector or "Unknown" for r in vcps)
    print(f"  {'─'*40}")
    print(f"  板塊 Setup 分布（共 {len(vcps)} 個）")
    print(f"  {'─'*40}")
    for sector, count in sector_counts.most_common():
        bar = "█" * count
        print(f"  {sector:<28} {count:>2}  {bar}")
    print(f"  {'─'*40}\n")

    for rank, r in enumerate(vcps, 1):
        entry      = round(r.pivot * 1.005, 2)   # 買入點 = pivot + 0.5%
        target     = round(r.pivot + (r.pivot - r.last_low) * 2, 2)  # 2:1 RR
        risk_pct   = (entry - r.stop_loss) / entry * 100
        reward_pct = (target - entry) / entry * 100

        depth_str  = " → ".join(f"{d:.1f}%" for d in r.depths)
        vol_str    = f"{r.vol_ratio:.2f}x avg" if r.vol_ratio else "N/A"

        print(f"  #{rank}  {r.symbol} — {r.company}")
        print(f"       Sector        : {r.sector}")
        print(f"       Score         : {r.score}/100")
        print(f"       Current price : ${r.current_price:.2f}")
        print(f"       Pivot (買入區) : ${r.pivot:.2f}  ({r.pivot_date})")
        print(f"       Distance       : {r.dist_to_pivot:+.1f}%  (負 = 尚未突破，正 = 剛突破)")
        print(f"       Contractions  : {r.n_contractions}次   {depth_str}")
        print(f"       Volume         : {vol_str}  {'✅ 萎縮' if r.vol_dryup else '⚠ 量未縮'}")
        print(f"       ─── 交易計劃 ───────────────────────────────")
        print(f"       Entry          : ${entry}  (pivot 突破進場)")
        print(f"       Stop Loss      : ${r.stop_loss}  (最後整固低點 -1%)")
        print(f"       Target         : ${target}  (2:1 Risk/Reward)")
        print(f"       Risk/Reward    : -{risk_pct:.1f}% / +{reward_pct:.1f}%")
        print(f"       SMA50/150/200  : ${r.sma50:.0f} / ${r.sma150:.0f} / ${r.sma200:.0f}")
        print(f"       vs 52W High    : {r.price_vs_52wh:+.1f}%")
        print(f"       vs 52W Low     : {r.price_vs_52wl:+.1f}%")
        print()


def save_json(results: list[VCPResult], path: str = "vcp_results.json"):
    vcps = [r.__dict__ for r in results if r.is_vcp]
    data = {
        "date":        datetime.date.today().isoformat(),
        "total_scanned": len(results),
        "vcp_count":   len(vcps),
        "candidates":  sorted(vcps, key=lambda x: x["score"], reverse=True),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Results saved → {path}\n")


def send_telegram(results: list[VCPResult]):
    token   = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    vcps = sorted([r for r in results if r.is_vcp], key=lambda x: x.score, reverse=True)

    # 載入前日結果，找出新標
    prev_symbols: set[str] = set()
    prev_path = Path("results/previous.json")
    if prev_path.exists():
        try:
            with open(prev_path) as f:
                prev_data = json.load(f)
            prev_symbols = {c["symbol"] for c in prev_data.get("candidates", [])}
        except Exception:
            pass

    new_vcps = [r for r in vcps if r.symbol not in prev_symbols]

    lines = [
        f"📈 <b>VCP 每日掃描</b> — {datetime.date.today()}",
        f"掃描 <b>{len(results):,}</b> 支　｜　候選 <b>{len(vcps)}</b> 支　｜　新增 <b>{len(new_vcps)}</b> 支",
        "",
        "📋 <b>全部候選股（分數排序）</b>",
    ]

    for i, r in enumerate(vcps, 1):
        vol_icon   = "✅" if r.vol_dryup else "⚠️"
        new_mark   = " 🆕" if r.symbol not in prev_symbols else ""
        sector_str = SECTOR_ZH.get(r.sector or "", r.sector or "—")
        lines.append(
            f"#{i:02d} <b>{r.symbol}</b>  {r.score:.0f}分  {r.n_contractions}收縮 {vol_icon}  {sector_str}{new_mark}"
        )

    if new_vcps:
        lines.append("")
        lines.append(f"🆕 <b>今日新增（{len(new_vcps)} 支）</b>")
        for r in new_vcps:
            vol_icon   = "✅" if r.vol_dryup else "⚠️"
            sector_str = SECTOR_ZH.get(r.sector or "", r.sector or "—")
            lines.append(f"• <b>{r.symbol}</b>  {r.score:.0f}分  {r.n_contractions}收縮 {vol_icon}  {sector_str}")

    lines.append("")
    lines.append(f'🔗 <a href="https://vcp-screener-2pb3mqkqze72yaegcybulg.streamlit.app">開啟 VCP 網站</a>')

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3950] + f'\n...\n\n🔗 <a href="https://vcp-screener-2pb3mqkqze72yaegcybulg.streamlit.app">開啟 VCP 網站</a>'

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=15,
    )
    if resp.ok:
        print("  Telegram 通知已發送 ✅")
    else:
        print(f"  Telegram 發送失敗：{resp.text}")


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VCP Screener using FMP API")
    parser.add_argument("--limit",     type=int, default=80,
                        help="Universe size from FMP screener (default: 80)")
    parser.add_argument("--watchlist", type=str, default=None,
                        help="Comma-separated symbols, e.g. AAPL,MSFT,NVDA")
    parser.add_argument("--index",     action="store_true",
                        help="掃 S&P 500 + Nasdaq 100 全部成分股")
    parser.add_argument("--broad",     action="store_true",
                        help="掃美股大型+中型股（市值>10億，~6000支，約25-30分鐘）")
    parser.add_argument("--output",    type=str, default="vcp_results.json",
                        help="Output JSON path")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.watchlist.split(",")] if args.watchlist else None
    results = run_screener(symbols=symbols, limit=args.limit, use_index=args.index, use_broad=args.broad)
    print_report(results)
    save_json(results, path=args.output)
    send_telegram(results)


if __name__ == "__main__":
    main()
