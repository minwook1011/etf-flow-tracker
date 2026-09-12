#!/usr/bin/env python3
"""Validate a licensed, normalized Vietnam feed and publish monthly aggregates.

Provider-specific raw rows must first be mapped to the contract documented in
data_sources/README.md. This is not a claim of working ImportGenius/TRASS access.
No raw company transactions or credentials are copied to the public docs tree.
"""
import argparse
from data_writer import write_changed
from collections import defaultdict
from datetime import date, datetime, timezone
import calendar
import json
import math
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "data" / "finemtec.json"
RULES = ROOT / "data_sources" / "finemtec_trade_rules.json"


def numeric(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def aggregate(feed, rules):
    if feed.get("schema_version") != 1 or not isinstance(feed.get("records"), list):
        raise ValueError("invalid feed schema")
    if feed.get("aggregate_publication_allowed") is not True:
        raise ValueError("feed must explicitly allow publication of aggregates")
    if not isinstance(feed.get("source"), str) or not feed["source"].strip():
        raise ValueError("source required")
    if not feed.get("available_at"):
        raise ValueError("feed publication timestamp required")
    datetime.fromisoformat(feed["available_at"].replace("Z", "+00:00"))
    products = {(p["exporter_id"], p["code"]) for p in rules.get("verified_products", []) if p.get("evidence_url", "").startswith("https://")}
    exporters, buyers = set(rules.get("exporter_ids", [])), set(rules.get("buyer_ids", []))
    qualified, seen, rejected = [], {}, defaultdict(int)
    for row in feed["records"]:
        if not isinstance(row, dict) or not row.get("transaction_id"):
            raise ValueError("stable transaction_id required for every row")
        transaction_id = row["transaction_id"]
        if transaction_id in seen:
            if seen[transaction_id] != row:
                raise ValueError("conflicting duplicate transaction_id")
            rejected["duplicate"] += 1
            continue
        seen[transaction_id] = row
        if row.get("exporter_id") not in exporters or row.get("buyer_id") not in buyers:
            rejected["unverified_party"] += 1
            continue
        if (row.get("exporter_id"), row.get("product_code")) not in products:
            rejected["unverified_product"] += 1
            continue
        if row.get("transaction_type") != "sale" or row.get("is_intercompany") is not False:
            rejected["non_external_sale"] += 1
            continue
        date.fromisoformat(row["date"])
        if date.fromisoformat(row["date"]) > date.today():
            raise ValueError("future transaction date")
        if row.get("currency") != "USD" or not numeric(row.get("value_usd")):
            raise ValueError("verified sale has invalid or non-USD value; cannot publish complete aggregate")
        # No currency conversion or weights inferred from unlabelled numbers.
        qualified.append(row)
    series = {key: [] for key in ("trade_value", "trade_quantity", "trade_weight", "trade_asp", "trade_value_yoy", "trade_count")}
    coverage = feed.get("coverage", {})
    if not qualified and not (products and buyers and any(v == "complete" for v in coverage.values())):
        return {"status": "needs_verification", "records_count": 0, "series": series, "as_of": None,
                "source": feed["source"], "available_at": feed["available_at"], "rejected": dict(rejected),
                "message": "수취 법인·제품코드를 확인한 거래가 아직 없습니다. 규칙과 실제 원본을 대조해야 합니다."}
    groups = defaultdict(list)
    for row in qualified:
        groups[row["date"][:7]].append(row)
    months = sorted(set(groups) | set(coverage))
    first_year, first_month = map(int, months[0].split("-"))
    last_year, last_month = map(int, months[-1].split("-"))
    index, last = first_year * 12 + first_month - 1, last_year * 12 + last_month - 1
    if last-index > 240:
        raise ValueError("feed spans more than 20 years")
    while index <= last:
        year, offset = divmod(index, 12); month = offset + 1; key = f"{year}-{month:02d}"
        rows = groups.get(key, [])
        covered = coverage.get(key) == "complete"
        known = bool(rows) or covered
        all_qty = bool(rows) and all(numeric(r.get("quantity")) and r.get("quantity_unit") in ("PCS", "PCE", "NOS", "EA") for r in rows)
        all_weight = bool(rows) and all(numeric(r.get("net_weight_kg")) for r in rows)
        quantity = sum(r["quantity"] for r in rows) if all_qty else 0 if covered and not rows else None
        weight = sum(r["net_weight_kg"] for r in rows) if all_weight else 0 if covered and not rows else None
        value = sum(r["value_usd"] for r in rows) if known else None
        asp_product = rules.get("asp_product") or {}
        cohort = [r for r in rows if r["exporter_id"] == asp_product.get("exporter_id") and r["product_code"] == asp_product.get("code")]
        cohort_qty = sum(r["quantity"] for r in cohort) if cohort and all(numeric(r.get("quantity")) and r.get("quantity_unit") in ("PCS", "PCE", "NOS", "EA") for r in cohort) else None
        values = {"trade_value": value, "trade_quantity": quantity, "trade_weight": weight,
                  "trade_asp": sum(r["value_usd"] for r in cohort) / cohort_qty if cohort_qty else None,
                  "trade_count": len(rows) if known else None}
        day = f"{key}-{calendar.monthrange(year,month)[1]}"
        for metric, value in values.items():
            series[metric].append({"date": day, "value": round(value, 4) if value is not None else None,
                                   "coverage": "complete" if covered else "partial" if rows else "unknown"})
        index += 1
    previous = {p["date"][:7]: p for p in series["trade_value"]}
    for point in series["trade_value"]:
        before = previous.get(f"{int(point['date'][:4])-1}-{point['date'][5:7]}", {})
        yoy = ((point["value"] / before["value"] - 1) * 100) if point["coverage"] == "complete" and before.get("coverage") == "complete" and before.get("value", 0) and point["value"] is not None else None
        series["trade_value_yoy"].append({"date": point["date"], "value": round(yoy, 2) if yoy is not None else None, "coverage": point["coverage"]})
    return {"status": "ready", "records_count": len(qualified), "series": series, "as_of": max((r["date"] for r in qualified), default=series["trade_value"][-1]["date"]),
            "source": feed["source"], "available_at": feed["available_at"], "fetched_at": datetime.now(timezone.utc).isoformat(),
            "rejected": dict(rejected), "message": "법인·백플레이트 품목을 확인한 외부 납품의 월별 합계입니다. 일부 수록 월은 전체 납품량이 아니며, 원본 수록 범위가 확인된 달끼리만 YoY를 계산합니다."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    feed_url = os.environ.get("FINEMTEC_TRADE_FEED_URL")
    if not args.input and not feed_url:
        print("Trade feed not configured; existing observations retained.")
        return 0
    try:
        if args.input:
            feed = json.loads(args.input.read_text(encoding="utf-8-sig"))
        else:
            if urllib.parse.urlparse(feed_url).scheme != "https":
                raise ValueError("HTTPS feed required")
            headers = {"User-Agent": "VantageTradeData/1.0"}
            token = os.environ.get("FINEMTEC_TRADE_FEED_TOKEN")
            if token:
                headers["Authorization"] = "Bearer " + token
            with urllib.request.urlopen(urllib.request.Request(feed_url, headers=headers), timeout=30) as response:
                raw = response.read(20_000_001)
            if len(raw) > 20_000_000:
                raise ValueError("feed exceeds size limit")
            feed = json.loads(raw)
        result = aggregate(feed, json.loads(RULES.read_text(encoding="utf-8")))
        current = json.loads(OUT.read_text(encoding="utf-8"))
        if result["status"] != "ready" and current.get("trade", {}).get("records_count", 0):
            raise ValueError("replacement contains no verified transactions")
        current["trade"] = result
        write_changed(OUT, current)
        print("Trade status: " + result["status"] + "; verified rows: " + str(result["records_count"]))
        return 0 if result["status"] == "ready" else 1
    except Exception as error:
        # Do not echo HTTP exceptions: their URLs can contain private tokens.
        print("Trade update failed (" + type(error).__name__ + "); existing observations retained.")
        if OUT.exists():
            current = json.loads(OUT.read_text(encoding="utf-8"))
            if current.get("trade", {}).get("records_count", 0):
                current["trade"]["status"] = "stale"
                write_changed(OUT, current)
        return 1


if __name__ == "__main__":
    sys.exit(main())
