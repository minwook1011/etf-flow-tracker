# -*- coding: utf-8 -*-
"""S&P500 전 종목으로 earnings_calendar.json 유니버스 확장.
기존 megacap(글로벌 TOP300) 캘린더에 없는 S&P500 구성종목을 Yahoo에서 수집해 추가한다.
name/sector는 S&P500 구성종목 CSV(위키/데이터셋)에서 채운다. 표준 라이브러리만 사용."""
import os, sys, json, io, csv, urllib.request, urllib.parse
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import fetch_earnings_calendar as F  # get_crumb, fetch_one, merge_eps_history, enrich_eps_yoy, KST

OUT = os.path.join(BASE, "docs", "earnings_calendar.json")
CONST = os.path.join(BASE, "docs", "sp500_constituents.json")
CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

def load_constituents():
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=40).read().decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(raw)))
    m = {}
    for r in rows:
        tk = r["Symbol"].strip().replace(".", "-")  # BRK.B -> BRK-B (야후 표기)
        m[tk] = {"name": r["Security"].strip(), "sector": r["GICS Sector"].strip()}
    json.dump({"updated": datetime.now(F.KST).strftime("%Y-%m-%d"), "count": len(m), "map": m},
              open(CONST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return m

def main():
    const = load_constituents()
    print(f"S&P500 구성종목 {len(const)}곳 로드")
    existing = {}
    if os.path.exists(OUT):
        existing = json.load(open(OUT, encoding="utf-8")).get("calendar", {})
    missing = [tk for tk in const if tk not in existing]
    print(f"기존 캘린더 {len(existing)}곳 · 신규 수집 대상 {len(missing)}곳")

    cookie, crumb = F.get_crumb()
    if not crumb:
        print("[경고] 크럼 실패 — 종료"); sys.exit(0)

    out = dict(existing)  # 기존 유지
    got = 0
    for i, tk in enumerate(missing, 1):
        r = F.fetch_one(tk, cookie, crumb)
        if r is None:
            if i % 40 == 0: print(f"  {i}/{len(missing)} (확보 {got})")
            continue
        eps_hist = F.enrich_eps_yoy(F.merge_eps_history(None, r["eps_history_new"]))[-10:]
        snaps = {}
        if r["consensus_quarter_end"] and r["consensus_rev"] is not None:
            snaps[r["consensus_quarter_end"]] = r["consensus_rev"]
        out[tk] = {
            "name": const[tk]["name"],
            "sector": const[tk]["sector"],
            "next_earnings_date": r["next_earnings_date"],
            "is_estimate": r["is_estimate"],
            "consensus_eps": r["consensus_eps"],
            "consensus_rev": r["consensus_rev"],
            "eps_history": eps_hist,
            "rev_consensus_snapshots": snaps,
        }
        got += 1
        if i % 40 == 0: print(f"  {i}/{len(missing)} (확보 {got})")

    data = {"updated": datetime.now(F.KST).strftime("%Y-%m-%d %H:%M KST"),
            "count": len(out), "calendar": out}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"=== 완료: 신규 {got}곳 추가 · 총 {len(out)}곳 → earnings_calendar.json ===")

if __name__ == "__main__":
    main()
