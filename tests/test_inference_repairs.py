from __future__ import annotations

import importlib.util
import contextlib
import io
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _utils import (
    OMNI_COLUMN_NAMES, add_cumulative_columns, complete_window_dates, null_tail_probabilities, parse_omni_hourly,
    year_month_matched_sampler, year_month_cluster_shift_sampler, year_season_cluster_shift_sampler,
)
import _outbreak_inference as outbreak


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EventPopulationTests(unittest.TestCase):
    def test_duplicates_invalid_and_edge_dates_removed(self):
        days = pd.date_range("2000-01-01", periods=10)
        events = ["1999-12-31", "2000-01-01", "2000-01-04T10:00Z", "2000-01-04T12:00Z", "invalid"]
        self.assertEqual(complete_window_dates(events, days, 2), [pd.Timestamp("2000-01-04")])

    def test_calendar_gaps_raise(self):
        with self.assertRaisesRegex(ValueError, "contiguous"):
            complete_window_dates([], pd.DatetimeIndex(["2000-01-01", "2000-01-03"]), 0)

    def test_samplers_do_not_reparse_typed_dates_each_iteration(self):
        anchors = pd.Series(pd.to_datetime(["2000-04-04", "2000-04-10"]))
        valid = pd.date_range("2000-01-01", "2000-12-31")
        samplers = [
            year_month_matched_sampler(anchors, valid),
            year_month_cluster_shift_sampler(anchors, valid),
            year_season_cluster_shift_sampler(anchors, valid, 15),
        ]
        with patch.object(pd, "to_datetime", side_effect=AssertionError("Unnecessary repeated date parsing")):
            for sampler in samplers:
                sampled = sampler(np.random.default_rng(42))
                self.assertEqual(sampled.dtype, np.dtype("datetime64[ns]"))
                self.assertEqual(len(sampled), len(anchors))

    def test_epoch_totals_are_across_events_not_across_lags(self):
        mean = pd.DataFrame({"lag": [-1, 0, 1], "count": [1., 3., 2.], "event_count": [2, 2, 2]})
        totals = add_cumulative_columns(mean, ["count"])
        np.testing.assert_array_equal(totals["count_cumulative"], [2., 6., 4.])
        module = load_script("27_event_study_reconstructed_hcs")
        daily = pd.DataFrame({metric: [0., 1., 3., 2., 0.] for metric in module.METRICS})
        observed = module.build_observed_table(daily, np.array([2]), np.array([-1, 0, 1]))
        for metric in module.METRICS:
            np.testing.assert_array_equal(observed[f"{metric}_cumulative"], [1., 3., 2.])

    def test_optional_paper_null_uses_across_event_totals(self):
        module = load_script("16_reproduce_paper_hcs_spe")
        days = pd.date_range("2000-01-01", periods=7)
        daily = pd.DataFrame({"date": days, **{metric: 2. for metric in module.METRICS}})
        result = module._build_null_summary(
            daily, [days[2], days[4]], 1, 3, np.random.default_rng(42), unittest.mock.Mock()
        )
        self.assertTrue(result.statistic.eq("across_event_total").all())
        self.assertTrue(result.event_count.eq(2).all())
        for metric in module.METRICS:
            np.testing.assert_array_equal(result[f"{metric}_cumulative_mean"], [4., 4., 4.])

    def test_paper_check_rejects_stale_running_sum_outputs(self):
        module = load_script("24_check_author_hcs_null_result")
        with tempfile.TemporaryDirectory() as directory:
            observed = Path(directory) / "observed.csv"
            null = Path(directory) / "null.csv"
            pd.DataFrame({"lag": [0]}).to_csv(observed, index=False)
            pd.DataFrame({"lag": [0]}).to_csv(null, index=False)
            with patch.object(module, "OBSERVED_PATH", observed), patch.object(module, "NULL_PATH", null):
                with self.assertRaisesRegex(ValueError, "rerun script 16"):
                    module.load_inputs()


