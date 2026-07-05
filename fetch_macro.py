#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_macro.py — 매크로 지표 + 자체 산출 공포·탐욕 프록시 지수 → docs/macro.json
표준 라이브러리만 사용. API 키 불필요:
  - 야후 차트 API: S&P500·나스닥·VIX·정크본드(HYG)·투자등급채(LQD)·장기국채(TLT) 일별 종가
  - FRED CSV 다운로드(fredgraph.csv, API 키 불필요): CPI·PPI·PCE·실업률·기준금리·비농업고용·
    신규실업수당청구·M2·10년물금리(DGS10)·소비자심리지수

공포·탐욕 지수는 CNN 공포탐욕지수의 "원본 데이터"가 아니라, 그 방법론을 참고해
무료로 구할 수 있는 데이터만으로 이 프로젝트가 자체 산출한 프록시 지수다(원본과 다를 수 있음).
5개 하위지표(모멘텀·변동성·정크본드 수요·안전자산 수요·주가 강도)를 전체 기간 백분위로
정규화해 평균한다 — 전체 표본 기준 정규화이므로 과거 특정 시점 실시간 값과는 다를 수 있음.
"""
import json
import os
import sys
import time
import bisect
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "docs", "macro.json")
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) etf-flow-tracker/1.0"

_last_req = [0.0]

def _throttle():
    wait = _last_req[0] + 0.5 - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()

def fetch_yahoo(ticker, rng):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={rng}&interval=1d"
    for attempt in range(3):
        _throttle()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read())
            res = d["chart"]["result"][0]
            ts = res["timestamp"]
            closes = res["indicators"]["quote"][0]["close"]
            out = []
            for t, c in zip(ts, closes):
                if c is None:
                    continue
                date = datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
                out.append((date, round(c, 4)))
            return out
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [skip] 야후 {ticker} -> {e}")
                return []

def fetch_fred(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    for attempt in range(3):
        _throttle()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                text = r.read().decode("utf-8")
            lines = text.strip().splitlines()[1:]  # 헤더 스킵
            out = []
            for ln in lines:
                parts = ln.split(",")
                if len(parts) != 2:
                    continue
                date, val = parts
                if val == "." or val == "":
                    continue
                try:
                    out.append((date, float(val)))
                except ValueError:
                    continue
            return out
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [skip] FRED {series_id} -> {e}")
                return []

def to_dict(series):
    return dict(series)

def percentile_rank_series(values):
    """values: [v0, v1, ...] (None 허용) -> 각 지점의 전체표본 대비 백분위(0~100), None은 None 유지."""
    valid_sorted = sorted(v for v in values if v is not None)
    n = len(valid_sorted)
    if n < 2:
        return [None] * len(values)
    out = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        lo = bisect.bisect_left(valid_sorted, v)
        hi = bisect.bisect_right(valid_sorted, v)
        rank = (lo + hi) / 2.0
        out.append(round(rank / (n - 1) * 100, 2))
    return out

def rolling_mean(vals, window):
    out = [None] * len(vals)
    s = 0.0
    cnt = 0
    q = []
    for i, v in enumerate(vals):
        q.append(v)
        if v is not None:
            s += v
            cnt += 1
        if len(q) > window:
            old = q.pop(0)
            if old is not None:
                s -= old
                cnt -= 1
        if cnt >= max(5, window // 3):
            out[i] = s / cnt
    return out

def rolling_max(vals, window):
    out = [None] * len(vals)
    for i in range(len(vals)):
        lo = max(0, i - window + 1)
        window_vals = [v for v in vals[lo:i + 1] if v is not None]
        out[i] = max(window_vals) if window_vals else None
    return out

def pct_return(vals, back):
    out = [None] * len(vals)
    for i in range(len(vals)):
        if i - back >= 0 and vals[i] is not None and vals[i - back] not in (None, 0):
            out[i] = (vals[i] / vals[i - back] - 1) * 100
    return out

def build_fear_greed(dates, spx, vix, hyg, lqd, tlt):
    """5개 하위지표를 계산해 전체기간 백분위 평균으로 합성. 각 하위지표는 dates 기준 정렬된 리스트."""
    spx_ma125 = rolling_mean(spx, 125)
    momentum_raw = [((s / m - 1) * 100) if (s is not None and m not in (None, 0)) else None
                    for s, m in zip(spx, spx_ma125)]
    volatility_raw = [(-v if v is not None else None) for v in vix]  # VIX가 높을수록 공포 -> 부호 반전
    spx_high252 = rolling_max(spx, 252)
    strength_raw = [((s / h - 1) * 100) if (s is not None and h not in (None, 0)) else None
                    for s, h in zip(spx, spx_high252)]
    hyg_ret = pct_return(hyg, 63)
    lqd_ret = pct_return(lqd, 63)
    junk_raw = [((h - l) if (h is not None and l is not None) else None) for h, l in zip(hyg_ret, lqd_ret)]
    spx_ret20 = pct_return(spx, 20)
    tlt_ret20 = pct_return(tlt, 20)
    haven_raw = [((s - t) if (s is not None and t is not None) else None) for s, t in zip(spx_ret20, tlt_ret20)]

    momentum_pct = percentile_rank_series(momentum_raw)
    volatility_pct = percentile_rank_series(volatility_raw)
    strength_pct = percentile_rank_series(strength_raw)
    junk_pct = percentile_rank_series(junk_raw)
    haven_pct = percentile_rank_series(haven_raw)

    composite = []
    n_used = []
    for i in range(len(dates)):
        parts = [p[i] for p in (momentum_pct, volatility_pct, strength_pct, junk_pct, haven_pct) if p[i] is not None]
        if len(parts) >= 3:  # 최소 3개 하위지표가 있어야 합성치 계산(정크본드·안전자산은 상장 이후에만 존재)
            composite.append(round(sum(parts) / len(parts), 1))
        else:
            composite.append(None)
        n_used.append(len(parts))
    return {
        "composite": composite,
        "n_components": n_used,
        "momentum_pct": momentum_pct,
        "volatility_pct": volatility_pct,
        "strength_pct": strength_pct,
        "junk_demand_pct": junk_pct,
        "safe_haven_pct": haven_pct,
    }

def find_drawdown_episodes(dates, prices, min_decline_pct=10.0):
    """전고점 대비 min_decline_pct% 이상 하락한 구간을 peak/trough/recovery로 식별."""
    episodes = []
    peak_i = 0
    in_episode = False
    trough_i = None
    for i in range(1, len(prices)):
        if prices[i] is None or prices[peak_i] is None:
            continue
        if prices[i] >= prices[peak_i]:
            if in_episode:
                # 전고점 회복 -> 에피소드 종료
                pct = (prices[trough_i] / prices[peak_i] - 1) * 100
                if pct <= -min_decline_pct:
                    episodes.append({
                        "peak_date": dates[peak_i], "peak_price": round(prices[peak_i], 2),
                        "trough_date": dates[trough_i], "trough_price": round(prices[trough_i], 2),
                        "recovery_date": dates[i], "pct_decline": round(pct, 1), "ongoing": False,
                    })
                in_episode = False
            peak_i = i
            trough_i = None
            continue
        # 현재가 < 전고점
        if trough_i is None or prices[i] < prices[trough_i]:
            trough_i = i
        decline = (prices[i] / prices[peak_i] - 1) * 100
        if decline <= -min_decline_pct:
            in_episode = True
    if in_episode and trough_i is not None:
        pct = (prices[trough_i] / prices[peak_i] - 1) * 100
        episodes.append({
            "peak_date": dates[peak_i], "peak_price": round(prices[peak_i], 2),
            "trough_date": dates[trough_i], "trough_price": round(prices[trough_i], 2),
            "recovery_date": None, "pct_decline": round(pct, 1), "ongoing": True,
        })
    for ep in episodes:
        d = abs(ep["pct_decline"])
        ep["severity"] = "severe" if d >= 30 else "high" if d >= 20 else "significant" if d >= 15 else "moderate"
    return episodes

def weekly_downsample(dates, *series_list):
    """각 ISO 주의 마지막 거래일(금요일 근접) 값만 남긴다."""
    idx_by_week = {}
    for i, d in enumerate(dates):
        dt = datetime.strptime(d, "%Y-%m-%d")
        wk = dt.strftime("%G-W%V")
        idx_by_week[wk] = i  # 마지막으로 덮어써지는 것이 그 주의 마지막 거래일
    weeks = sorted(idx_by_week.keys())
    out_dates = [dates[idx_by_week[w]] for w in weeks]
    out_series = [[s[idx_by_week[w]] for w in weeks] for s in series_list]
    return out_dates, out_series

def main():
    print(f"=== fetch_macro.py 시작 ({datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}) ===")

    print("야후 시장 데이터 수집 중...")
    spx_raw = fetch_yahoo("^GSPC", "30y")
    ixic_raw = fetch_yahoo("^IXIC", "30y")
    vix_raw = fetch_yahoo("^VIX", "30y")
    hyg_raw = fetch_yahoo("HYG", "25y")
    lqd_raw = fetch_yahoo("LQD", "25y")
    tlt_raw = fetch_yahoo("TLT", "25y")

    if len(spx_raw) < 100:
        print("[오류] S&P500 데이터 확보 실패 — 종료")
        sys.exit(1)

    # 공통 캘린더: SPX 거래일 기준으로 정렬, 나머지는 전일 값으로 forward-fill
    dates = [d for d, _ in spx_raw]
    spx_map = to_dict(spx_raw)
    ixic_map = to_dict(ixic_raw)
    vix_map = to_dict(vix_raw)
    hyg_map = to_dict(hyg_raw)
    lqd_map = to_dict(lqd_raw)
    tlt_map = to_dict(tlt_raw)

    def ffill_series(m):
        out = []
        last = None
        for d in dates:
            if d in m:
                last = m[d]
            out.append(last)
        return out

    spx = ffill_series(spx_map)
    ixic = ffill_series(ixic_map)
    vix = ffill_series(vix_map)
    hyg = ffill_series(hyg_map)
    lqd = ffill_series(lqd_map)
    tlt = ffill_series(tlt_map)

    print("FRED 매크로 지표 수집 중...")
    fred_series = {
        "cpi": "CPIAUCSL", "ppi": "PPIACO", "pce": "PCEPI", "unrate": "UNRATE",
        "fedfunds": "FEDFUNDS", "payems": "PAYEMS", "icsa": "ICSA", "m2": "M2SL",
        "dgs10": "DGS10", "umcsent": "UMCSENT",
    }
    fred_out = {}
    for key, sid in fred_series.items():
        rows = fetch_fred(sid)
        fred_out[key] = [{"date": d, "value": v} for d, v in rows]
        print(f"  {key}({sid}): {len(rows)}개 관측치")

    print("공포·탐욕 프록시 지수 산출 중...")
    fg = build_fear_greed(dates, spx, vix, hyg, lqd, tlt)

    print("드로다운(조정) 에피소드 탐지 중...")
    spx_episodes = find_drawdown_episodes(dates, spx, 10.0)
    ixic_episodes = find_drawdown_episodes(dates, ixic, 10.0)
    print(f"  S&P500 10%+ 조정 {len(spx_episodes)}건, 나스닥 {len(ixic_episodes)}건")

    # 일별 현재가 대비 드로다운(%) — 프론트에서 차트 음영에 사용 (전체기간 누적 최고가 기준)
    running_peak = []
    m = None
    for p in spx:
        if p is not None:
            m = p if m is None else max(m, p)
        running_peak.append(m)
    spx_drawdown = [round((p / rp - 1) * 100, 2) if (p is not None and rp) else None for p, rp in zip(spx, running_peak)]

    # 최근 3년 = 일별 해상도, 전체기간 = 주별 다운샘플
    cutoff = (datetime.strptime(dates[-1], "%Y-%m-%d") - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    recent_start_i = bisect.bisect_left(dates, cutoff)

    daily = {
        "dates": dates[recent_start_i:],
        "spx": spx[recent_start_i:], "ixic": ixic[recent_start_i:], "vix": vix[recent_start_i:],
        "hyg": hyg[recent_start_i:], "lqd": lqd[recent_start_i:], "tlt": tlt[recent_start_i:],
        "fear_greed": fg["composite"][recent_start_i:],
        "drawdown_pct": spx_drawdown[recent_start_i:],
    }

    w_dates, (w_spx, w_ixic, w_vix, w_fg, w_dd) = weekly_downsample(
        dates, spx, ixic, vix, fg["composite"], spx_drawdown)
    weekly = {"dates": w_dates, "spx": w_spx, "ixic": w_ixic, "vix": w_vix,
              "fear_greed": w_fg, "drawdown_pct": w_dd}

    latest_fg = next((v for v in reversed(fg["composite"]) if v is not None), None)
    latest_components = {}
    for key in ("momentum_pct", "volatility_pct", "strength_pct", "junk_demand_pct", "safe_haven_pct"):
        latest_components[key] = next((v for v in reversed(fg[key]) if v is not None), None)

    data = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "methodology": ("자체 산출 공포·탐욕 프록시 지수 — CNN 공포탐욕지수의 데이터를 그대로 쓴 것이 아니라, "
                        "무료로 구할 수 있는 시장데이터(S&P500 모멘텀·VIX 변동성·정크본드 대비 투자등급채 수요·"
                        "주식 대비 장기국채 안전자산 수요·52주 고점 대비 주가강도) 5개를 전체기간 백분위로 "
                        "정규화해 평균한 것. 전체 표본 기준 정규화라 과거 특정 시점에 실시간으로 관측했을 값과는 "
                        "다를 수 있음. 정크본드/안전자산 지표는 해당 ETF 상장 이후(2002~2007년)부터 반영됨."),
        "latest_fear_greed": latest_fg,
        "latest_components": latest_components,
        "daily": daily,
        "weekly": weekly,
        "macro_monthly": fred_out,
        "drawdown_episodes": {"spx": spx_episodes, "ixic": ixic_episodes},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"=== 완료: {len(dates)}거래일 처리 → {OUT} ===")

if __name__ == "__main__":
    main()
