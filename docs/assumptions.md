# Assumptions

## Explicit assumptions

- The author-provided HCS/SBC text file is expected somewhere inside this workspace and is located automatically by filename pattern.
- Until that file is present, the author-HCS branch cannot run and should fail transparently.
- SPC tornado daily analyses use the catalog calendar date rather than UTC-converted timestamps.
- Strong tornadoes are defined as F3+/EF3+ using `mag >= 3`.
- The independently reconstructed HCS catalog is a proxy, not a substitute for the author list.
- The reconstructed HCS proxy uses smoothed IMF sector-polarity sign flips derived from OMNI hourly data.
- CIR/HSS events are simple transparent proxies based on speed rise and compression signatures, not a claim of exact stream-interface identification.
- ICME analysis times default to the parsed plasma/field start when available; otherwise the disturbance time is used.

## Known caveats

- The current Richardson-Cane source available in this workspace covers 1996 onward rather than the full OMNI span.
- OMNI currently extends beyond 2023; the analysis table is clipped to 2023-12-31 unless configured otherwise.
- Overlapping event windows can inflate apparent sample size; stricter nulls and max-statistic correction are used to address this.
