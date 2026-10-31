# Lag-0 Permutation P-values

## P-value Table

| analysis | branch | null_model | block_length_days | observed_lag0 | null_mean | null_q025 | null_q975 | p_value_one_sided | p_value_two_sided | interpretation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| core_fast_null | author_hcs | fast_random_date | nan | 2.989933 | 2.847025 | 2.539304 | 3.139723 | 0.205589 | 0.411178 | not significant at p < 0.05 |
| core_fast_null | reconstructed_hcs | fast_random_date | nan | 3.061133 | 2.847564 | 2.548233 | 3.151739 | 0.101796 | 0.203593 | not significant at p < 0.05 |
| phase_randomized | author_hcs | phase_randomized | nan | 2.989933 | 2.833203 | 2.545342 | 3.154546 | 0.164179 | 0.328358 | not significant at p < 0.05 |
| block_bootstrap_author_block7 | author_hcs | block_bootstrap | 7.0 | 2.989933 | 2.840331 | 2.556753 | 3.201664 | 0.191617 | 0.383234 | not significant at p < 0.05 |
| block_bootstrap_author_block14 | author_hcs | block_bootstrap | 14.0 | 2.989933 | 2.847147 | 2.555467 | 3.166960 | 0.175649 | 0.351297 | not significant at p < 0.05 |
| block_bootstrap_reconstructed_block7 | reconstructed_hcs | block_bootstrap | 7.0 | 3.061133 | 2.837317 | 2.525911 | 3.126220 | 0.081836 | 0.163673 | not significant at p < 0.05 |
| block_bootstrap_reconstructed_block14 | reconstructed_hcs | block_bootstrap | 14.0 | 3.061133 | 2.837780 | 2.517050 | 3.199720 | 0.105788 | 0.211577 | not significant at p < 0.05 |
| seasonal_full_year | author_hcs | seasonal_random_date | nan | 2.989933 | 2.856180 | 2.555020 | 3.178789 | 0.193613 | 0.387226 | not significant at p < 0.05 |
| seasonal_mar_jun | author_hcs | seasonal_random_date | nan | 5.355263 | 5.175164 | 4.520518 | 5.940090 | 0.297405 | 0.594810 | not significant at p < 0.05 |
| seasonal_apr_jun | author_hcs | seasonal_random_date | nan | 6.378723 | 6.167443 | 5.360479 | 6.986543 | 0.309381 | 0.618762 | not significant at p < 0.05 |
| seasonal_full_year | reconstructed_hcs | seasonal_random_date | nan | 3.061133 | 2.838452 | 2.552776 | 3.151767 | 0.075848 | 0.151697 | not significant at p < 0.05 |
| seasonal_mar_jun | reconstructed_hcs | seasonal_random_date | nan | 5.647359 | 5.182201 | 4.559497 | 5.877385 | 0.083832 | 0.167665 | not significant at p < 0.05 |
| seasonal_apr_jun | reconstructed_hcs | seasonal_random_date | nan | 6.845133 | 6.148248 | 5.253042 | 7.079038 | 0.059880 | 0.119760 | not significant at p < 0.05 |

## Interpretation
- Any p < 0.05: False
- Any p < 0.01: False
- None of these lag-0 Monte Carlo comparisons rejects at 0.05. This is not an equivalence test or evidence of an exactly zero effect; distinct null constructions preserve different properties.

## Source Files Used
- data/derived/spe/author_hcs_apr_jun_fast_null_all_tornadoes.csv
- data/derived/spe/author_hcs_full_year_fast_null_all_tornadoes.csv
- data/derived/spe/author_hcs_mar_jun_fast_null_all_tornadoes.csv
- data/derived/spe/block_bootstrap_author_hcs_block14.csv
- data/derived/spe/block_bootstrap_author_hcs_block7.csv
- data/derived/spe/block_bootstrap_reconstructed_hcs_block14.csv
- data/derived/spe/block_bootstrap_reconstructed_hcs_block7.csv
- data/derived/spe/fast_null_test_all_tornadoes.csv
- data/derived/spe/phase_randomized_author_hcs_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_apr_jun_fast_null_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_fast_null_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_full_year_fast_null_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_mar_jun_fast_null_all_tornadoes.csv
