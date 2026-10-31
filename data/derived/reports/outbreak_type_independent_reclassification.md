# Independent Outbreak Reclassification

## Rules
- A_like_CIR_following: CIR proxy within 3 days prior to outbreak.
- B_like_HCS_HDP_preceding: reconstructed HCS within 3 days prior plus proton density >= 8.0 cm^-3 on outbreak date.
- C_like_ICME_following: ICME catalog date or OMNI-derived ICME proxy within 3 days prior.
- D_like_major_HSS_declining_phase: outbreak 1-4 days after a local speed peak >= 600.0 km/s with non-increasing speed.

- Total outbreaks processed: 457
- Classifiable outbreaks: 184
- Unclassified outbreaks: 273

## Notes
- Existing ICME/CIR/HSS catalogs are used when present; otherwise transparent OMNI daily proxies are constructed.
- This branch is intentionally independent of the author outbreak labels and does not hard-code their classifications.
