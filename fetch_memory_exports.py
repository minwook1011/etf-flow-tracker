"""Collect Korean DRAM/flash exports from the official, free KCS API.

Requires an approved data.go.kr service key in KCS_API_KEY or
DATA_GO_KR_API_KEY. Never substitutes semiconductor totals for memory exports.
"""
from __future__ import annotations

import argparse
import calendar
import json
import math
import os
from pathlib import Path
import re
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "docs" / "data" / "memory_exports.json"
API_URL = "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
SOURCE_URL = "https://www.data.go.kr/data/15101609/openapi.do"
CLASSIFICATION_URL = "https://unipass.customs.go.kr/clip/hsinfosrch/openULS0201005Q.do?searchVal=854232"
KST = timezone(timedelta(hours=9))
PRODUCTS = (
    ("dram", "DRAM", "8542321010", "모노리식 DRAM 집적회로. DRAM 모듈 및 HBM 전체 출하를 뜻하지 않습니다."),
    ("flash", "플래시 메모리", "8542321030", "플래시 메모리 품목 전체로 NAND만 분리되지 않습니다. NAND 전용 출하량으로 해석하지 않습니다."),
)
METRICS = (
    ("value", "수출금액", "USD", "expDlr"),
    ("weight", "수출 순중량", "kg", "expWgt"),
)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def refresh_metadata() -> dict:
    return {
        "frequency": "monthly",
        "publish_times": [],
        "timezone": "Asia/Seoul",
        "publication_rule": "매월 15일경 전월까지의 자료 현행화; 정확한 발표 시각 미공시",
        "publication_day_approximate": 15,
        "evidence_url": SOURCE_URL,
        "polling_policy": {
            "kind": "application_policy_not_official_release_schedule",
            "release_window_days": [15, 16, 17, 18],
            "release_window_interval_minutes": 5,
            "outside_window_interval_minutes": 1440,
        },
        "note": "1·11·21일 총괄/주요품목 잠정치 발표와 이 HS10 월별 API의 갱신은 별개입니다.",
    }


def definitions() -> list[dict]:
    result = []
    for product, label, hs_code, coverage in PRODUCTS:
        for metric, metric_label, unit, _ in METRICS:
            result.append({
                "id": f"kr_{product}_export_{metric}",
                "label": f"한국 {label} {metric_label}",
                "unit": unit,
                "country": "KR",
                "category": "memory_exports",
                "frequency": "monthly",
                "hs_code": hs_code,
                "hs_classification_year": 2026,
                "classification_source_url": CLASSIFICATION_URL,
                "coverage": coverage,
                "source": "관세청 품목별 수출입실적(GW)",
                "source_url": SOURCE_URL,
                "source_updated_at": None,
                "source_time_note": "API에 원출처 갱신 시각 필드가 없어 확인 시각으로 대체하지 않습니다.",
                "source_latest_period": None,
                "refresh": refresh_metadata(),
                "status": "needs_api_key",
                "status_message": "무료 관세청 API 연결키 설정 대기",
                "points": [],
            })
    return result


def read_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("series", []), list):
        raise ValueError("Existing memory export data has an invalid schema; refusing to replace it.")
    return data


def month(value: str) -> str | None:
    match = re.fullmatch(r"\s*(\d{4})\D*(\d{1,2})\D*\s*", value or "")
    if not match:
        return None
    year, number = map(int, match.groups())
    return f"{year:04d}-{number:02d}" if 1900 <= year <= 2100 and 1 <= number <= 12 else None


def number(value: str | None) -> float | None:
    if value is None or not value.strip() or value.strip() in {"-", "..", "..."}:
        return None
    try:
        parsed = float(value.replace(",", "").strip())
    except ValueError as exc:
        raise ValueError("Unexpected nonnumeric customs observation") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError("Customs observation must be finite and nonnegative")
    return parsed


def parse_response(raw: bytes, hs_code: str, start: str, end: str) -> list[dict]:
    root = ET.fromstring(raw)
    # Gateway errors may be OpenAPI_ServiceResponse, not the documented response.
    error_code = root.findtext(".//returnReasonCode")
    result_code = root.findtext(".//resultCode")
    if error_code or result_code not in {"00", "000", "0"}:
        # Never log request URLs or response bodies: they can contain the service key.
        safe_code = re.sub(r"[^A-Za-z0-9_-]", "", error_code or result_code or "unknown")[:40]
        raise ValueError(f"Customs API returned an error ({safe_code})")
    observed = {}
    for item in root.findall(".//items/item"):
        period = month(item.findtext("year", ""))
        if period is None:  # Skip the API's aggregate total row.
            continue
        compact = period.replace("-", "")
        if not start <= compact <= end:
            raise ValueError("Customs response includes an unexpected period")
        returned_code = item.findtext("hsCode", "").strip()
        if returned_code != hs_code:
            raise ValueError("Customs response does not match the requested HS10 code")
        row = {"period": period}
        for _, _, _, field in METRICS:
            row[field] = number(item.findtext(field))
        if period in observed and observed[period] != row:
            raise ValueError("Conflicting duplicate customs observations")
        observed[period] = row
    return [observed[key] for key in sorted(observed)]


def retrieve(service_key: str, hs_code: str, start: str, end: str) -> list[dict]:
    query = urlencode({"serviceKey": unquote(service_key), "strtYymm": start, "endYymm": end, "hsSgn": hs_code})
    request = Request(API_URL + "?" + query, headers={"Accept": "application/xml", "User-Agent": "Vantage-MemoryExports/1.0"})
    with urlopen(request, timeout=35) as response:
        return parse_response(response.read(), hs_code, start, end)


