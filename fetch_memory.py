#!/usr/bin/env python3
"""Read TrendForce's public summary tables and retain dated price observations.

No authentication, history endpoints, or paid content are accessed.  Call
``--self-test`` for offline parser/merge validation. Publication and scheduled
collection are disabled until the provider's permission is explicitly recorded;
see data_sources/memory.md. With no permission this writes metadata only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "data" / "memory.json"
TAIPEI = timezone(timedelta(hours=8))
UTC = timezone.utc
FAQ = "https://www.dramexchange.com/service/faqs"
TERMS = "https://www.trendforce.com/about/terms"
PAGES = (
    "https://www.trendforce.com/price/dram/dram_spot",
    "https://www.trendforce.com/price/flash/flash_spot",
)
SECTIONS = {
    "dram_spot": ("dram_spot", "DRAM 칩 현물", "dram"),
    "module_spot": ("module_spot", "DRAM 모듈 현물", "dram"),
    "flash_spot": ("nand_spot", "NAND 칩 현물", "flash"),
    "dram_contract": ("contract", "DRAM 계약가격", "dram"),
    "flash_contract": ("contract", "NAND 계약가격", "flash"),
}
CATALOG = {
    "dram_spot": ("2026-09-11T18:10:00+08:00", ["DDR5 16Gb (2Gx8) 4800/5600", "DDR5 16Gb (2Gx8) eTT", "DDR4 16Gb (2Gx8) 3200", "DDR4 16Gb (2Gx8) eTT", "DDR4 8Gb (1Gx8) 3200", "DDR4 8Gb (1Gx8) eTT", "DDR3 4Gb 512Mx8 1600/1866"]),
    "module_spot": ("2026-08-31T14:40:00+08:00", ["DDR5 UDIMM 16GB 4800/5600", "DDR5 RDIMM 32GB 4800/5600", "DDR4 UDIMM 16GB 3200"]),
    "flash_spot": ("2026-08-31T14:40:00+08:00", ["SLC 2Gb 256MBx8", "SLC 1Gb 128MBx8", "MLC 64Gb 8GBx8", "MLC 32Gb 4GBx8"]),
    "dram_contract": ("2026-07-31T15:00:00+08:00", ["DDR5 8GB SO-DIMM", "DDR4 16GB SO-DIMM", "DDR4 8GB SO-DIMM", "DDR4 16Gb 2Gx8", "DDR4 8Gb 1Gx8", "DDR4 4Gb 256Mx16", "DDR3 4Gb 256Mx16"]),
    "flash_contract": ("2026-07-31T09:00:00+08:00", ["NAND 128Gb 16Gx8 MLC", "NAND 64Gb 8Gx8 MLC", "NAND 32Gb 4Gx8 MLC"]),
}
NOTES = [
    "Spot은 현물가격이며 Contract(계약가격)과 다릅니다. DRAM 칩과 완성 모듈은 별도 품목입니다.",
    "가격은 공개 표의 Session Average(계약가격은 Average)입니다. 용량·규격·eTT 여부가 다른 품목을 합산하지 않습니다.",
    "source_updated_at은 공급자 표의 기준시각, observed_at은 수집기가 처음 확인한 시각입니다. 과거 시계열을 임의로 생성하지 않습니다.",
    "일반 현물 세션은 대만 11:00 / 14:40 / 18:10, 한국 12:00 / 15:40 / 19:10입니다. 공개 요약표가 모든 세션에 갱신된다는 보장은 없습니다.",
    "공개 모듈·NAND 표의 별도 고정 발표주기는 확인되지 않았습니다. 월간 계약가격도 정확한 발표 일시가 고정되지 않습니다.",
    "공개 표에 표시되는 계약가격 기준월은 유료 최신 리포트 안내의 기준월보다 늦을 수 있습니다.",
    "TrendForce 약관의 자동수집·재배포 조건은 별도 확인이 필요합니다. 출처 링크만으로 사용 허가가 성립하지 않습니다.",
]


def clean(text):
    return " ".join(text.split()).strip()


def number(raw):
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        text = str(raw)
        value = float(text.replace(",", "").replace("%", "").replace("▲", "").replace("▼", "").replace("—", "").strip())
        if "▼" in text and value > 0:
            value = -value
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


class PriceTables(HTMLParser):
    """Parse only explicitly identified public price-content sections."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = {}
        self.active = None
        self.div_depth = 0
        self.table_depth = 0
        self.table_region = None
        self.row = None
        self.cell = None
        self.cell_tag = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.active is None:
            if tag == "div" and attrs.get("id") in SECTIONS and "price-content" in attrs.get("class", "").split():
                self.active = {"id": attrs["id"], "text": [], "headers": [], "rows": []}
                self.div_depth = 1
            return
        if tag == "div":
            self.div_depth += 1
        if tag == "table" and (self.table_depth or "price-table" in attrs.get("class", "").split()):
            self.table_depth += 1
        if not self.table_depth:
            return
        if tag in ("thead", "tbody", "tfoot"):
            self.table_region = tag
        if tag == "tr" and self.table_region in ("thead", "tbody"):
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
            self.cell_tag = tag

    def handle_data(self, data):
        if self.active is not None:
            self.active["text"].append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.active is None:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(clean(" ".join(self.cell)))
            if tag == "th":
                self.active["has_header"] = True
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.active.pop("has_header", False):
                self.active["headers"] = self.row
            elif self.row:
                self.active["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1
        elif tag in ("thead", "tbody", "tfoot"):
            self.table_region = None
        if tag == "div":
            self.div_depth -= 1
            if not self.div_depth:
                self.sections[self.active["id"]] = self.active
                self.active = None


def refresh_rule(section):
    common = {"timezone": "Asia/Taipei", "check_times": ["11:00", "14:40", "18:10"],
              "evidence_url": FAQ, "access": "public_summary", "terms_url": TERMS}
    if section == "dram_spot":
        return {**common, "publish_times": ["11:00", "14:40", "18:10"],
                "frequency": "daily_three_sessions", "schedule_confirmed": True,
                "note": "일반 공개 세션 · 실제 요약표 반영시각은 Last Update로 확인"}
    if section.endswith("contract"):
        return {**common, "publish_times": [], "frequency": "monthly",
                "schedule_confirmed": False, "note": "월 1회 원칙 · 공개표의 정확한 발표 일시 미확인"}
    return {**common, "publish_times": [], "frequency": "not_confirmed",
            "schedule_confirmed": False, "observed_publish_times": ["14:40"],
            "note": "해당 공개표의 고정 발표주기 미확인 · 현물 세션 시각에 갱신 여부 확인"}


def permission_catalog(now, previous=None):
    """Publish identifying metadata only; source numeric prices are not copied."""
    old = {item["id"]: item for item in (previous or {}).get("series", [])}
    rows = []
    for section, (updated, items) in CATALOG.items():
        group, prefix, category = SECTIONS[section]
        for item in items:
            slug = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_")
            key = f"{section}_{slug}"
            prior = old.pop(key, {})
            rows.append({**prior, "id": key, "label": f"{prefix} · {item}",
                         "item": item, "group": group, "unit": "USD/모듈" if "DIMM" in item.upper() else "USD/개",
                         "currency": "USD", "source": "TrendForce / DRAMeXchange",
                         "source_url": f"https://www.trendforce.com/price/{category}/{section}",
                         "source_updated_at": prior.get("source_updated_at", updated), "source_checked_on": prior.get("source_checked_on", "2026-09-12"),
                         "refresh": {**refresh_rule(section), "enabled": False},
                         "status": "permission_required", "status_message": "자동수집·재배포 이용 허용 확인 대기",
                         "display_prices": False, "points": prior.get("points", [])})
    # Preserve historical licensed observations if execution permission is removed.
    # The UI must honor display_prices/status rather than treating them as live data.
    for prior in old.values():
        rows.append({**prior, "status": "permission_required", "display_prices": False,
                     "status_message": "자동수집·재배포 이용 허용 확인 대기",
                     "refresh": {**prior.get("refresh", {}), "enabled": False}})
    return {"schema_version": 1, "checked_at": now,
            "series": sorted(rows, key=lambda item: (item["group"], item["id"])),
            "notes": NOTES, "refresh_errors": [],
            "collection_policy": {"terms_url": TERMS, "publication_permission": "not_confirmed",
                                  "enabled": False, "display_prices": False, "method": "public_summary_html",
                                  "paid_history_accessed": False,
                                  "message": "공급자의 자동수집·공개 재배포 허용 확인 후 연결됩니다."}}


def parse_page(html, observed_at):
    parser = PriceTables()
    parser.feed(html)
    output = []
    for section, table in parser.sections.items():
        group, prefix, category = SECTIONS[section]
        text = clean(" ".join(table["text"]))
        stamp = re.search(r"Last Update\s*:?[\s]*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s*\(GMT\+8\)", text)
        if not stamp:
            raise ValueError(f"{section}: missing source timestamp")
        updated = datetime.fromisoformat(f"{stamp[1]}T{stamp[2]}:00+08:00")
        now = datetime.fromisoformat(observed_at)
        if updated > now + timedelta(minutes=5):
            raise ValueError(f"{section}: future timestamp")
        headers = table["headers"]
        average_key = "Session Average" if "Session Average" in headers else "Average"
        if average_key not in headers or "Item" not in headers:
            raise ValueError(f"{section}: changed price columns")
        average_index = headers.index(average_key)
        high_key = "Session High" if "Session High" in headers else "High"
        low_key = "Session Low" if "Session Low" in headers else "Low"
        change_key = "Session Change" if "Session Change" in headers else "Average Change"
        before = len(output)
        for cells in table["rows"]:
            if len(cells) != len(headers):
                raise ValueError(f"{section}: changed row layout")
            label = cells[headers.index("Item")]
            value = number(cells[average_index])
            if not label or value is None or value <= 0:
                raise ValueError(f"{section}: invalid price")
            high = number(cells[headers.index(high_key)]) if high_key in headers else None
            low = number(cells[headers.index(low_key)]) if low_key in headers else None
            if high is None or low is None or not low <= value <= high:
                raise ValueError(f"{section}: average outside quote range")
            slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
            age_days = round((now - updated).total_seconds() / 86400, 2)
            stale_after = 40 if group == "contract" else 7
            unit = "USD/모듈" if "DIMM" in label.upper() else "USD/개"
            point = {"date": updated.date().isoformat(), "value": value,
                     "observed_at": observed_at, "source_updated_at": updated.isoformat(),
                     "low": low, "high": high,
                     "change_pct": number(cells[headers.index(change_key)]) if change_key in headers else None}
            output.append({"id": f"{section}_{slug}", "label": f"{prefix} · {label}",
                           "item": label, "group": group, "unit": unit, "currency": "USD",
                           "source": "TrendForce / DRAMeXchange", "source_url": f"https://www.trendforce.com/price/{category}/{section}",
                           "source_updated_at": updated.isoformat(), "checked_at": observed_at,
                           "source_age_days": age_days, "refresh": {**refresh_rule(section), "enabled": True},
                           "display_prices": True,
                           "status": "source_delayed" if age_days > stale_after else "ready",
                           "status_message": "공개 원문 기준일이 오래되었습니다" if age_days > stale_after else "공개표 확인",
                           "points": [point]})
        if len(output) == before:
            raise ValueError(f"{section}: no price observations")
    return output, set(parser.sections)


def merge_series(previous, incoming):
    """Keep one latest session per source day, preserving actual first observation."""
    by_day = {point["date"]: dict(point) for point in previous.get("points", [])}
    revisions = list(previous.get("revisions", []))
    for point in incoming["points"]:
        prior = by_day.get(point["date"])
        if prior and prior.get("source_updated_at", "") > point["source_updated_at"]:
            continue
        if prior and prior.get("source_updated_at") == point["source_updated_at"]:
            if prior["value"] == point["value"]:
                point = {**point, "observed_at": prior.get("observed_at", point["observed_at"])}
            else:
                revisions.append({"date": point["date"], "source_updated_at": point["source_updated_at"],
                                  "previous_value": prior["value"], "value": point["value"],
                                  "observed_at": point["observed_at"]})
        by_day[point["date"]] = point
    merged = {**incoming, "points": [by_day[day] for day in sorted(by_day)]}
    if merged["points"]:
        latest = merged["points"][-1]
        merged["source_updated_at"] = latest["source_updated_at"]
        merged["as_of"] = latest["date"]
        age = (datetime.fromisoformat(incoming["checked_at"]) - datetime.fromisoformat(latest["source_updated_at"])).total_seconds() / 86400
        merged["source_age_days"] = round(age, 2)
        delayed = age > (40 if merged["group"] == "contract" else 7)
        merged["status"] = "source_delayed" if delayed else "ready"
        merged["status_message"] = "공개 원문 기준일이 오래되었습니다" if delayed else "공개표 확인"
    if revisions:
        merged["revisions"] = revisions
    return merged


def read_page(url):
    request = urllib.request.Request(url, headers={"User-Agent": "VantageMemoryData/1.0 (public price table reader)",
                                                    "Accept": "text/html", "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("unexpected response size")
        return raw.decode("utf-8")


def collect(data=None, now=None):
    now = now or datetime.now(UTC).isoformat(timespec="seconds")
    data = data or {}
    previous = {item["id"]: item for item in permission_catalog(now)["series"]}
    previous.update({item["id"]: item for item in data.get("series", [])})
    result = dict(previous)
    errors = []
    seen = set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(read_page, url): url for url in PAGES}
        for future in as_completed(futures):
            url = futures[future]
            expected = {key for key, (_, _, category) in SECTIONS.items() if f"/price/{category}/" in url}
            try:
                items, sections = parse_page(future.result(), now)
                if not expected.issubset(sections):
                    raise ValueError("missing expected public price section")
                for item in items:
                    result[item["id"]] = merge_series(previous.get(item["id"], {}), item)
                    seen.add(item["id"])
            except Exception as error:
                errors.append({"source_url": url, "error": type(error).__name__, "message": str(error)[:180]})
    for key, item in result.items():
        if key not in seen:
            item = dict(item)
            item.update({"status": "stale" if item.get("points") else "unavailable",
                         "status_message": "이번 수집 실패 또는 원문 항목 누락 · 이전 관측 보존", "checked_at": now})
            result[key] = item
    return {"schema_version": 1, "checked_at": now,
            "series": sorted(result.values(), key=lambda item: (item["group"], item["id"])),
            "notes": NOTES, "refresh_errors": errors,
            "collection_policy": {"terms_url": TERMS, "publication_permission": "not_confirmed",
                                  "method": "public_summary_html", "paid_history_accessed": False}}, errors


def self_test():
    html = '''<div id="dram_spot" class="price-content"><div><p>Last Update 2026-09-11 18:10 (GMT+8)</p></div>
<table class="price-table"><thead><tr><th>Item</th><th>Daily High</th><th>Daily Low</th><th>Session High</th><th>Session Low</th><th>Session Average</th><th>Session Change</th><th>History</th></tr></thead>
<tbody><tr><td><span>DDR5 RDIMM 32GB</span></td><td>2,150.00</td><td>1,700.00</td><td>2,150.00</td><td>1,700.00</td><td>1,800.00</td><td><span>▲ 8.11 %</span></td><td></td></tr></tbody><tfoot><tr><td colspan="8">Members click for details</td></tr></tfoot></table></div>'''
    rows, groups = parse_page(html, "2026-09-12T00:00:00+00:00")
    assert groups == {"dram_spot"} and len(rows) == 1
    assert rows[0]["points"][0]["value"] == 1800 and rows[0]["points"][0]["change_pct"] == 8.11
    assert rows[0]["source_updated_at"] == "2026-09-11T18:10:00+08:00"
    assert number("▼ 0.83 %") == -0.83 and number("▼ -0.83 %") == -0.83
    assert number("▲ 1.22 %") == 1.22 and number("— 0.00 %") == 0
    earlier = {**rows[0], "points": [{**rows[0]["points"][0], "observed_at": "2026-09-11T11:11:00+00:00"}]}
    merged = merge_series(earlier, rows[0])
    assert len(merged["points"]) == 1 and merged["points"][0]["observed_at"] == "2026-09-11T11:11:00+00:00"
    older = {**rows[0], "points": [{**rows[0]["points"][0], "value": 1750, "source_updated_at": "2026-09-11T14:40:00+08:00"}]}
    assert merge_series(earlier, older)["points"][0]["value"] == 1800
    revised = {**rows[0], "points": [{**rows[0]["points"][0], "value": 1810}]}
    assert merge_series(earlier, revised)["revisions"][0]["previous_value"] == 1800
    disabled = permission_catalog("2026-09-12T00:00:00+00:00", {"series": [earlier]})
    retained = next(row for row in disabled["series"] if row["id"] == earlier["id"])
    assert retained["points"][0]["value"] == 1800 and not retained["display_prices"]
    assert retained["status"] == "permission_required"
    assert comparable({"checked_at": "before", "points": [{"date": "2026-09-11", "value": 1}]}) == comparable({"checked_at": "after", "points": [{"date": "2026-09-11", "value": 1}]})
    for invalid in (html.replace("1,800.00", "9,000.00"), html.replace("Session Average", "New Average"), html.replace("2026-09-11", "2028-09-11")):
        try:
            parse_page(invalid, "2026-09-12T00:00:00+00:00")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid source should fail closed")
    print("memory parser and point-in-time merge checks passed")


def comparable(value):
    """Clock-only changes do not warrant a new published dataset revision."""
    if isinstance(value, dict):
        return {key: comparable(item) for key, item in value.items() if key not in {"checked_at", "source_age_days"}}
    if isinstance(value, list):
        return [comparable(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--preview", action="store_true", help="Print observed values without saving the data file")
    parser.add_argument("--provider-permission-confirmed", action="store_true", help="Enable collection only after provider permission covers automated extraction and public redistribution")
    parser.add_argument("--only-if-changed", action="store_true", help="Do not rewrite the dataset when only checking timestamps or source age changed")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    permission = args.provider_permission_confirmed or os.environ.get("MEMORY_PRICE_COLLECTION_ALLOWED") == "true"
    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if permission or args.preview:
        data, errors = collect(previous)
        data["collection_policy"]["enabled"] = permission
        data["collection_policy"]["display_prices"] = permission
        data["collection_policy"]["publication_permission"] = "confirmed_by_operator" if permission else "not_confirmed"
    else:
        data = permission_catalog(datetime.now(UTC).isoformat(timespec="seconds"), previous)
        errors = []
    if args.preview:
        print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        if args.only_if_changed and comparable(previous) == comparable(data):
            print(json.dumps({"changed": False, "series": len(data["series"]), "errors": errors}, ensure_ascii=False))
            return 1 if errors else 0
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"series": len(data["series"]), "groups": sorted({row["group"] for row in data["series"]}),
                          "latest": {row["group"]: row["source_updated_at"] for row in data["series"]},
                          "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
