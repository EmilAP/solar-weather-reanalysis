from __future__ import annotations

import sys
import unittest
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from _utils import (
    holm_adjust_pvalues,
    nearest_event_differences,
    season_matched_random_sampler,
    within_days_indicator,
    year_month_cluster_shift_dates,
    year_month_matched_dates,
    year_season_cluster_shift_sampler,
)

SUMMARY_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "45_author_outbreak_branch_summary.py"
SUMMARY_SPEC = importlib.util.spec_from_file_location("author_outbreak_branch_summary", SUMMARY_SCRIPT)
SUMMARY_MODULE = importlib.util.module_from_spec(SUMMARY_SPEC)
SUMMARY_SPEC.loader.exec_module(SUMMARY_MODULE)
STRICT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "19_run_stricter_event_study.py"
STRICT_SPEC = importlib.util.spec_from_file_location("strict_event_study", STRICT_SCRIPT)
STRICT_MODULE = importlib.util.module_from_spec(STRICT_SPEC)
STRICT_SPEC.loader.exec_module(STRICT_MODULE)
DISTANCE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "43_author_outbreak_event_distance_test.py"
DISTANCE_SPEC = importlib.util.spec_from_file_location("outbreak_distance_test", DISTANCE_SCRIPT)
DISTANCE_MODULE = importlib.util.module_from_spec(DISTANCE_SPEC)
DISTANCE_SPEC.loader.exec_module(DISTANCE_MODULE)
COINCIDENCE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "44_author_outbreak_event_coincidence_test.py"
COINCIDENCE_SPEC = importlib.util.spec_from_file_location("outbreak_coincidence_test", COINCIDENCE_SCRIPT)
COINCIDENCE_MODULE = importlib.util.module_from_spec(COINCIDENCE_SPEC)
COINCIDENCE_SPEC.loader.exec_module(COINCIDENCE_MODULE)


class YearMonthMatchedDateTests(unittest.TestCase):
    def test_samples_preserve_each_year_and_month(self) -> None:
        observed = pd.to_datetime(["2020-04-04", "2020-04-10", "2021-11-05"])
        valid = pd.date_range("2020-01-01", "2021-12-31", freq="D")

        sampled = year_month_matched_dates(observed, valid, np.random.default_rng(42))

        self.assertEqual(list(zip(sampled.dt.year, sampled.dt.month)), [(2020, 4), (2020, 4), (2021, 11)])
        self.assertEqual(sampled.iloc[:2].nunique(), 2)

    def test_missing_year_month_stratum_fails_loudly(self) -> None:
        with self.assertRaisesRegex(ValueError, "2021, 11"):
            year_month_matched_dates(
                pd.to_datetime(["2021-11-05"]),
                pd.to_datetime(["2020-11-05"]),
                np.random.default_rng(42),
            )

    def test_cluster_shift_preserves_strata_counts_and_cyclic_gaps(self) -> None:
        observed = pd.to_datetime(["2020-04-04", "2020-04-10", "2020-04-11", "2021-11-05"])
        valid = pd.date_range("2020-01-01", "2021-12-31", freq="D")

        sampled = year_month_cluster_shift_dates(observed, valid, np.random.default_rng(42))

        self.assertEqual(list(zip(sampled.dt.year, sampled.dt.month)), [(2020, 4), (2020, 4), (2020, 4), (2021, 11)])
        observed_days = sorted(observed[:3].day)
        sampled_days = sorted(sampled.iloc[:3].dt.day)
        observed_gaps = sorted(np.diff(observed_days).tolist() + [30 - observed_days[-1] + observed_days[0]])
        sampled_gaps = sorted(np.diff(sampled_days).tolist() + [30 - sampled_days[-1] + sampled_days[0]])
        self.assertEqual(sampled_gaps, observed_gaps)


class SeasonMatchedSamplerTests(unittest.TestCase):
    def test_precomputed_pools_preserve_year_and_day_of_year_tolerance(self) -> None:
        observed = pd.to_datetime(["2020-04-04", "2020-10-10", "2021-11-05"])
        available = pd.date_range("2020-01-01", "2021-12-31", freq="D")
        sampler = season_matched_random_sampler(observed, available, 15)

        sampled = sampler(np.random.default_rng(42))

        self.assertEqual([date.year for date in sampled], [2020, 2020, 2021])
        for event, date in zip(observed, sampled, strict=True):
            self.assertLessEqual(abs(event.dayofyear - date.dayofyear), 15)

    def test_year_shift_preserves_cross_month_cluster_spacing(self) -> None:
        observed = pd.to_datetime(["2020-01-30", "2020-02-01", "2020-02-03", "2021-11-05"])
        available = pd.date_range("2020-01-01", "2021-12-31", freq="D")
        sampler = year_season_cluster_shift_sampler(observed, available, 15)

        sampled = sampler(np.random.default_rng(42))

        self.assertEqual(list(sampled.dt.year), [2020, 2020, 2020, 2021])
        self.assertEqual((sampled.iloc[1] - sampled.iloc[0]).days, 2)
        self.assertEqual((sampled.iloc[2] - sampled.iloc[1]).days, 2)
        self.assertLessEqual(abs(sampled.iloc[0].dayofyear - observed[0].dayofyear), 15)


