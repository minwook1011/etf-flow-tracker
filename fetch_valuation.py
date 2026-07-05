#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_valuation.py — S&P500 밸류에이션 시계열 → docs/valuation.json
표준 라이브러리만 사용. API 키 불필요.

두 축으로 밸류에이션을 본다:
  1) 후행 P/E (trailing) — multpl.com 월별 히스토리(1871~현재)에서 최근 ~30년치. 무료로 얻을 수
     있는 유일한 장기 밸류에이션 시계열. S&P500 지수와 겹쳐 보기 위한 배경.
  2) 포워드 P/E (forward) — megacap.json의 pe_now(올해)·pe_next(내년) 선행PER을 시총가중 평균해
     "S&P500 기업들의 포워드 밸류에이션" 프록시로 산출. 포워드 P/E 과거 시계열은 유료(FactSet 등)라
     무료로는 현재값만 가능 → 매 실행마다 스냅샷을 날짜별로 누적해 시간이 지나면 포워드 라인도 그린다.
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
MEGA = os.path.join(BASE, "docs", "megacap.json")
OUT = os.path.join(BASE, "docs", "valuation.json")
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) etf-flow-tracker/1.0"

MONTHS = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
          "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}

def scrape_multpl(slug, keep_months=372):
    """multpl.com 월별 테이블에서 (YYYY-MM-01, value) 리스트를 최신→과거 순으로. keep_months개만 유지."""
    url = "https://www.multpl.com/" + slug + "/table/by-month"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  [skip] multpl {slug} -> {e}")
                return []
    # <td>Jul 2, 2026</td> <td> ...(abbr/entity)... 32.15 </td>
    pairs = re.findall(r"<td>([A-Z][a-z]{2}) (\d{1,2}), (\d{4})</td>\s*<td>(.*?)</td>", html, re.S)
    out = []
    for mon, day, year, valcell in pairs:
        # HTML 엔티티(&#x2002; 안의 '2002' 등)와 태그를 먼저 제거 → 소수점 있는 숫자만 값으로 인정
        clean = re.sub(r"&#?\w+;", " ", valcell)
        clean = re.sub(r"<[^>]+>", " ", clean)
        m = re.search(r"[0-9]+\.[0-9]+", clean)
        if not m:
            continue
        date = "%s-%s-01" % (year, MONTHS.get(mon, "01"))
        try:
            out.append({"date": date, "value": float(m.group(0))})
        except ValueError:
            continue
    return out[:keep_months]

def weighted_fwd_pe(stocks, field):
    """시총가중 조화평균(= sum(mcap)/sum(mcap/pe)). 음수·이상치 PER 제외."""
    num = den = 0.0
    n = 0
    for s in stocks:
        pe = s.get(field)
        mc = s.get("mcap_usd")
        if pe and pe > 0 and pe < 500 and mc:
            num += mc
            den += mc / pe
            n += 1
    return (round(num / den, 2), n) if den else (None, 0)

def main():
    print(f"=== fetch_valuation.py 시작 ({datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}) ===")

    print("multpl.com 후행 P/E·CAPE 수집...")
    trailing = scrape_multpl("s-p-500-pe-ratio", keep_months=372)   # 최근 31년
    cape = scrape_multpl("shiller-pe", keep_months=372)
    print(f"  후행 P/E {len(trailing)}개월, CAPE {len(cape)}개월")

    today = datetime.now(KST).strftime("%Y-%m-%d")
    fwd_this = fwd_next = None
    if os.path.exists(MEGA):
        try:
            stocks = json.load(open(MEGA, encoding="utf-8")).get("stocks", [])
            fwd_this, n1 = weighted_fwd_pe(stocks, "pe_now")
            fwd_next, n2 = weighted_fwd_pe(stocks, "pe_next")
            print(f"  메가캡 시총가중 포워드 P/E: 올해 {fwd_this}({n1}종) · 내년 {fwd_next}({n2}종)")
        except Exception as e:
            print(f"  [경고] megacap.json 포워드 P/E 계산 실패: {e}")

    # 기존 파일 로드(포워드 스냅샷 누적 유지)
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            prev = {}
    snaps = dict(prev.get("fwd_pe_snapshots") or {})
    if fwd_this is not None:
        snaps[today] = {"this": fwd_this, "next": fwd_next}

    # 후행 P/E는 못 받으면 기존 값 유지
    if not trailing and prev.get("trailing_pe"):
        trailing = prev["trailing_pe"]
    if not cape and prev.get("cape"):
        cape = prev["cape"]

    data = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "note": ("후행 P/E·CAPE는 multpl.com(무료) 월별 히스토리. 포워드 P/E는 megacap.json의 "
                 "선행PER(올해·내년)을 시총가중 조화평균한 'S&P500 기업 포워드 밸류에이션' 프록시로, "
                 "무료로는 현재값만 가능해 매 실행마다 날짜별로 누적한다(시간이 지나면 포워드 라인도 그림)."),
        "current_fwd_pe": {"this": fwd_this, "next": fwd_next, "asof": today},
        "trailing_pe": trailing,   # [{date, value}] 최신→과거
        "cape": cape,
        "fwd_pe_snapshots": snaps,  # {date: {this, next}}
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"=== 완료 → {OUT} (후행 {len(trailing)}·포워드 스냅샷 {len(snaps)}) ===")

if __name__ == "__main__":
    main()
