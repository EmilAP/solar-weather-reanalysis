from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _hcs_reconstruction import reconstruct_hcs

spec = importlib.util.spec_from_file_location("observation_sensitivity", SCRIPTS / "46_observation_sensitivity.py")
sensitivity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sensitivity)


class CoverageTests(unittest.TestCase):
    def frame(self, values):
        return pd.DataFrame({"date": pd.date_range("2000-01-01", periods=len(values)), "bx_gse_mean": values})

    def test_primary_crossing_and_later_date(self):
        frame = self.frame([-1., -1., 1., 1.])
        catalog, count = reconstruct_hcs(frame)
        self.assertEqual(count, 1)
        self.assertEqual(catalog.date.tolist(), [frame.date.iloc[2]])

    def test_low_coverage_is_a_hard_barrier_not_forward_filled(self):
        frame = self.frame([-1., -1., np.nan, 1., 1.])
        primary, _ = reconstruct_hcs(frame)
        constrained, _ = reconstruct_hcs(frame, coverage_ok=pd.Series([True, True, False, True, True]))
        self.assertEqual(len(primary), 1)
        self.assertTrue(constrained.empty)

    def test_qualified_ambiguous_day_still_uses_original_fill(self):
        frame = self.frame([-1., -1., .1, 1., 1.])
        primary, _ = reconstruct_hcs(frame)
        constrained, _ = reconstruct_hcs(frame, coverage_ok=pd.Series(True, index=frame.index))
        pd.testing.assert_frame_equal(primary, constrained)

    def test_coverage_alignment_must_be_explicit(self):
        with self.assertRaisesRegex(ValueError, "Coverage eligibility"):
            reconstruct_hcs(self.frame([-1., -1., 1., 1.]), coverage_ok=pd.Series([True]))


class TimingTests(unittest.TestCase):
    def test_cst_is_fixed_six_hours_gmt_unchanged_others_unresolved(self):
        frame = pd.DataFrame({
            "date": ["2000-06-01"] * 4,
            "event_datetime_local": ["2000-06-01 20:00:00"] * 4,
            "tz": [3, 0, 6, 9],
        })
        converted = sensitivity.utc_tornado_dates(frame)
        self.assertEqual(converted.utc_date.iloc[0], pd.Timestamp("2000-06-02"))
        self.assertEqual(converted.utc_date.iloc[1], pd.Timestamp("2000-06-01"))
        self.assertTrue(converted.utc_date.iloc[2:].isna().all())
        self.assertEqual(converted.timezone_documented.tolist(), [True, True, False, False])

    def test_december_rollover_and_missing_codes(self):
        frame = pd.DataFrame({
            "date": ["2023-12-31"] * 2,
            "event_datetime_local": ["2023-12-31 23:00:00"] * 2,
            "tz": [3, np.nan],
        })
        converted = sensitivity.utc_tornado_dates(frame)
        self.assertEqual(converted.utc_date.iloc[0], pd.Timestamp("2024-01-01"))
        self.assertTrue(pd.isna(converted.utc_date.iloc[1]))

    def test_missing_clock_is_not_silently_assigned(self):
        frame = pd.DataFrame({"date": ["2000-01-01"], "event_datetime_local": [None], "tz": [3]})
        with self.assertRaisesRegex(ValueError, "nonmissing"):
            sensitivity.utc_tornado_dates(frame)


class NullTests(unittest.TestCase):
    def test_exact_monthly_nulls_match_brute_force(self):
        index = pd.date_range("2000-01-01", "2000-12-31")
        anchors = pd.DatetimeIndex(["2000-02-10", "2000-02-12"])
        events = pd.DatetimeIndex(["2000-02-10"])
        rows = sensitivity.exact_coincidence(index, anchors, events)
        # Two anchors, one observed hit, three exposed dates in February.
        n = 29
        independent = np.mean([any(day in (9, 10, 11) for day in pair)
                               for pair in itertools.combinations(range(1, n + 1), 2)])
        rotation = np.mean([any((day - 1 + shift) % n + 1 in (9, 10, 11)
                                for day in (10, 12)) for shift in range(n)])
        annual = np.mean([any(day + shift in (9, 10, 11) for day in (10, 12))
                          for shift in range(-15, 16)])
        np.testing.assert_allclose([row["p_exact"] for row in rows], [independent, rotation, annual], atol=1e-14)
        self.assertEqual([row["observed_count"] for row in rows], [1, 1, 1])

    def test_annual_profiles_observed_and_boundaries(self):
        index = pd.date_range("2000-01-01", "2000-12-31")
        events = pd.DatetimeIndex(["2000-01-31", "2000-12-01"])
        outcome = np.arange(len(index), dtype=np.int64)
        observed, groups = sensitivity.yearly_profiles(index, events, outcome)
        expected = outcome[np.array([30, 335])[:, None] + np.arange(-30, 31)].sum(axis=0)
        np.testing.assert_array_equal(observed, expected)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 1)

    def test_daily_constant_counts_and_add_one_ties(self):
        index = pd.date_range("2000-01-01", "2000-12-31")
        events = pd.DatetimeIndex(["2000-04-04", "2000-06-10"])
        row, curve, draws = sensitivity.daily_test(index, events, np.ones(len(index), dtype=int), 25, 42)
        self.assertEqual(row["lag0_p_two_sided"], 1.)
        self.assertEqual(row["maximum_p"], 1.)
        self.assertEqual(row["lag0_upper_hits"], 25)
        self.assertEqual(row["maximum_hits"], 25)
        np.testing.assert_array_equal(draws, np.full((25, 61), 2))
        self.assertTrue(curve.observed_daily_mean.eq(1).all())

    def test_outbreak_anchors_outside_calendar_raise(self):
        with self.assertRaisesRegex(ValueError, "within the analysis"):
            sensitivity.exact_coincidence(
                pd.date_range("2000-01-01", "2000-12-31"),
                pd.DatetimeIndex(["1999-12-31"]), pd.DatetimeIndex(["2000-02-01"]),
            )

    def test_publication_workflow_runs_sensitivity_after_inputs(self):
        runner_spec = importlib.util.spec_from_file_location("publication", SCRIPTS / "run_publication.py")
        runner = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(runner)
        steps = [path for _, path in runner.STEPS]
        self.assertGreater(steps.index("scripts/46_observation_sensitivity.py"),
                           steps.index("scripts/45_author_outbreak_branch_summary.py"))


if __name__ == "__main__":
    unittest.main()
