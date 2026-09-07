#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공개 투자자 포트폴리오 갱신 → docs/investor_portfolios.json.

13F는 미국 SEC에 분기마다 제출되는 공개 보유내역이다. 따라서 실시간 매매가
아니며, 가장 최근 제출본의 장부가치 비중만 보여준다. 캐시 우드 항목은 ARK의
공개 ARKK 상위 보유종목 페이지를 별도로 읽어 거래일마다 갱신한다.
"""
import json
import os
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html import unescape

try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "docs", "investor_portfolios.json")
KST = timezone(timedelta(hours=9))
UA = "etf-flow-tracker contact@example.com"
SEC = "https://www.sec.gov"

# 영향도 순. CIK는 각 운용사의 공개 EDGAR 제출자 번호다.
INVESTORS = [
    {"id": "buffett", "name": "워런 버핏", "firm": "버크셔 해서웨이", "cik": "0001067983", "rank": 1},
    {"id": "druckenmiller", "name": "스탠리 드러켄밀러", "firm": "Duquesne Family Office", "cik": "0001536411", "rank": 2},
    {"id": "dalio", "name": "레이 달리오", "firm": "Bridgewater Associates", "cik": "0001350694", "rank": 3},
    {"id": "ackman", "name": "빌 애크먼", "firm": "Pershing Square", "cik": "0001336528", "rank": 4},
    {"id": "burry", "name": "마이클 버리", "firm": "Scion Asset Management", "cik": "0001649339", "rank": 5},
]

_last = [0.0]

def get(url, timeout=30):
    """SEC 권고 속도를 지키며 공개 자료만 읽는다."""
    wait = _last[0] + 0.25 - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def text(node, key):
    for child in list(node):
        if child.tag.rsplit("}", 1)[-1] == key:
            return (child.text or "").strip()
    return ""

def latest_13f(cik):
    data = json.loads(get("https://data.sec.gov/submissions/CIK%s.json" % cik).decode("utf-8"))
    recent = data.get("filings", {}).get("recent", {})
    for i, form in enumerate(recent.get("form", [])):
        if form == "13F-HR":
            return {
                "accession": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "primary": recent.get("primaryDocument", [""])[i],
            }
    return None

def filing_files(cik, accession):
    path = accession.replace("-", "")
    url = "%s/Archives/edgar/data/%s/%s/index.json" % (SEC, str(int(cik)), path)
    data = json.loads(get(url).decode("utf-8"))
    return path, [x.get("name", "") for x in data.get("directory", {}).get("item", [])]

def parse_13f(cik, meta):
    path, files = filing_files(cik, meta["accession"])
    primary = meta.get("primary") or ""
    xml_files = [f for f in files if f.lower().endswith(".xml") and not f.lower().endswith("primary_doc.xml")]
    if not xml_files:
        raise RuntimeError("information table XML 없음")
    xml_name = max(xml_files, key=lambda f: len(f))
    root = ET.fromstring(get("%s/Archives/edgar/data/%s/%s/%s" % (SEC, str(int(cik)), path, xml_name)))
    rows = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "infoTable":
            continue
        issuer, cls = text(node, "nameOfIssuer"), text(node, "titleOfClass")
        try:
            value = float(text(node, "value").replace(",", ""))
        except ValueError:
            value = 0
        if issuer and value > 0:
            rows.append({"name": issuer.title(), "class": cls, "value_usd": value})
    # 같은 발행인이 여러 행으로 분할된 공시는 합산해 실제 상위 비중을 만든다.
    merged = {}
    for row in rows:
        key = row["name"] + "|" + row["class"]
        merged[key] = merged.get(key, 0) + row["value_usd"]
    total = sum(merged.values())
    holdings = sorted((
        {"name": key.split("|", 1)[0], "class": key.split("|", 1)[1], "value_usd": round(value),
         "weight": round(value / total * 100, 2) if total else 0}
        for key, value in merged.items()
    ), key=lambda x: x["value_usd"], reverse=True)[:10]
    primary_file = next((f for f in files if f.lower().endswith("primary_doc.xml")), primary)
    primary_xml = get("%s/Archives/edgar/data/%s/%s/%s" % (SEC, str(int(cik)), path, primary_file)).decode("utf-8", "ignore")
    report_m = re.search(r"<periodOfReport>([^<]+)</periodOfReport>", primary_xml, re.I)
    return {"holdings": holdings, "report_date": report_m.group(1).strip() if report_m else "", "filing_url": "%s/Archives/edgar/data/%s/%s/%s" % (SEC, str(int(cik)), path, primary), "total_value_usd": round(total)}

def clean_html(s):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", s))).strip()

def fetch_arkk():
    """ARK 공식 ARKK 페이지의 공개 상위 10 보유종목. 거래일 종가 기준 공개 자료."""
    url = "https://www.ark-funds.com/funds/arkk"
    html = get(url).decode("utf-8", "ignore")
    # 페이지의 별도 holdings API는 서버가 HTML 조각으로 반환한다.
    payload = {
        "Heading": "Top 10 Holdings", "PdfLinkText": "Full Holdings PDF", "CsvLinkText": "Full Holdings CSV",
        "Link": {"Style": "", "Href": "", "Aria": "", "Target": "", "Text": ""},
    }
    api = "https://www.ark-funds.com/api/fund/holdings/1004?fundHoldingData=" + urllib.parse.quote(json.dumps(payload, separators=(",", ":")))
    try:
        html = get(api).decode("utf-8", "ignore")
    except Exception:
        pass
    date_m = re.search(r"As of\s*(?:<[^>]+>\s*)*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", html, re.I)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
        cells = [clean_html(x) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.I | re.S)]
        if len(cells) < 4 or cells[0].lower() in ("ticker", ""):
            continue
        weight_m = re.search(r"(-?[0-9]+(?:\.[0-9]+)?)%", " ".join(cells[-2:]))
        if not weight_m:
            continue
        ticker = cells[0].strip()
        if len(ticker) > 12 or not re.match(r"^[A-Z0-9.\- ]+$", ticker):
            continue
        rows.append({"ticker": ticker, "name": cells[1].title(), "weight": float(weight_m.group(1))})
    rows = sorted(rows, key=lambda x: x["weight"], reverse=True)[:10]
    if not rows:
        raise RuntimeError("ARKK 보유종목 파싱 실패")
    return {
        "id": "cathie", "rank": 6, "name": "캐시 우드", "firm": "ARK Invest · ARKK", "source_type": "daily_etf",
        "as_of": date_m.group(1) if date_m else "", "filing_date": "", "holdings": rows,
        "source_url": url, "disclosure": "ARKK 공개 보유종목 · 거래일 마감 후 갱신",
    }

def main():
    print("=== 공개 투자자 포트폴리오 갱신 ===")
    items = []
    for inv in INVESTORS:
        try:
            meta = latest_13f(inv["cik"])
            if not meta:
                raise RuntimeError("13F 신고 없음")
            parsed = parse_13f(inv["cik"], meta)
            items.append({
                "id": inv["id"], "rank": inv["rank"], "name": inv["name"], "firm": inv["firm"],
                "source_type": "sec_13f", "as_of": parsed["report_date"], "filing_date": meta["filing_date"],
                "holdings": parsed["holdings"], "total_value_usd": parsed["total_value_usd"],
                "source_url": parsed["filing_url"], "disclosure": "SEC Form 13F · 분기 공시 기준 (실시간 매매 아님)",
            })
            print("  [ok]", inv["name"], len(parsed["holdings"]), "종목")
        except Exception as e:
            print("  [skip]", inv["name"], e)
    try:
        items.append(fetch_arkk())
        print("  [ok] 캐시 우드 ARKK")
    except Exception as e:
        print("  [skip] 캐시 우드", e)
    if not items:
        print("[경고] 전부 실패 — 기존 파일 유지")
        return
    payload = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "notice": "공시·공개 보유종목 기준이며 투자 조언이 아닙니다.",
        "investors": sorted(items, key=lambda x: x["rank"]),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print("=== 완료:", len(items), "명 →", OUT, "===")

if __name__ == "__main__":
    main()
