# Manual Steps

Some sources may not be fully downloadable in automated mode. Follow these steps when manifests indicate `manual_required: true`.

## HCS Catalog (Exact Cited List)
1. Identify the exact heliospheric current sheet (HCS) crossing/list source cited by Prikryl and Rusin (2025).
2. Download the original public file(s) from the official host.
3. Place raw files in `data/raw/hcs/` without editing.
4. Add a short provenance note in `docs/provenance.md` with citation, URL, access date, and checksum.

## Green Corona Dataset
1. Obtain the official/public green coronal line dataset used by the paper.
2. Place raw source file(s) in `data/raw/green_corona/`.
3. Preserve any original metadata pages in HTML or PDF form in the same directory.
4. Record source details and checksums in `docs/provenance.md`.

## ERA5 Credentials and Controlled Download
1. Copy `data/raw/era5/.cdsapirc.template` to `~/.cdsapirc` and insert your CDS credentials.
2. Review `data/raw/era5/era5_request_template.json` and reduce scope if needed.
3. Use `data/raw/era5/download_era5_template.py` for controlled retrieval.
4. Keep downloaded files in `data/raw/era5/` and do not overwrite raw assets.

## NCEI Large Pull (Optional Staged Run)
1. Run with a limit first for smoke test:
   - `python scripts/02_download_ncei_storm_events.py --limit 2`
2. Run full acquisition when bandwidth and storage are available:
   - `python scripts/02_download_ncei_storm_events.py`
