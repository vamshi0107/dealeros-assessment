# Notes on Data Problems & Anomalies

Identified from raw specifications and sample analysis of the three datasets:

## 1. File Summary
- `locations.csv`: 5 rows (`location_id`, `org_id`)
  - `LOC-101`, `LOC-102`, `LOC-103` belong to `ORG-A`
  - `LOC-201`, `LOC-202` belong to `ORG-B`
- `system_a.csv`: 120 rows (`record_id`, `location_id`, `event_date`, `base_value`, `adjustment`, `total_value`, `state`)
- `system_b.csv`: 121 rows (`entry_id`, `record_ref`, `location_id`, `recorded_on`, `value`)

## 2. Intentional Quirks & Edge Cases
1. **Row Count Discrepancy:**
   - System A has 120 rows; System B has 121 rows.
   - Discrepancy is caused by missing entries, duplicates, split amounts, and an orphan in B.
   - All 121 rows must be preserved during ingestion.
2. **Comparison Target:**
   - System B `value` must be compared with System A's `total_value` (`base_value + adjustment`), not `base_value`.
3. **Reference Variations in System B:**
   - Format variations include: `rec1034`, `REC - 1070` (with whitespace), or raw digits `1112`.
   - Normalization rule: extract digits and normalize to `REC-<digits>`.
4. **Invalid & Formatted Values:**
   - One B value is blank: must be stored as `null`, never `0` (blank = unknown value).
   - One B value is formatted with Indian-style grouping (e.g., `1,25,400.00`): commas must be stripped prior to `Decimal` conversion (`125400.00`).
5. **Missing Fields in System A:**
   - One A record has an empty `actor_id`: store as `null`.
6. **Orphan Entries in System B:**
   - A B entry points to a `record_ref` not present in System A. Must NOT enforce a database Foreign Key from B to A.
7. **Split Payments vs. Duplicates:**
   - Multiple B entries pointing to the same record:
     - If the sum of values equals A's `total_value` (e.g. marked "part 2 of 2"), this is a split, not an error.
     - If the sum does not equal A's `total_value`, flag as `DUPLICATE_IN_B`.
8. **Record State in System A:**
   - System A contains a `state` column (`CONFIRMED` or `VOIDED`).
9. **Cross-Tenant Trap Row:**
   - A record exists where System A places it at an `ORG-A` location, but System B places it at an `ORG-B` location.
   - Cross-tenant data leak must be strictly prevented.
