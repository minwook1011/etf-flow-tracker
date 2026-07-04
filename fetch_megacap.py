#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_megacap.py — megacap_universe.json 명단의 시세·모멘텀 갱신 → docs/megacap.json
표준 라이브러리만 사용. 매일 실행.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
UNIVERSE = os.path.join(BASE, "docs", "megacap_universe.json")
OUT = os.path.join(BASE, "docs", "megacap.json")
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) etf-flow-tracker/1.0"

_last_req = [0.0]

def _throttle():
    wait = _last_req[0] + 0.5 - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()

def http_get(url, timeout=20):
    for attempt in range(3):
        _throttle()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [skip] {url[:80]} -> {e}")
    return None

def fetch_closes(ticker):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(ticker)}?range=1y&interval=1d")
    raw = http_get(url)
    if not raw:
        return None
    try:
        res = json.loads(raw)["chart"]["result"][0]
        ts = res.get("timestamp") or []
        q = res["indicators"]["quote"][0]
        dates, closes, vols = [], [], []
        for i, t in enumerate(ts):
            c = q["close"][i]
            if c is None:
                continue
            dates.append(datetime.fromtimestamp(t, tz=KST).strftime("%Y-%m-%d"))
            closes.append(float(c))
            vols.append(int(q["volume"][i] or 0))
        return (dates, closes, vols) if len(closes) >= 2 else None
    except Exception:
        return None

def pct(a, b):
    if not b:
        return 0.0
    return round((a / b - 1) * 100, 2)

def ret_n(closes, n):
    if len(closes) <= n:
        return pct(closes[-1], closes[0])
    return pct(closes[-1], closes[-1 - n])

def main():
    print(f"=== fetch_megacap.py 시작 ({datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}) ===")
    if not os.path.exists(UNIVERSE):
        print("[오류] megacap_universe.json 없음 — fetch_universe.py를 먼저 실행")
        sys.exit(1)
    uni = json.load(open(UNIVERSE, encoding="utf-8"))
    stocks_in = uni.get("stocks", [])

    out_stocks = []
    fail = 0
    for i, s in enumerate(stocks_in, 1):
        tk = s["ticker"]
        r = fetch_closes(tk)
        if not r:
            fail += 1
            continue
        dates, closes, vols = r
        year = dates[-1][:4]
        base = None
        for d, c in zip(dates, closes):
            if d[:4] < year:
                base = c
        ytd = pct(closes[-1], base if base is not None else closes[0])
        dv = [c * v for c, v in zip(closes, vols)]
        vr = round((sum(dv[-5:]) / 5) / (sum(dv[-20:]) / 20), 2) if len(dv) >= 20 and sum(dv[-20:]) > 0 else 1.0
        out_stocks.append({
            "ticker": tk, "name": s["name"], "sector": s["sector"],
            "mcap_usd": s.get("mcap_usd", 0),
            "price": round(closes[-1], 4),
            "r1w": ret_n(closes, 5), "r1m": ret_n(closes, 21),
            "r3m": ret_n(closes, 63), "ytd": ytd,
            "from_high": pct(closes[-1], max(closes[-252:])),
            "vol_ratio": vr,
        })
        if i % 50 == 0:
            print(f"  {i}/{len(stocks_in)} (실패 {fail})")

    if len(out_stocks) < len(stocks_in) * 0.2:
        print("[경고] 80% 이상 실패 — 기존 megacap.json 유지 후 종료")
        sys.exit(0)

    data = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "universe_updated": uni.get("updated", ""),
        "count": len(out_stocks),
        "stocks": out_stocks,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"=== 완료: {len(out_stocks)}종 저장 (실패 {fail}) ===")

if __name__ == "__main__":
    main()
