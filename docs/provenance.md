# Provenance

This document tracks source provenance and acquisition outcomes.

## Required fields for each source
- Dataset name
- Citation or official source page
- Direct URL(s)
- Access timestamp (UTC)
- Download script used
- File path(s)
- SHA-256 checksum(s)
- Notes on transformations (if any)

## Current status
- Script-generated per-source manifests are written to `data/manifests/`.
- Master summary is written to `data/manifests/master_manifest.json`.
- Validation report is written to `data/processed/validation_report.json`.

## Manuscript input snapshot

The following SHA-256 fingerprints were calculated from the local inputs on 31 October 2026. This records the bytes present during the publication investigation, not a new acquisition timestamp or a publicly deposited archive. Match these fingerprints before claiming use of the same inputs. A checksum alone is not a download location.

| Input path | SHA-256 | Source |
|---|---|---|
| `data/raw/spc_tornado/spc_actual_tornadoes_1950_2023.csv` | `fa616e2f829c553acc7b60f5130a3ac498198e0b9d69e37a0e1289df71dc5fcc` | [NOAA SPC CSV](https://www.spc.noaa.gov/wcm/data/1950-2023_actual_tornadoes.csv) |
| `data/raw/omni/omni2_all_years.dat` | `5e18e8cdc52e1fc8ede19b68ce5ca7b1f7b9b71b187f0e1879278ec5373f926f` | [NASA OMNI hourly file](https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_all_years.dat) |
| `data/raw/icme/icmetable2.csv` | `2bfa87cf4980b8ded825df38b8b3d9bc222f9d0443e24e1feff51b95ec3f4547` | Parsed from the [Richardson-Cane table](https://izw1.caltech.edu/ACE/ASC/DATA/level3/icmetable2.htm) by `scripts/04_download_icme.py` |
| `data/raw/hcs/SBCtorlist1963-2024.txt` | `0db523d78af8c2af3f6dd4083184bfd160dd7c81cd5d6e54fcf5f16d273ec473` | Locally supplied author list; an exact public source URL has not been established here. |
| `data/papers/tornado-paper-supplement.pdf` | `cd2db44abe3936afef69ccb9f6fccfd6bcd46fd6ded24a4bd6231f6134dd12f2` | [Prikryl and Rusin (2025) supplement](https://asr.copernicus.org/articles/22/19/2025/asr-22-19-2025-supplement.pdf) |

The ICME source HTML fingerprint is `7cf9d9ddb2a5104401a0b0e12b889f8354a0ed45899d2e3737f4d581cbaefb7b` for `data/raw/icme/icmetable2.html`. The CSV is the analysis input; the HTML documents its source.

The public endpoints can change. For exact numerical reproduction, preserve these input bytes in an immutable release or data archive, record the released code commit and runtime, and archive the comparison outputs. See [the reproduction requirements](../README.md#github-publication-and-reproducibility). Neither an unsuccessful GitHub push nor a local fingerprint table constitutes such a release.