def year_windows(start: str, end: str):
    for year in range(int(start[:4]), int(end[:4]) + 1):
        yield max(start, f"{year}01"), min(end, f"{year}12")


def build(previous: dict, service_key: str | None, start: str, end: str) -> dict:
    now = timestamp()
    old = {item["id"]: item for item in previous.get("series", []) if isinstance(item, dict) and "id" in item}
    series = definitions()
    by_id = {item["id"]: item for item in series}
    for item in series:
        prior = old.get(item["id"], {})
        item["points"] = prior.get("points", [])
        item["source_latest_period"] = prior.get("source_latest_period")
        item["last_successful_fetch_at"] = prior.get("last_successful_fetch_at")
        item["checked_at"] = now
        if item["points"]:
            item["status"] = "stale"
            item["status_message"] = "기존 관측값 보존 · 무료 관세청 API 연결키 설정 대기"
    if service_key:
        for product, _, hs_code, _ in PRODUCTS:
            try:
                rows = []
                for window_start, window_end in year_windows(start, end):
                    rows.extend(retrieve(service_key, hs_code, window_start, window_end))
                if not rows:
                    raise ValueError("No monthly observations were returned")
                for metric, _, _, field in METRICS:
                    item = by_id[f"kr_{product}_export_{metric}"]
                    points = {point["date"]: point for point in item["points"]}
                    received_values = 0
                    for row in rows:
                        if row[field] is None:
                            continue
                        received_values += 1
                        year, mon = map(int, row["period"].split("-"))
                        period_end = date(year, mon, calendar.monthrange(year, mon)[1]).isoformat()
                        point = {"date": period_end, "period": row["period"], "value": row[field], "first_seen_at": points.get(period_end, {}).get("first_seen_at", now)}
                        if period_end in points and points[period_end].get("value") != row[field]:
                            point["revised_at"] = now
                        elif points.get(period_end, {}).get("revised_at"):
                            point["revised_at"] = points[period_end]["revised_at"]
                        points[period_end] = point
                    item["points"] = [points[key] for key in sorted(points)]
                    item["status"] = "ok" if received_values else ("stale" if item["points"] else "unavailable")
                    item["status_message"] = "관세청 월별 관측값" if received_values else "요청 기간 수치 미제공"
                    item["source_latest_period"] = item["points"][-1]["period"] if item["points"] else None
                    if received_values:
                        item["last_successful_fetch_at"] = now
            except (HTTPError, URLError, TimeoutError, ET.ParseError, ValueError) as exc:
                safe_error = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                for metric, _, _, _ in METRICS:
                    item = by_id[f"kr_{product}_export_{metric}"]
                    item["status"] = "stale" if item["points"] else "unavailable"
                    item["status_message"] = "수집 실패 · 기존 관측값 보존" if item["points"] else "수집 연결 확인 필요"
                    item["last_error"] = safe_error
    return {
        "schema_version": 1,
        "checked_at": now,
        "series": series,
        "notes": [
            "물량은 순중량(kg)입니다. 칩 개수·비트 출하량·DRAM 모듈 출하량이 아닙니다.",
            "HS8542321030은 플래시 메모리 전체이며 NAND 전용 통계가 아닙니다.",
            "국가 전체 수출 통계로 개별 기업의 납품 또는 실적으로 확정하지 않습니다.",
            "전월 관측값은 매월 15일경 현행화되며 정정될 수 있습니다. 발표 시각은 공식 미공시입니다.",
            "금액/순중량은 제품 구성과 패키지 변화에 영향을 받으므로 메모리 칩의 거래 단가와 동일하지 않습니다.",
        ],
    }


def stable_data(value):
    """Exclude polling timestamps so unchanged observations do not trigger commits."""
    if isinstance(value, dict):
        return {key: stable_data(item) for key, item in value.items() if key not in {"checked_at", "last_successful_fetch_at"}}
    if isinstance(value, list):
        return [stable_data(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--start", help="First month YYYYMM (overrides --history-months)")
    parser.add_argument("--end", help="Last month YYYYMM (default: previous month)")
    parser.add_argument("--history-months", type=int, default=60, help="Initial/daily revision lookback, default 60 months")
    parser.add_argument("--recent-only", action="store_true", help="With existing observations, request only the latest completed month")
    parser.add_argument("--only-if-changed", action="store_true", help="Keep the JSON byte-for-byte when values/status/metadata have not changed")
    args = parser.parse_args()
    today = datetime.now(KST).date()
    last_month = date(today.year, today.month, 1) - timedelta(days=1)
    if not 1 <= args.history_months <= 240:
        parser.error("--history-months must be between 1 and 240")
    first_index = last_month.year * 12 + last_month.month - args.history_months
    start = args.start or f"{first_index // 12:04d}{first_index % 12 + 1:02d}"
    end = args.end or last_month.strftime("%Y%m")
    if not re.fullmatch(r"\d{6}", start) or not re.fullmatch(r"\d{6}", end) or not month(start) or not month(end) or start > end:
        parser.error("--start and --end must be valid YYYYMM values, with start <= end")
    key = os.environ.get("KCS_API_KEY") or os.environ.get("DATA_GO_KR_API_KEY")
    previous = read_existing(args.output)
    if args.recent_only and not args.start and previous.get("series") and all(item.get("points") for item in previous["series"]):
        start = end
    payload = build(previous, key, start, end)
    if not args.only_if_changed or stable_data(previous) != stable_data(payload):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_suffix(args.output.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(args.output)
    counts = {item["id"]: {"status": item["status"], "points": len(item["points"])} for item in payload["series"]}
    print(json.dumps(counts, ensure_ascii=False))
    return 1 if key and any(item["status"] != "ok" for item in payload["series"]) else 0


if __name__ == "__main__":
    sys.exit(main())
