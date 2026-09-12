"""Synthetic API fixtures only; no test values are published."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import fetch_memory_exports as exports
from data_writer import write_changed


class ExportTests(unittest.TestCase):
    def fixture(self, value="100", weight="2", code="8542321010"):
        return ("<response><header><resultCode>00</resultCode></header><body><items>"
                f"<item><year>2026.08</year><hsCode>{code}</hsCode><expDlr>{value}</expDlr><expWgt>{weight}</expWgt></item>"
                "<item><year>총계</year></item></items></body></response>").encode()

    def test_zero_and_missing_weight_are_different(self):
        rows=exports.parse_response(self.fixture("0",""),"8542321010","202608","202608")
        self.assertEqual(rows[0]["expDlr"],0)
        self.assertIsNone(rows[0]["expWgt"])

    def test_unexpected_code_and_invalid_value_rejected(self):
        for raw in (self.fixture(code="8542321030"),self.fixture(value="nan"),self.fixture(value="-1")):
            with self.assertRaises(ValueError):
                exports.parse_response(raw,"8542321010","202608","202608")

    def test_missing_key_not_empty_success(self):
        result=exports.build({},None,"202608","202608")
        self.assertTrue(all(s["status"]=="needs_api_key" and not s["points"] for s in result["series"]))
        self.assertTrue(all(s["source_updated_at"] is None for s in result["series"]))

    def test_failure_and_missing_value_preserve_history(self):
        with patch.object(exports,"retrieve",return_value=[{"period":"2026-08","expDlr":100,"expWgt":2}]):
            before=exports.build({},"fixture-key","202608","202608")
        with patch.object(exports,"retrieve",side_effect=ValueError("fixture-error")):
            after=exports.build(before,"fixture-key","202608","202608")
        self.assertTrue(all(s["status"]=="stale" for s in after["series"]))
        self.assertEqual(after["series"][0]["points"],before["series"][0]["points"])
        with patch.object(exports,"retrieve",return_value=[{"period":"2026-08","expDlr":110,"expWgt":None}]):
            partial=exports.build(before,"fixture-key","202608","202608")
        self.assertEqual(partial["series"][1]["points"][0]["value"],2)
        self.assertEqual(partial["series"][1]["status"],"stale")

    def test_unchanged_semantics_and_first_seen_preserved(self):
        with patch.object(exports,"retrieve",return_value=[{"period":"2026-08","expDlr":100,"expWgt":2}]):
            with patch.object(exports,"timestamp",return_value="2026-09-15T00:00:00Z"):
                before=exports.build({},"fixture-key","202608","202608")
            with patch.object(exports,"timestamp",return_value="2026-09-15T00:05:00Z"):
                after=exports.build(copy.deepcopy(before),"fixture-key","202608","202608")
        self.assertEqual(exports.stable_data(before),exports.stable_data(after))
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"fixture.json"
            self.assertTrue(write_changed(target,{"checked_at":"first","points":[{"value":1}]}))
            raw=target.read_bytes()
            self.assertFalse(write_changed(target,{"checked_at":"second","points":[{"value":1}]}))
            self.assertEqual(raw,target.read_bytes())


if __name__ == "__main__":
    unittest.main()