class TimezoneIndicatorTests(unittest.TestCase):
    def test_timezone_aware_events_match_naive_daily_index(self) -> None:
        index_dates = pd.Series(pd.date_range("2000-01-01", periods=4, freq="D"))
        event_dates = [pd.Timestamp("2000-01-02T18:00:00Z")]

        result = within_days_indicator(index_dates, event_dates, 1)

        self.assertEqual(result.tolist(), [1, 1, 1, 0])

    def test_nearest_event_differences_accept_timezone_aware_inputs(self) -> None:
        left = [pd.Timestamp("2000-01-02T18:00:00Z")]
        right = [pd.Timestamp("2000-01-01"), pd.Timestamp("2000-01-04T00:00:00Z")]

        result = nearest_event_differences(left, right)

        self.assertEqual(result.loc[0, "delta_days"], 1.25)


class FastEventWindowTests(unittest.TestCase):
    def test_timezone_aware_events_match_naive_daily_dates(self) -> None:
        daily = pd.DataFrame(
            {
                "date": pd.date_range("2000-01-01", periods=5, freq="D"),
                "count": [0.0, 1.0, 2.0, 3.0, 4.0],
            }
        )
        events = [pd.Timestamp("2000-01-03T00:00:00Z")]

        result = STRICT_MODULE.build_event_window_fast(daily, events, ["count"], 1)

        self.assertEqual(result["event_count"].tolist(), [1, 1, 1])
        self.assertEqual(result["count"].tolist(), [1.0, 2.0, 3.0])

    def test_edge_dates_are_excluded_at_every_lag(self) -> None:
        daily = pd.DataFrame(
            {
                "date": pd.date_range("2000-01-01", periods=5, freq="D"),
                "count": [0.0, 1.0, 2.0, 3.0, 4.0],
            }
        )
        events = [pd.Timestamp("2000-01-01"), pd.Timestamp("2000-01-03")]

        result = STRICT_MODULE.build_event_window_fast(daily, events, ["count"], 1)

        self.assertEqual(result["event_count"].tolist(), [1, 1, 1])
        self.assertEqual(result["count"].tolist(), [1.0, 2.0, 3.0])


class NearestDistanceTests(unittest.TestCase):
    def test_vectorized_distance_matches_expected_nearest_days(self) -> None:
        dates = pd.Series(pd.to_datetime(["2000-01-02", "2000-01-10", "2000-01-04"]))
        events = pd.Series(pd.to_datetime(["2000-01-01", "2000-01-04"]))

        result = DISTANCE_MODULE.compute_abs_distances(dates, events)

        np.testing.assert_array_equal(result, [1.0, 6.0, 0.0])


class CoincidenceWindowTests(unittest.TestCase):
    def test_inclusive_windows_count_each_anchor_once(self) -> None:
        anchors = pd.Series(pd.to_datetime(["2000-01-01", "2000-01-02", "2000-01-10", "2000-01-10"]))
        events = pd.Series(pd.to_datetime(["2000-01-02", "2000-01-10"]))

        self.assertEqual(COINCIDENCE_MODULE.count_with_window(anchors, events, -1, 1), 4)
        self.assertEqual(COINCIDENCE_MODULE.count_with_window(anchors, events, 1, 1), 1)


class HolmAdjustmentTests(unittest.TestCase):
    def test_adjustment_is_monotone_and_preserves_input_order(self) -> None:
        adjusted = holm_adjust_pvalues([0.01, 0.04, 0.03])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06])

    def test_adjustment_ignores_nan_and_caps_at_one(self) -> None:
        adjusted = holm_adjust_pvalues([0.02, np.nan, 0.8])
        np.testing.assert_allclose(adjusted[[0, 2]], [0.04, 0.8])
        self.assertTrue(np.isnan(adjusted[1]))

    def test_summary_adjusts_distance_and_coincidence_tests_together(self) -> None:
        distance = pd.DataFrame(
            [{
                "event_family": "HCS_author_catalog",
                "observed_mean_abs_distance": 2.0,
                "null_mean_abs_distance": 4.0,
                "null_q025": 1.0,
                "null_q975": 8.0,
                "observed_median_abs_distance": 1.0,
                "null_median": 2.0,
                "p_value_mean": 0.01,
                "p_value_median": 0.02,
                "cluster_null_mean_abs_distance": 4.1,
                "cluster_null_q025": 1.1,
                "cluster_null_q975": 8.1,
                "cluster_null_median": 2.1,
                "p_value_mean_cluster": 0.01,
                "p_value_median_cluster": 0.02,
                "season_cluster_null_mean_abs_distance": 4.2,
                "season_cluster_null_q025": 1.2,
                "season_cluster_null_q975": 8.2,
                "season_cluster_null_median": 2.2,
                "p_value_mean_season_cluster": 0.01,
                "p_value_median_season_cluster": 0.02,
                "interpretation": "test",
            }]
        )
        coincidence = pd.DataFrame(
            [{
                "event_family": "CIR_arrival_catalog",
                "window_definition": "plus_minus_1d",
                "observed_count": 8,
                "null_mean_count": 4.0,
                "null_q025_count": 1.0,
                "null_q975_count": 7.0,
                "p_value": 0.03,
                "cluster_null_mean_count": 4.1,
                "cluster_null_q025_count": 1.1,
                "cluster_null_q975_count": 7.1,
                "p_value_cluster": 0.03,
                "season_cluster_null_mean_count": 4.2,
                "season_cluster_null_q025_count": 1.2,
                "season_cluster_null_q975_count": 7.2,
                "p_value_season_cluster": 0.03,
                "interpretation": "test",
            }]
        )

        results = SUMMARY_MODULE.build_key_results(distance, coincidence)

        self.assertEqual(len(results), 9)
        self.assertEqual(
            set(results["null_model"]),
            {"year_month_independent", "year_month_cluster_rotation", "year_season_cluster_shift_15d"},
        )
        np.testing.assert_allclose(results["p_value_holm"], [0.09, 0.09, 0.09, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12])


if __name__ == "__main__":
    unittest.main()