# Methodology

This project separates two branches of analysis.

## Branch 1: Paper-Style Replication

- Use the author-provided HCS/SBC list when available.
- Build superposed-epoch windows around HCS crossing days.
- Reproduce cumulative tornado, strong tornado, injury, and fatality curves.
- Include a paper-style random-date Monte Carlo null for comparability.

## Branch 2: Stricter Reanalysis

- Use daily rates rather than cumulative curves as the primary inferential target.
- Compare author HCS, independently reconstructed HCS, and CIR/HSS proxy events.
- Use season-matched permutation nulls that preserve year structure.
- Correct across lags with a max-statistic.
- Fit daily count and outbreak-day models with seasonality and trend controls.

## Core Data Products

- Clean event catalogs in `data/derived/catalogs/`
- Daily tornado and solar-wind summaries in `data/derived/daily/`
- Superposed-epoch outputs in `data/derived/spe/`
- Model outputs in `data/derived/models/`
- Final figures, tables, and reports in `data/derived/`
