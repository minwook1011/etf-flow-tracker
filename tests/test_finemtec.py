import copy
import io
import unittest
from unittest.mock import patch

from fetch_finemtec import enrich, load_history, main, merge_records, parse_financials, profit_growth, supplement_history
from ingest_finemtec_trade import aggregate


class FinancialTests(unittest.TestCase):
    def test_consensus_excluded_and_zero_preserved(self):
        payload = {"financeInfo": {"trTitleList": [
            {"isConsensus": "N", "key": "202606"}, {"isConsensus": "Y", "key": "202609"}],
            "rowList": [{"title": "매출액", "columns": {"202606": {"value": "1,234"}, "202609": {"value": "9999"}}},
                        {"title": "영업이익", "columns": {"202606": {"value": "0"}}}]}}
        rows = parse_financials(payload, "quarter", "2026-09-12")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["revenue"], 1234)
        self.assertEqual(rows[0]["operating_income"], 0)

    def test_yoy_uses_calendar_not_four_rows_back(self):
        rows = [{"date": "2024-06-30", "revenue": 50, "operating_income": -2},
                {"date": "2025-06-30", "revenue": 100, "operating_income": 5},
                {"date": "2026-03-31", "revenue": 60, "operating_income": -1},
                {"date": "2026-06-30", "revenue": 120, "operating_income": 6}]
        result = enrich(rows, "quarter")
        self.assertEqual(result[-1]["revenue_yoy"], 20)
        self.assertEqual(result[-1]["opm"], 5)
        self.assertIsNone(result[-2]["revenue_yoy"])
        self.assertEqual(result[1]["profit_growth_label"], "흑자전환")

    def test_negative_profit_is_not_misleading_growth(self):
        self.assertEqual(profit_growth(2, -4), (None, "흑자전환"))
        self.assertEqual(profit_growth(-2, -4), (None, "적자축소"))
        self.assertEqual(profit_growth(-8, -4), (None, "적자확대"))
        self.assertEqual(profit_growth(-1, 4), (None, "적자전환"))

    def test_archive_and_original_observation_retained(self):
        before = [{"date": "2025-03-31", "revenue": 90}, {"date": "2025-06-30", "revenue": 100, "observed_at": "first", "reported_at": "2025-08-14"}]
        after = [{"date": "2025-06-30", "revenue": 101, "observed_at": "later", "reported_at": None}]
        result = merge_records(before, after)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[-1]["observed_at"], "first")
        self.assertEqual(result[-1]["reported_at"], "2025-08-14")

    def test_partial_response_preserves_last_known_field(self):
        before = [{"date":"2026-06-30", "revenue":100, "operating_income":10}]
        after = [{"date":"2026-06-30", "revenue":110, "operating_income":None}]
        row = merge_records(before, after)[0]
        self.assertEqual(row["operating_income"],10)
        self.assertEqual(row["retained_fields"],["operating_income"])

    def test_history_reconciles_quarters_to_annual_and_has_yoy_baseline(self):
        history = load_history()
        self.assertEqual(len(history["quarterly"]), 12)
        self.assertEqual(len(history["annual"]), 4)
        for year in ("2024", "2025"):
            annual = next(r for r in history["annual"] if r["date"].startswith(year))
            quarters = [r for r in history["quarterly"] if r["date"].startswith(year)]
            for field in ("revenue_krw", "operating_income_krw"):
                self.assertEqual(sum(r[field] for r in quarters), annual[field])
        rows = enrich(history["quarterly"], "quarter")
        first_visible = rows[-8]
        self.assertEqual(first_visible["date"], "2024-09-30")
        self.assertIsNotNone(first_visible["revenue_yoy"])
        annual = enrich(history["annual"], "annual")
        self.assertIsNone(annual[1]["revenue_yoy"])
        self.assertIn("4개월", annual[0]["period_note"])

    def test_rounded_provider_does_not_destroy_filing_precision(self):
        before = load_history()["quarterly"]
        live = {"date":"2026-06-30", "revenue":952, "operating_income":73,
                "source":"Naver Finance / FnGuide", "source_url":"https://example.org"}
        row = merge_records(before, [live])[-1]
        self.assertEqual(row["source"], "DART 공시")
        self.assertEqual(row["operating_income"], 73.30620602)
        corrected = merge_records(before, [{**live, "revenue":980}])
        self.assertEqual(corrected[-1]["revenue"], 980)
        self.assertEqual(corrected[-1]["source"], "Naver Finance / FnGuide")
        self.assertNotIn("revenue_krw", corrected[-1])
        reapplied = merge_records(load_history()["quarterly"], corrected)
        self.assertEqual(reapplied[-1]["revenue"], 980, "seed must not undo a material revision")

    def test_history_survives_live_failure_without_claiming_freshness(self):
        with patch("fetch_finemtec.OUT") as out, patch("fetch_finemtec.fetch_prices", side_effect=OSError), patch("fetch_finemtec.read_url", side_effect=OSError), patch("fetch_finemtec.write_changed") as write, patch("sys.argv", ["fetch_finemtec.py"]), patch("sys.stdout", new_callable=io.StringIO):
            out.exists.return_value = False
            write.return_value = False
            self.assertEqual(main(), 1)
            data = write.call_args.args[1]
            self.assertEqual(len(data["financials"]["quarterly"]), 12)
            self.assertEqual(data["financials"]["status"]["quarterly"], "stale")
            self.assertEqual(data["trade"]["status"], "not_connected")

    def test_seed_preserves_archive_first_observation_and_filing_date(self):
        archive = [{"date":"2026-06-30", "revenue":952, "operating_income":73,
                    "source":"Naver Finance / FnGuide", "observed_at":"2026-08-15", "reported_at":"2026-08-14"}]
        row = supplement_history(load_history()["quarterly"], archive)[-1]
        self.assertEqual(row["source"], "DART 공시")
        self.assertEqual(row["observed_at"], "2026-08-15")
        self.assertEqual(row["reported_at"], "2026-08-14")

    def test_mixed_refresh_keeps_per_field_provenance(self):
        new = {"date":"2026-06-30", "revenue":980, "operating_income":None,
               "source":"Naver Finance / FnGuide", "source_url":"https://example.org"}
        row = merge_records(load_history()["quarterly"], [new])[-1]
        self.assertEqual(row["operating_income"], 73.30620602)
        self.assertEqual(row["field_sources"]["operating_income"]["source"], "DART 공시")
        self.assertEqual(row["field_sources"]["revenue"]["source"], "Naver Finance / FnGuide")
        self.assertTrue(row["field_sources"]["operating_income"]["source_url"].startswith("https://dart.fss.or.kr/"))
        self.assertIn("혼합 자료", row["source"])


