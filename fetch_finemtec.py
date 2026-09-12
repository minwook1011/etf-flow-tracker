#!/usr/bin/env python3
"""Refresh Fine M-Tec prices and reported financials; retain successful history.

Only public observations are written. Customs series remain unconnected until a
licensed, verified transaction feed is configured. Standard library only.
"""
import calendar
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET
from data_writer import write_changed

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "data" / "finemtec.json"
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; VantageFinancialData/1.0)"
PRICE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/441270.KQ?range=5y&interval=1d"
NAVER_CHART = "https://fchart.stock.naver.com/sise.nhn?symbol=441270&timeframe=day&count=1500&requestType=0"
FINANCE_URL = "https://m.stock.naver.com/api/stock/441270/finance/"


def read_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://m.stock.naver.com/"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()


def number(raw):
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = float(str(raw).replace(",", "").replace("%", "").strip())
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def fetch_prices():
    try:
        data = json.loads(read_url(PRICE_URL))["chart"]["result"][0]
        quotes = data["indicators"]["quote"][0]["close"]
        points = []
        for timestamp, close in zip(data["timestamp"], quotes):
            value = number(close)
            if value is not None and value > 0:
                points.append({"date": datetime.fromtimestamp(timestamp, KST).date().isoformat(), "value": round(value, 2)})
        if len(points) < 20:
            raise ValueError("insufficient price observations")
        return points, "Yahoo Finance", PRICE_URL
    except Exception:
        root = ET.fromstring(read_url(NAVER_CHART))
        points = []
        for item in root.iter("item"):
            fields = item.attrib.get("data", "").split("|")
            if len(fields) >= 5 and number(fields[4]) is not None and float(fields[4]) > 0:
                day = datetime.strptime(fields[0], "%Y%m%d").date().isoformat()
                points.append({"date": day, "value": float(fields[4])})
        if len(points) < 20:
            raise ValueError("insufficient price observations")
        return points, "Naver Finance", NAVER_CHART


def parse_financials(payload, period, observed_at):
    info = payload["financeInfo"]
    titles = info["trTitleList"]
    rows = {row["title"].strip(): row for row in info["rowList"]}
    output = []
    for title in titles:
        if title.get("isConsensus") != "N":
            continue
        key = title["key"]
        if len(key) != 6 or not key.isdigit():
            continue
        year, month = int(key[:4]), int(key[4:])
        day = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}"
        record = {"date": day, "observed_at": observed_at, "reported_at": None,
                  "source_url": FINANCE_URL + period, "source": "Naver Finance / FnGuide",
                  "unit": "억원", "basis": "연결", "is_estimate": False}
        for field, label in (("revenue", "매출액"), ("operating_income", "영업이익")):
            cell = rows.get(label, {}).get("columns", {}).get(key, {})
            record[field] = number(cell.get("value"))
        if record["revenue"] is not None or record["operating_income"] is not None:
            output.append(record)
    if not output:
        raise ValueError("no reported financial observations")
    return output


def profit_growth(current, previous):
    if current is None or previous is None:
        return None, "비교 자료 없음"
    if previous == 0:
        return None, "전년 0 · 비율 산출 불가"
    if previous < 0:
        return None, "흑자전환" if current > 0 else "손익분기" if current == 0 else "적자축소" if current > previous else "적자확대" if current < previous else "적자유지"
    if current < 0:
        return None, "적자전환"
    return round((current / previous - 1) * 100, 2), "전년 동기 대비"


def enrich(records, period):
    lookup = {row["date"][:7]: row for row in records}
    for row in records:
        revenue, profit = row.get("revenue"), row.get("operating_income")
        row["opm"] = round(profit / revenue * 100, 2) if profit is not None and revenue is not None and revenue > 0 else None
        year, month = map(int, row["date"][:7].split("-"))
        prior = lookup.get(f"{year - 1}-{month:02d}", {})
        # The 2022 spin-off has a shortened fiscal period; it is not a full-year comparator.
        if period == "annual" and year == 2023:
            prior = {}
        previous_revenue = prior.get("revenue")
        row["revenue_yoy"] = round((revenue / previous_revenue - 1) * 100, 2) if revenue is not None and previous_revenue is not None and previous_revenue > 0 else None
        row["operating_income_yoy"], row["profit_growth_label"] = profit_growth(profit, prior.get("operating_income"))
    return records


def merge_records(old, new):
    merged = {row["date"]: row for row in old}
    for row in new:
        previous = merged.get(row["date"], {})
        row = {**row, "observed_at": previous.get("observed_at") or row.get("observed_at")}
        row["retained_fields"] = []
        for field in ("revenue", "operating_income"):
            if row.get(field) is None and previous.get(field) is not None:
                row[field] = previous[field]
                row["retained_fields"].append(field)
        # Preserve verified filing dates when a source lacks them.
        row["reported_at"] = previous.get("reported_at") or row.get("reported_at")
        merged[row["date"]] = row
    return [merged[day] for day in sorted(merged)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-if-changed", action="store_true")
    args = parser.parse_args()
    now = datetime.now(KST).isoformat(timespec="seconds")
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    data.update({"schema_version": 1, "company": {"name": "파인엠텍", "ticker": "441270", "yahoo_ticker": "441270.KQ", "currency": "KRW"}, "checked_at": now})
    errors = []
    try:
        points, provider, url = fetch_prices()
        intraday = points[-1]["date"] == now[:10] and datetime.now(KST).hour < 16
        data["price"] = {"points": points, "source": provider, "source_url": url, "fetched_at": now,
                         "status": "ready", "unit": "원", "basis": "KRX 일봉 · 당일 장중 값은 변동 가능", "is_intraday": intraday, "as_of": points[-1]["date"]}
    except Exception as error:
        errors.append("주가: " + type(error).__name__)
        data.setdefault("price", {"points": []})["status"] = "stale" if data.get("price", {}).get("points") else "unavailable"
    financials = data.setdefault("financials", {})
    for period in ("quarter", "annual"):
        key = "quarterly" if period == "quarter" else "annual"
        try:
            records = parse_financials(json.loads(read_url(FINANCE_URL + period)), period, now)
            financials[key] = enrich(merge_records(financials.get(key, []), records), period)
            retained = any(row.get("retained_fields") for row in financials[key])
            financials.setdefault("status", {})[key] = "stale" if retained else "ready"
            if retained:
                errors.append(key + ": 일부 항목 수신 실패 · 마지막 값 유지")
            financials.setdefault("fetched_at", {})[key] = now
        except Exception as error:
            errors.append(key + ": " + type(error).__name__)
            financials.setdefault("status", {})[key] = "stale" if financials.get(key) else "unavailable"
    data["refresh_errors"] = errors
    data.setdefault("trade", {"status": "not_connected", "records_count": 0, "series": {}, "as_of": None,
        "message": "베트남 거래별 원본 미연결 · FINE MS VINA → 삼성디스플레이의 품목별 거래와 수록 범위를 확인해야 합니다."})
    changed = write_changed(OUT, data, args.only_if_changed)
    print(json.dumps({"prices": len(data.get("price", {}).get("points", [])), "latest": data.get("price", {}).get("as_of"),
                      "quarterly": len(financials.get("quarterly", [])), "annual": len(financials.get("annual", [])), "changed": changed, "errors": errors}, ensure_ascii=False))
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
