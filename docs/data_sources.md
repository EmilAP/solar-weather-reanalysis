# Data Sources

This workspace stages public datasets used in the 2025 tornado/solar-wind study by Prikryl and Rusin.

## SPC Tornado Database
- Source: NOAA Storm Prediction Center (SPC)
- URL: `https://www.spc.noaa.gov/wcm/data/1950-2023_actual_tornadoes.csv`
- Script: `scripts/01_download_spc_tornado.py`

## NCEI Storm Events
- Source: NOAA NCEI Storm Events bulk CSV archive
- URL: `https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/`
- Script: `scripts/02_download_ncei_storm_events.py`

## OMNI Hourly Solar-Wind and IMF
- Source: NASA SPDF OMNI low-resolution archive
- URL base: `https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/`
- Script: `scripts/03_download_omni.py`

## ICME (Richardson-Cane)
- Source: Caltech ACE/ASC, Richardson and Cane ICME table
- URLs:
  - `https://izw1.caltech.edu/ACE/ASC/DATA/level3/icmetable2.htm`
  - `https://izw1.caltech.edu/ACE/ASC/DATA/level3/icmetable2.txt`
- Script: `scripts/04_download_icme.py`

## HCS Catalog
- Candidate public sources attempted in `config/sources.yaml`.
- Script: `scripts/05_get_hcs_catalog.py`
- If exact cited list is not available, a documented manual gap is recorded.

## Green Corona Dataset
- Candidate official/public sources attempted in `config/sources.yaml`.
- Script: `scripts/06_get_green_corona.py`
- If blocked/unavailable, manual instructions are recorded.

## ERA5
- Source: Copernicus Climate Data Store (CDS)
- Script: `scripts/07_prepare_era5_requests.py`
- This project prepares request templates only; it does not launch large downloads automatically.

## SPC Outlook Archives (Table 2 context)
- Source: SPC archive pages for 2021 outlook products
- Script: `scripts/08_get_spc_outlooks.py`
