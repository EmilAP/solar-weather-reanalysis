# Reanalysis Pipeline: Tornado and Solar-Wind / HCS Coupling (Prikryl & Rušin, 2025)

This workspace now contains both:

- a reproducible acquisition/staging layer for the public raw inputs
- a full reanalysis pipeline intended to reproduce and stress-test the paper's HCS-keyed tornado results

The manuscript release includes the staged raw inputs and derived evidence. The oversized raw OMNI file and cleaned hourly CSV use Git LFS; retrieve their contents before analysis. See [GitHub publication and reproducibility](#github-publication-and-reproducibility) before distributing this project.

Required data sources:

OMNI solar wind data
https://omniweb.gsfc.nasa.gov/

NOAA SPC tornado database
https://www.spc.noaa.gov/wcm/

Data ingestion scripts in /scripts reproduce all derived datasets.

## Project Structure

- `config/sources.yaml`: source URLs and acquisition settings
- `config/analysis_config.yaml`: analysis thresholds, event windows, and model settings
- `scripts/00_*` to `scripts/10_*`: raw-data acquisition and validation
- `scripts/11_*` to `scripts/23_*`: ingestion, reanalysis, figures, tables, and reporting
- `scripts/run_all.py`: one-command acquisition pipeline
- `scripts/run_analysis.py`: one-command reanalysis pipeline
- `data/raw/`: immutable raw source files
- `data/interim/`: intermediate working files
- `data/processed/`: validation and run reports
- `data/derived/catalogs/`: cleaned event catalogs
- `data/derived/daily/`: daily tornado and solar-wind tables
- `data/derived/spe/`: superposed-epoch outputs and null summaries
- `data/derived/models/`: daily model outputs
- `data/derived/figures/`: PNG/SVG figures
- `data/derived/tables/`: summary tables
- `data/derived/reports/`: markdown reports and interpretation memos
- `data/logs/`: per-script logs
- `data/manifests/`: JSON manifests
- `docs/`: methodology, assumptions, replication notes, and data dictionary

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Preferred runtime: Python 3.11+

## Run Order

```bash
python3 scripts/00_check_environment.py
python3 scripts/01_download_spc_tornado.py
python3 scripts/02_download_ncei_storm_events.py
python3 scripts/03_download_omni.py
python3 scripts/04_download_icme.py
python3 scripts/05_get_hcs_catalog.py
python3 scripts/06_get_green_corona.py
python3 scripts/07_prepare_era5_requests.py
python3 scripts/08_get_spc_outlooks.py
python3 scripts/09_validate_downloads.py
python3 scripts/10_build_master_manifest.py
```

## One-Command Pipeline

```bash
python3 scripts/run_all.py
```

Outputs:
- Timestamped run report: `data/processed/pipeline_run_YYYYMMDDTHHMMSSZ.json`
- Latest run report (overwritten each run): `data/processed/pipeline_run_latest.json`

## Reanalysis Pipeline

```bash
python3 scripts/run_analysis.py
```

This runs:

```bash
python3 scripts/11_ingest_author_hcs.py
python3 scripts/12_parse_spc_tornado.py
python3 scripts/13_parse_omni.py
python3 scripts/14_parse_icme.py
python3 scripts/15_build_daily_tornado_series.py
python3 scripts/26_reconstruct_hcs_from_omni.py
python3 scripts/16_reproduce_paper_hcs_spe.py
python3 scripts/17_build_independent_hcs_from_omni.py
python3 scripts/18_detect_cir_hss_events.py
python3 scripts/19_run_stricter_event_study.py
python3 scripts/20_run_daily_models.py
python3 scripts/21_compare_event_catalogs.py
python3 scripts/22_generate_figures_and_tables.py
python3 scripts/23_write_summary_report.py
```

Primary reanalysis outputs:

- cleaned catalogs in `data/derived/catalogs/`
- daily analysis tables in `data/derived/daily/`
- event-study outputs in `data/derived/spe/`
- model outputs in `data/derived/models/`
- figures and tables in `data/derived/figures/` and `data/derived/tables/`
- final report in `data/derived/reports/analysis_summary.md`

## Publication Workflow

The full journal-style manuscript is in [`docs/manuscript.md`](docs/manuscript.md), including results tables, linked figures, references, an evidence map, and a submission checklist. It is a scientific-review draft, not a claim of causal validation or submission readiness. The [methodology](docs/methodology.md) records computational repairs, including consistent event populations and HCS definitions, empirical p-values, estimated count dispersion, and 50,000-replicate outbreak nulls with Monte Carlo uncertainty.

The publication workflow assumes acquisition inputs are already present locally. It does not download data or request credentials.

```bash
python3 scripts/run_publication.py
```

### GitHub publication and reproducibility

GitHub rejects ordinary Git blobs larger than 100 MiB. The attempted initial push was rejected because `data/raw/omni/omni2_all_years.dat` is 184,015,872 bytes; the 65,761,728-byte `data/derived/daily/omni_hourly_clean.csv` also exceeds GitHub's recommended 50 MB size. The entire push was rejected, not just the large files.

Adding a path to `.gitignore`, deleting it in a new commit, or running `git rm --cached` does not remove its large blobs from earlier commits. Publication requires either migrating those blobs to Git LFS or removing them from the history being pushed and supplying the required inputs separately. History migration changes commit IDs: preserve a backup first and coordinate with collaborators. Do not force-push an existing shared branch without agreement.

The manuscript release migrates both files to Git LFS, includes the recorded publication report and derived evidence, and identifies that snapshot with the `publication-2026-10-31` tag. Appendix C uses full GitHub URLs pinned to this tag rather than moving `main` URLs. To perform the same migration on an original, unmigrated checkout with an empty remote, install Git LFS and run the following from a clean working tree. Do not repeat this migration on the already migrated release:

```bash
git branch backup-before-lfs
git lfs install
git lfs migrate import \
  --include="data/raw/omni/omni2_all_years.dat,data/derived/daily/omni_hourly_clean.csv" \
  --include-ref=refs/heads/main
git lfs ls-files
git push -u origin main
```

Push `main`, not `--all`: the backup branch deliberately retains the original oversized history. Check the repository owner's LFS storage and bandwidth allowance before choosing this approach. Migration only converts already committed files; ignored Appendix C evidence still needs to be explicitly included in the release.

**Viewing results is not the same as reproducing them.** A reader can inspect uploaded CSVs, figures, and code without rerunning the analysis. Full computational reproduction requires the following raw inputs, the configuration, and the pinned dependencies in [`requirements.txt`](requirements.txt):

| Required input | Expected location | Acquisition or regeneration |
|---|---|---|
| SPC tornado records | `data/raw/spc_tornado/spc_actual_tornadoes_1950_2023.csv` | `python3 scripts/01_download_spc_tornado.py` |
| OMNI hourly records | `data/raw/omni/omni2_all_years.dat` | `python3 scripts/03_download_omni.py` |
| Richardson-Cane ICME table | `data/raw/icme/icmetable2.csv` | `python3 scripts/04_download_icme.py` |
| Exact author HCS crossing list | `data/raw/hcs/SBCtorlist1963-2024.txt` | Supply the original file; the candidate-page HCS downloader does not obtain this exact list. |
| Published supplement PDF | `data/papers/tornado-paper-supplement.pdf` | Obtain the [published supplement](https://asr.copernicus.org/articles/22/19/2025/asr-22-19-2025-supplement.pdf) and save it at this exact path. |

The cleaned OMNI CSV is an output of `scripts/13_parse_omni.py`, not a separately required input. It can be regenerated from the raw OMNI file during the publication run. NCEI, green-corona, ERA5, and outlook acquisition is not required by the current 38-step manuscript workflow.

For a fresh checkout, follow Setup above. If the release uses LFS, install Git LFS and run `git lfs pull` before analysis; a pointer file is not usable scientific data. Do not assume a GitHub ZIP includes LFS contents. If required public inputs are absent, the three acquisition commands in the table can fetch them; supply the exact author list and supplement separately. Avoid redownloading over an archived input snapshot.

Once all five inputs are present and their fingerprints have been checked against [the recorded snapshot](docs/provenance.md#manuscript-input-snapshot), run:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/run_publication.py
```

Fresh upstream downloads are not guaranteed to reproduce the manuscript's numerical values: OMNI and ICME records can be revised, and matching a year range does not establish matching contents. Exact-input reproduction requires an immutable, retrievable input snapshot with checksums, an identified code commit and environment, and comparison against archived outputs. The current checksums document the local inputs but do not themselves make those files downloadable.

The previously recorded reproduction checks used staged local inputs and an already installed environment. They do not establish that a fresh installation reproduces the expanded workflow. The release supplies the inputs and evidence, but this README does not claim that the expanded workflow has been independently rerun from a fresh public checkout. Appendix C's full, tag-pinned URLs also work in a separately distributed Markdown manuscript. GitHub can display text evidence; binary NumPy banks require downloading and opening with NumPy.

The included source paper, supplement, and extracted supplement material are attributed to Prikryl and Rusin (2025), [doi:10.5194/asr-22-19-2025](https://doi.org/10.5194/asr-22-19-2025), distributed by the publisher under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), except where otherwise noted in the source. Extracted catalogs are transformed outputs: parsing, date reconciliation, and classification changes are documented in the scripts and manuscript. The full author HCS file is a separately supplied input; inclusion is not a claim that it was extracted from the published supplement.

The runner executes the core reanalysis, null and robustness analyses, supplement extraction/preparation, outbreak analyses, manuscript tables, metadata, figure index, and canonical results export in dependency order. It stops at the first failed step and writes a detailed report to `data/processed/publication_run_latest.json`.

Source-date repairs preserve original records: the author crossing with invalid day zero is reconciled from two agreeing redundant date fields, and cross-month outbreak ranges retain their starts. The literal 31 May-24 June 1996 interval and inferred 2011 year were accepted by the project author; their accepted audit status remains in `data/derived/catalogs/supplement_table_s1_source_date_review.csv`. Neither entry is excluded.

Regression checks:

```bash
python3 -m unittest discover -s tests -q
```

The publication workflow now includes `scripts/46_observation_sensitivity.py`: minimum daily Bx coverage (1/12/18/24 hours with hard gaps), paired documented-SPC timezone conversion, and one-day timing shifts. It produces 22 daily scenarios (44 separately Holm-adjusted endpoints) and 30 exact outbreak sensitivity tests. The [sensitivity results](data/derived/reports/observation_sensitivity.md) and [manuscript](docs/manuscript.md#45-coverage-and-daily-timing-sensitivity-results) report the alignment-sensitive outbreak finding rather than claiming blanket robustness.

The [manuscript verification record](docs/manuscript.md#appendix-c-evidence-and-reproduction-map) distinguishes the earlier cache-free 37-step baseline reproduction from the expanded 38-step workflow and its sensitivity tests. Verification uses the installed virtual environment, not a fresh dependency installation.

To acquire or validate raw inputs first, use the acquisition steps above or `python3 scripts/run_all.py`. The paper-style cumulative Monte Carlo check (`scripts/16_reproduce_paper_hcs_spe.py --run-null`) is separate from the primary daily-rate publication workflow and should be run explicitly when that replication output is required.

## Notes

- Raw files are preserved in source-specific folders under `data/raw/`.
- HTML source pages are saved along with parsed text versions where applicable.
- ERA5 is scaffolded only (templates and credentials placeholder), no default bulk pull.
- Replication and stricter reanalysis are intentionally kept separate.
- Assumptions are documented in `docs/assumptions.md`.
- If a source cannot be downloaded automatically, manual instructions are documented in `docs/manual_steps.md`.

## Current Workspace Status

Acquisition status from the earlier pipeline is complete and validated.

- Validation: `data/manifests/09_validate_downloads.json` -> `overall_ok: true`
- Master manifest: `data/manifests/master_manifest.json` -> `ok_count: 10`, `fail_count: 0`
- SPC tornado: downloaded and validated (`row_count: 70022`, years `1950-2023`)
- NCEI storm events: full configured span downloaded (`1963-2023`, 61 yearly files)
- OMNI hourly: `omni2_all_years.dat` downloaded (`row_count: 561024`, years observed `1963-2026`)
- ICME Richardson-Cane: HTML acquired; TXT endpoint returned `404`; CSV derived from HTML table (`row_count: 648`, years observed `1996-2025`)
- HCS: candidate public pages acquired from WSO over HTTP and preserved as raw HTML + parsed text
- Green corona: one candidate source (`ngdc.noaa.gov`) returned `404`; alternate official SWPC page acquired and preserved
- ERA5: request templates and credentials scaffold created only (no bulk download launched)
- SPC outlook archive/index: archive root captured; 2021 directory intermittently returned `504`; extracted archive links saved to `data/raw/spc_outlooks/archive_links.csv` (`link_count: 29`)

The repository includes core analyses through script 23, publication analyses through script 45, and a sequential publication runner. The manuscript-facing reports distinguish the project-designated primary lag-0 daily-rate endpoint from post-hoc outbreak analyses and list outstanding limitations. Check `data/processed/publication_run_latest.json` for the status of the most recent complete publication run.