class TradeTests(unittest.TestCase):
    def setUp(self):
        # Entirely synthetic fixtures, never published as observations.
        self.rules = {"exporter_ids": ["fixture-exporter"], "buyer_ids": ["fixture-buyer"],
                      "verified_products": [{"exporter_id": "fixture-exporter", "code": "fixture-plate", "evidence_url": "https://example.org/evidence"}]}
        self.row = {"transaction_id": "fixture-1", "date": "2025-01-15", "exporter_id": "fixture-exporter",
                    "buyer_id": "fixture-buyer", "product_code": "fixture-plate", "transaction_type": "sale",
                    "is_intercompany": False, "currency": "USD", "value_usd": 100, "quantity": 10, "quantity_unit": "PCS", "net_weight_kg": 2}
        self.feed = {"schema_version": 1, "source": "synthetic test", "available_at": "2026-01-20T00:00:00Z",
                     "aggregate_publication_allowed": True, "coverage": {}, "records": [self.row]}

    def test_no_guessed_company_or_product(self):
        self.assertEqual(aggregate(self.feed, {"exporter_ids": ["fixture-exporter"], "buyer_ids": []})["status"], "needs_verification")

    def test_duplicate_removed_and_conflict_rejected(self):
        self.feed["records"].append(copy.deepcopy(self.row))
        result = aggregate(self.feed, self.rules)
        self.assertEqual(result["records_count"], 1)
        self.feed["records"][-1]["value_usd"] = 999
        with self.assertRaises(ValueError):
            aggregate(self.feed, self.rules)

    def test_missing_weight_is_not_zero_or_partial_total(self):
        self.feed["records"].append({**self.row, "transaction_id": "fixture-2", "net_weight_kg": None})
        result = aggregate(self.feed, self.rules)
        self.assertIsNone(result["series"]["trade_weight"][0]["value"])
        self.assertEqual(result["series"]["trade_quantity"][0]["value"], 20)

    def test_gap_null_and_complete_zero_only(self):
        self.feed["coverage"] = {"2025-03": "complete"}
        result = aggregate(self.feed, self.rules)
        self.assertEqual([p["value"] for p in result["series"]["trade_value"]], [100, None, 0])

    def test_yoy_only_with_complete_current_and_prior(self):
        self.feed["records"].append({**self.row, "transaction_id": "fixture-2", "date": "2026-01-15", "value_usd": 120})
        result = aggregate(self.feed, self.rules)
        self.assertIsNone(result["series"]["trade_value_yoy"][-1]["value"])
        self.feed["coverage"] = {"2025-01": "complete", "2026-01": "complete"}
        result = aggregate(self.feed, self.rules)
        self.assertEqual(result["series"]["trade_value_yoy"][-1]["value"], 20)

    def test_non_sales_and_wrong_currency_excluded(self):
        for overrides in [{"transaction_type": "return"}, {"is_intercompany": True}]:
            self.feed["records"] = [{**self.row, **overrides}]
            self.assertEqual(aggregate(self.feed, self.rules)["records_count"], 0)

    def test_missing_value_rejects_instead_of_false_complete_total(self):
        self.feed["coverage"] = {"2025-01": "complete"}
        self.feed["records"].append({**self.row, "transaction_id": "fixture-2", "value_usd": None})
        with self.assertRaises(ValueError):
            aggregate(self.feed, self.rules)

    def test_empty_but_verified_complete_month_is_zero(self):
        self.feed["records"] = []
        self.feed["coverage"] = {"2025-01": "complete"}
        self.assertEqual(aggregate(self.feed, self.rules)["series"]["trade_value"][0]["value"], 0)

    def test_asp_tracks_fixed_product(self):
        self.rules["verified_products"].append({"exporter_id": "fixture-exporter", "code": "fixture-other", "evidence_url": "https://example.org/evidence"})
        self.rules["asp_product"] = {"exporter_id": "fixture-exporter", "code": "fixture-plate"}
        self.feed["records"].append({**self.row, "transaction_id": "fixture-2", "date": "2025-02-15", "product_code": "fixture-other", "value_usd": 1000})
        result = aggregate(self.feed, self.rules)
        self.assertEqual([p["value"] for p in result["series"]["trade_asp"]], [10, None])


if __name__ == "__main__":
    unittest.main()
