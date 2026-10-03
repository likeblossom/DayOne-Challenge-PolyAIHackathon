# Image/CSV correspondence audit

This derived dataset leaves all organizer files unchanged. It contains 80 uniquely renamed clean synthetic registry pages and five degraded JPG examples. Duplicate PNG copies were omitted.

No image patient exactly matches any row in `maternal_registry_synthetic.csv` across the nine compared clinical fields. Consequently, `csv_record_id` is blank and `match_status` is `no_exact_csv_match`; nearest CSV IDs are diagnostics only and must not be used as labels. Clinical labels were verified from the image registry pages. Direct identifiers are deliberately excluded from the CSV.