class AuditedSourceTests(unittest.TestCase):
    def test_distance_and_coincidence_cir_reconstruction_agree(self):
        distance = load_script("43_author_outbreak_event_distance_test")
        coincidence = load_script("44_author_outbreak_event_coincidence_test")
        omni = pd.DataFrame({
            "date": pd.date_range("2000-01-01", periods=3),
            "speed_mean": [400., 550., 650.], "proton_density_mean": [1., 9., 1.],
            "b_mag_mean": [1., 1., 1.], "flow_pressure_mean": [1., 1., 1.],
        })
        expected = distance.derive_cir_catalog(omni)
        self.assertEqual(len(expected), 1)
        pd.testing.assert_frame_equal(expected, coincidence.derive_cir_catalog(omni))

    def test_cross_month_dates_survive_extraction_and_preparation(self):
        extract = load_script("39c_extract_supplement_table_pdfplumber")
        prepare = load_script("39d_prepare_pdfplumber_outbreak_table")
        cases = [
            ("31 May \u2013 1 Jun 1971", "1971-05-31", "1971-06-01"),
            ("30 Apr \u2013 1 May 1975", "1975-04-30", "1975-05-01"),
            ("30 Jun \u2013 4 Jul 1993", "1993-06-30", "1993-07-04"),
            ("31 May - 24 Jun 1996", "1996-05-31", "1996-06-24"),
            ("31 May - 1 Jun 1998", "1998-05-31", "1998-06-01"),
            ("30 Jun - 1 Jul 1998", "1998-06-30", "1998-07-01"),
            ("31 May - 1 Jun 2013", "2013-05-31", "2013-06-01"),
            ("30 Apr \u2013 1 May 2017", "2017-04-30", "2017-05-01"),
            ("Dec 31-Jan 1, 1971", "1970-12-31", "1971-01-01"),
        ]
        for text, start, end in cases:
            with self.subTest(text=text):
                raw = f"A {text} (17, 20) Great Plains HCS/CIR: May 29"
                rows, _ = extract.rows_from_text(7, raw)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["outbreak_date_text"], text)
                self.assertEqual(prepare.parse_date_text(rows[0]["outbreak_date_text"]), (start, end))
                self.assertIn(text, rows[0]["raw_row_text"])

    def test_source_review_keeps_literal_dates_and_inference_notes(self):
        extract = load_script("39c_extract_supplement_table_pdfplumber")
        prepare = load_script("39d_prepare_pdfplumber_outbreak_table")
        rows = [
            dict(row_id=169, source_page=11, **extract.parse_row_text(
                "A 31 May - 24 Jun 1996 (27, 24) Central CIR: May 29")),
            dict(row_id=329, source_page=14, **extract.parse_row_text(
                "B 28 Feb - 1 Mar (33, 12) Midwest HCS/CIR: Jan 1; HDP")),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ["INPUT_PATH", "FLAGGED_PATH", "OUTPUT_PATH", "REVIEW_PATH", "SOURCE_REVIEW_PATH", "REPORT_PATH"]
            paths = {name: root / f"{name}.csv" for name in names}
            pd.DataFrame(rows).to_csv(paths["INPUT_PATH"], index=False)
            with patch.multiple(prepare, ROOT=root, **paths), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(prepare.main(), 0)
            saved = pd.read_csv(paths["OUTPUT_PATH"]).set_index("row_id")
            review = pd.read_csv(paths["SOURCE_REVIEW_PATH"])
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved.loc[169, "outbreak_date_start"], "1996-05-31")
        self.assertEqual(saved.loc[169, "outbreak_date_end"], "1996-06-24")
        self.assertIn("accepted by the project author", saved.loc[169, "source_date_review_note"])
        self.assertEqual(saved.loc[329, "outbreak_date_start"], "2011-02-28")
        self.assertEqual(set(review.row_id), {169, 329})
        self.assertTrue(review.source_date_review_status.eq("accepted").all())
        self.assertFalse(review.source_date_review_required.any())

    def author_frame(self, text):
        module = load_script("11_ingest_author_hcs")
        return module, pd.DataFrame([dict(line_number=848, **module.parse_line(text))])

    def test_invalid_author_date_reconciled_only_by_redundant_agreement(self):
        module, frame = self.author_frame("1993 11 0 0 2 304 270264")
        result = module.reconcile_dates(frame)
        self.assertEqual(result.loc[0, "datetime_utc"], pd.Timestamp("1993-10-31T00:00Z"))
        self.assertTrue(pd.isna(result.loc[0, "datetime_source_utc"]))
        self.assertEqual(result.loc[0, "day"], 0)
        self.assertIn("agreement", result.loc[0, "date_reconciliation_note"])

    def test_author_date_conflicts_and_unresolved_rows_raise(self):
        for text in ["1993 11 0 0 2 304 270265", "1993 11 1 0 2 304 270264",
                     "1993 11 0 0 2 367 270264", "1993 11 0 0 2"]:
            with self.subTest(text=text):
                module, frame = self.author_frame(text)
                with self.assertRaisesRegex(ValueError, "848"):
                    module.reconcile_dates(frame)

    def test_valid_author_date_preserved(self):
        module, frame = self.author_frame("1993 11 3 18 1 307 270354")
        result = module.reconcile_dates(frame)
        self.assertEqual(result.loc[0, "datetime_utc"], pd.Timestamp("1993-11-03T18:00Z"))
        self.assertEqual(result.loc[0, "date_reconciliation_note"], "")

    def test_missing_decline_catalog_is_rebuilt_not_replaced_by_onsets(self):
        module = load_script("43_author_outbreak_event_distance_test")
        days = pd.date_range("2000-01-01", periods=7)
        omni = pd.DataFrame({"date": days, "speed_mean": [400, 450, 650, 600, 550, 500, 450]})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalogs = root / "data" / "derived" / "catalogs"
            catalogs.mkdir(parents=True)
            for name in ["author_hcs_catalog", "hcs_from_omni", "cir_proxy_catalog", "icme_catalog", "hss_onset_catalog"]:
                pd.DataFrame({"date": [days[2]]}).to_csv(catalogs / f"{name}.csv", index=False)
            paths = {
                "ROOT": root, "AUTHOR_HCS_PATH": catalogs / "author_hcs_catalog.csv",
                "RECON_HCS_PATH": catalogs / "hcs_from_omni.csv",
                "HSS_DECLINE_OUT_PATH": catalogs / "major_hss_declining_phase_catalog.csv",
            }
            with patch.multiple(module, **paths):
                result, status, _ = module.get_event_catalogs(omni)
                self.assertTrue(paths["HSS_DECLINE_OUT_PATH"].exists())
                second, _, _ = module.get_event_catalogs(omni)
        expected = days[3:7].tolist()
        self.assertEqual(result["major_HSS_declining_phase_catalog"].tolist(), expected)
        self.assertEqual(second["major_HSS_declining_phase_catalog"].tolist(), expected)
        self.assertEqual(status["major_HSS_declining_phase_catalog"], "reconstructed")

    def test_summary_report_creates_directory_on_clean_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            for filename in ["23_write_summary_report.py", "_utils.py", "common.py"]:
                shutil.copy2(SCRIPTS / filename, scripts / filename)
            process = subprocess.run(
                [sys.executable, "-B", str(scripts / "23_write_summary_report.py")],
                cwd=root, capture_output=True, text=True, check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue((root / "data" / "derived" / "reports" / "analysis_summary.md").exists())


class TailProbabilityTests(unittest.TestCase):
    def test_add_one_and_equal_tail_definition(self):
        result = null_tail_probabilities(np.array([5., 1.]), np.array([[1., 1.], [2., 2.], [3., 3.]]))
        np.testing.assert_allclose(result["p_value_one_sided"], [0.25, 1.])
        np.testing.assert_allclose(result["p_value_two_sided"], [0.5, 1.])
        np.testing.assert_array_equal(result["null_iterations"], [3, 3])

    def test_empty_draws_raise(self):
        with self.assertRaises(ValueError):
            null_tail_probabilities(np.array([1.]), np.empty((0, 1)))

    def test_envelope_only_report_is_rejected(self):
        module = load_script("38_lag0_permutation_pvalues")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "curve.csv"
            pd.DataFrame([dict(lag=0, observed_daily_mean=2, null_mean=2, null_q025=1, null_q975=3)]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "rerun"):
                module.process_file(path, "test", "author", "test", None)

    def test_precision_allows_holm_rejection_and_reports_uncertainty(self):
        result = outbreak.tail_summary(2, np.ones(outbreak.ITERATIONS))
        self.assertLess(87 * result["p"], 0.05)
        self.assertEqual(result["exceedances"], 0)
        self.assertGreater(result["mc_high"], result["p"])
        self.assertEqual(result["mc_low"], 0)

    def test_summary_flags_threshold_spanning_monte_carlo_bounds(self):
        module = load_script("45_author_outbreak_branch_summary")
        row = dict(
            event_family="HCS_author_catalog", window_definition="plus_minus_1d",
            observed_count=15, interpretation="test", outbreak_count=30,
        )
        for prefix, suffix in (("", ""), ("cluster_", "_cluster"), ("season_cluster_", "_season_cluster")):
            row.update({
                f"{prefix}null_mean_count": 10, f"{prefix}null_q025_count": 5,
                f"{prefix}null_q975_count": 14, f"p_value{suffix}": 0.01,
                f"p_value{suffix}_mc_low": 0.001, f"p_value{suffix}_mc_high": 0.1,
                f"p_value{suffix}_iterations": 50000, f"p_value{suffix}_exceedances": 499,
            })
        results = module.build_key_results(pd.DataFrame(), pd.DataFrame([row]))
        self.assertTrue((results.p_value_holm < 0.05).all())
        self.assertTrue(results.interpretation.str.contains("uncertainty spans").all())
        self.assertIn("3 intervals span", module.interpret_rescue(results))


class OutbreakPopulationTests(unittest.TestCase):
    def test_icme_uses_documented_coverage(self):
        anchors = pd.Series(pd.to_datetime(["1995-05-01", "1996-05-01"]))
        selected, valid = outbreak.exposure_population(anchors, pd.Series(pd.date_range("1995-01-01", "1997-01-01")), "ICME_impact_catalog")
        self.assertEqual(selected.tolist(), [pd.Timestamp("1996-05-01")])
        self.assertEqual(valid.min(), pd.Timestamp("1996-01-01"))

    def test_batched_statistics_match_direct_windows_and_cache(self):
        family = "HCS_reconstructed_catalog"
        anchors = pd.Series(pd.to_datetime(["2000-04-04", "2000-04-10"]))
        events = pd.Series(pd.to_datetime(["2000-04-03", "2000-04-12"]))
        valid = pd.Series(pd.date_range("2000-01-01", "2000-12-31"))
        with tempfile.TemporaryDirectory() as directory, patch.object(outbreak, "ROOT", Path(directory)):
            observed, draws, count = outbreak.family_statistics(anchors, events, valid, family, 20)
            second = outbreak.family_statistics(anchors, events, valid, family, 20)
        np.testing.assert_array_equal(observed, [1.5, 1.5, 1, 2, 2, 1])
        np.testing.assert_array_equal(draws, second[1])
        self.assertEqual(draws.shape, (3, 20, 6))
        self.assertEqual(count, 2)

    def test_distance_and_coincidence_use_identical_icme_catalog(self):
        distance = load_script("43_author_outbreak_event_distance_test")
        coincidence = load_script("44_author_outbreak_event_coincidence_test")
        self.assertEqual(coincidence.ICME_PATH.name, "icme_catalog.csv")
        self.assertEqual(distance.ITERATIONS, coincidence.ITERATIONS)


class CountModelTests(unittest.TestCase):
    def test_estimates_overdispersion_instead_of_boundary_solution(self):
        module = load_script("20_run_daily_models")
        rng = np.random.default_rng(42)
        outcome = pd.Series(rng.negative_binomial(0.1, 0.1 / 0.4, size=3000))
        features = pd.DataFrame({"const": np.ones(len(outcome))})
        coefficients, metrics = module.fit_and_collect(
            "synthetic_nb", outcome, features, module.sm.families.NegativeBinomial(alpha=1.0)
        )
        alpha = coefficients.loc[coefficients.term == "alpha", "coef"].iloc[0]
        self.assertGreater(alpha, 4)
        self.assertLess(alpha, 20)
        self.assertEqual(metrics["covariance"], "HAC_14_days")
        self.assertTrue(np.isfinite(coefficients.stderr).all())


class OmniParserTests(unittest.TestCase):
    def test_whitespace_parser_preserves_fields_and_replaces_missing_codes(self):
        row = dict.fromkeys(OMNI_COLUMN_NAMES, 0)
        row.update(year=2000, doy=60, hour=12, bx_gse=1.25, speed=9999)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omni.dat"
            path.write_text("   ".join(str(row[name]) for name in OMNI_COLUMN_NAMES) + "\n")
            parsed = parse_omni_hourly(path)
        self.assertEqual(parsed.loc[0, "datetime_utc"], pd.Timestamp("2000-02-29T12:00Z"))
        self.assertEqual(parsed.loc[0, "bx_gse"], 1.25)
        self.assertTrue(pd.isna(parsed.loc[0, "speed"]))


if __name__ == "__main__":
    unittest.main()
