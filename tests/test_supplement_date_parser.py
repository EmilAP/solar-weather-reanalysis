from __future__ import annotations

import unittest
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from _utils import parse_supplement_date_range


class SupplementDateParserTests(unittest.TestCase):
    def test_day_first_same_month_range(self) -> None:
        self.assertEqual(
            parse_supplement_date_range("29-30 Apr 1963"),
            (pd.Timestamp("1963-04-29"), pd.Timestamp("1963-04-30")),
        )

    def test_month_first_same_month_range(self) -> None:
        self.assertEqual(
            parse_supplement_date_range("Sep. 20-23, 1967"),
            (pd.Timestamp("1967-09-20"), pd.Timestamp("1967-09-23")),
        )

    def test_cross_month_range(self) -> None:
        self.assertEqual(
            parse_supplement_date_range("31 May – 1 Jun 1971"),
            (pd.Timestamp("1971-05-31"), pd.Timestamp("1971-06-01")),
        )

    def test_cross_year_range(self) -> None:
        self.assertEqual(
            parse_supplement_date_range("31 Dec-1 Jan 1971"),
            (pd.Timestamp("1970-12-31"), pd.Timestamp("1971-01-01")),
        )

    def test_single_date_and_iso_date(self) -> None:
        expected = (pd.Timestamp("1964-04-23"), pd.Timestamp("1964-04-23"))
        self.assertEqual(parse_supplement_date_range("Apr 23 1964"), expected)
        self.assertEqual(parse_supplement_date_range("1964-04-23"), expected)

    def test_invalid_date_is_left_unresolved(self) -> None:
        start, end = parse_supplement_date_range("31-32 Feb 1967")
        self.assertTrue(pd.isna(start))
        self.assertTrue(pd.isna(end))


if __name__ == "__main__":
    unittest.main()