#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_financials.py — 메가캡 명단의 재무(매출·영업이익) 시계열 → docs/financials.json
표준 라이브러리만 사용. 매일 실행(분기 데이터라 실제 변동은 분기 1회).

핵심: 야후 무료 fundamentals-timeseries는 연 4개·분기 5개까지만 준다.
     그래서 매 실행마다 기존 financials.json에 **병합(누적)**해 기간이 시간이 지날수록
     연 5개+·분기 8개+로 쌓이게 한다.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
UNIVERSE = os.path.join(BASE, "docs", "megacap.json")
OUT = os.path.join(BASE, "docs", "financials.json")
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) etf-flow-tracker/1.0"

_last_req = [0.0]

def _throttle():
    wait = _last_req[0] + 0.5 - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()

def get_crumb():
    try:
        req = urllib.request.Request("https://fc.yahoo.com", headers={"User-Agent": UA})
        cookie = ""
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                cookie = r.headers.get("Set-Cookie", "")
        except urllib.error.HTTPError as e:
            cookie = e.headers.get("Set-Cookie", "")
        cookie = cookie.split(";")[0] if cookie else ""
        if not cookie:
            return None, None
        hdr = {"User-Agent": UA, "Cookie": cookie}
        req2 = urllib.request.Request("https://query1.finance.yahoo.com/v1/test/getcrumb", headers=hdr)
        with urllib.request.urlopen(req2, timeout=15) as r:
            crumb = r.read().decode("utf-8").strip()
        return (cookie, crumb) if crumb and "<" not in crumb else (None, None)
    except Exception as e:
        print(f"  [crumb-fail] {e}")
        return None, None

TYPES = ("annualTotalRevenue,annualOperatingIncome,"
         "quarterlyTotalRevenue,quarterlyOperatingIncome")

def fetch_ts(ticker, cookie, crumb):
    """{period: {date: {rev, op, ccy}}} 형태로 파싱. period='annual'|'quarterly'."""
    url = ("https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/"
           + urllib.parse.quote(ticker) + "?symbol=" + urllib.parse.quote(ticker)
           + "&type=" + TYPES + "&period1=1420070400&period2=1893456000&crumb=" + urllib.parse.quote(crumb))
    hdr = {"User-Agent": UA, "Cookie": cookie}
    for attempt in range(3):
        _throttle()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20) as r:
                raw = r.read()
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [skip] {ticker} -> {e}")
                return None
    try:
        results = json.loads(raw)["timeseries"]["result"]
    except Exception:
        return None
    out = {"annual": {}, "quarterly": {}}
    for r in results:
        t = r["meta"]["type"][0]  # e.g. annualTotalRevenue
        period = "annual" if t.startswith("annual") else "quarterly"
        field = "rev" if "Revenue" in t else "op"
        for v in r.get(t, []):
            if not v:
                continue
            d = v.get("asOfDate")
            rv = v.get("reportedValue", {})
            val = rv.get("raw")
            if d is None or val is None:
                continue
            slot = out[period].setdefault(d, {})
            slot[field] = round(val / 1e6, 1)  # 백만 단위
            ccy = v.get("currencyCode")
            if ccy:
                slot["ccy"] = ccy
    return out

def merge_periods(old_list, new_map):
    """old_list: 기존 [{date, rev, op, ccy}] · new_map: {date:{rev,op,ccy}} → 병합 후 날짜순 정렬"""
    by_date = {row["date"]: dict(row) for row in (old_list or [])}
    for d, slot in new_map.items():
        row = by_date.setdefault(d, {"date": d})
        if "rev" in slot:
            row["rev"] = slot["rev"]
        if "op" in slot:
            row["op"] = slot["op"]
        if "ccy" in slot:
            row["ccy"] = slot["ccy"]
    return [by_date[d] for d in sorted(by_date)]

def enrich(rows, is_quarter):
    """매출증가율(YoY, 분기는 QoQ 추가)·OPM·영업이익증가율 계산. rows는 날짜 오름차순."""
    for i, row in enumerate(rows):
        rev, op = row.get("rev"), row.get("op")
        row["opm"] = round(op / rev * 100, 1) if (rev and op is not None) else None
        # YoY: 연간=1칸 전, 분기=4칸 전
        back = 4 if is_quarter else 1
        if i - back >= 0:
            pr = rows[i - back].get("rev")
            po = rows[i - back].get("op")
            row["rev_yoy"] = round((rev / pr - 1) * 100, 1) if (rev and pr) else None
            row["op_yoy"] = round((op / po - 1) * 100, 1) if (op is not None and po not in (None, 0)) else None
        else:
            row["rev_yoy"] = None
            row["op_yoy"] = None
        if is_quarter:
            if i - 1 >= 0:
                pr = rows[i - 1].get("rev")
                po = rows[i - 1].get("op")
                row["rev_qoq"] = round((rev / pr - 1) * 100, 1) if (rev and pr) else None
                row["op_qoq"] = round((op / po - 1) * 100, 1) if (op is not None and po not in (None, 0)) else None
            else:
                row["rev_qoq"] = None
                row["op_qoq"] = None
    return rows

def main():
    print(f"=== fetch_financials.py 시작 ({datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}) ===")
    if not os.path.exists(UNIVERSE):
        print("[오류] megacap.json 없음 — fetch_megacap.py를 먼저 실행")
        sys.exit(1)
    stocks = json.load(open(UNIVERSE, encoding="utf-8")).get("stocks", [])

    existing = {}
    if os.path.exists(OUT):
        try:
            existing = json.load(open(OUT, encoding="utf-8")).get("financials", {})
        except Exception:
            existing = {}

    cookie, crumb = get_crumb()
    if not crumb:
        print("[경고] 크럼 확보 실패 — 종료")
        sys.exit(0)

    out = {}
    got = 0
    for i, s in enumerate(stocks, 1):
        tk = s["ticker"]
        ts = fetch_ts(tk, cookie, crumb)
        prev = existing.get(tk, {})
        if ts and (ts["annual"] or ts["quarterly"]):
            a = enrich(merge_periods(prev.get("annual"), ts["annual"]), False)
            q = enrich(merge_periods(prev.get("quarterly"), ts["quarterly"]), True)
            out[tk] = {"name": s["name"], "annual": a[-6:], "quarterly": q[-10:]}
            got += 1
        elif prev:
            out[tk] = prev  # 이번엔 못 받았지만 과거 데이터 유지
        if i % 50 == 0:
            print(f"  {i}/{len(stocks)} (재무 확보 {got})")

    data = {"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
            "count": len(out), "financials": out}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"=== 완료: {got}/{len(stocks)}종 재무 확보 → {OUT} ===")

if __name__ == "__main__":
    main()
