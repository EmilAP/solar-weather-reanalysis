# Block Bootstrap Null Summary

Analysis period: 1963-01-01 to 2023-12-31
Lag window: +/-30 days
Iterations per analysis: 500

## Lag-0 Results
- author_hcs, block=7: observed=2.989933, null_mean=2.840331, 95%=[2.556753, 3.201664], inside_band=True, outside_band_lag_count=6, event_count=1788
- author_hcs, block=14: observed=2.989933, null_mean=2.847147, 95%=[2.555467, 3.166960], inside_band=True, outside_band_lag_count=7, event_count=1788
- reconstructed_hcs, block=7: observed=3.061133, null_mean=2.837317, 95%=[2.525911, 3.126220], inside_band=True, outside_band_lag_count=7, event_count=1783
- reconstructed_hcs, block=14: observed=3.061133, null_mean=2.837780, 95%=[2.517050, 3.199720], inside_band=True, outside_band_lag_count=5, event_count=1783

## Interpretation
No lag-0 estimate falls outside the block-bootstrap 95% null band.
This indicates whether preserving short-range clustering changes the null conclusion for lag 0.
