# Architecture & Engineering Decisions

## Decision: compare B's value with A's total_value
-Rejected: compare with base_value
-Why: Inspection of matched rows confirms System B records the gross transaction amount corresponding to System A's total_value (base_value + adjustment); comparing to base_value would falsely flag normal adjustments as value mismatches.

## Decision: treat blank values as None/null rather than zero
-Rejected: default or coerce blank values to Decimal("0.00")
-Why: A blank value in System B represents missing/unknown data rather than an event value of zero; coercing blank to 0 alters audit truth and misrepresents the financial record.

## Decision: treat split entries summing to total_value as valid non-errors
-Rejected: flag any record with multiple System B entries as DUPLICATE_IN_B
-Why: Business transactions can be paid in installments (e.g. REC-1055 with "part 2 of 2"); when the sum of B entries equals A's total_value exactly (179877.32), it is a legitimate split payment and not a duplication error.

## Decision: retain VOIDED records at their stated ledger amount without coercing to zero
-Rejected: force total_value of VOIDED records to Decimal("0.00") or discard them during import
-Why: System A preserves the historical audit amount for voided transactions; since System B records the matching amount (57092.35), keeping the ledger amount avoids false numeric differences while allowing downstream business rules to inspect the state column.

## Decision: redact foreign location IDs on the cross-tenant trap row (REC-1077)
-Rejected: display System B's location (LOC-201) to ORG-A, or display REC-1077 to ORG-B
-Why: In REC-1077, System A is located at LOC-102 (ORG-A) but System B recorded it at LOC-201 (ORG-B); showing LOC-201 to ORG-A leaks ORG-B's internal branch topology, so the foreign location is redacted and ownership is scoped strictly by System A's originating tenant.

## Decision: normalize reference variations using regex digit extraction
-Rejected: strict string matching or manual case-by-case mapping
-Why: System B contains reference variations ('rec1034', ' REC - 1070 ', '1112'); extracting contiguous digits into the canonical format 'REC-<digits>' robustly reconciles all variations without modifying raw original values.

## Decision: omit database Foreign Key from System B to System A
-Rejected: ForeignKey(SystemARecord, on_delete=models.CASCADE) on SystemBEntry.record_ref
-Why: System B contains orphan entries (e.g. ENT/2026/4901 referencing non-existent REC-1999) and split entries; a relational FK constraint would cause database integrity errors during ingestion of valid dirty rows.

## Decision: surface location and date discrepancies as distinct informational categories
-Rejected: ignoring location/date differences or conflating them with financial VALUE_MISMATCH
-Why: Ledger reconciliation extends beyond amounts; differing branches or booking dates represent operational deviations that audit teams must inspect independently from dollar imbalances.

## Decision: use DecimalField over IEEE 754 float across all monetary columns
-Rejected: float or FloatField
-Why: Binary floating-point representation causes precision loss (e.g. 0.1 + 0.2 != 0.3); DecimalField ensures exact two-decimal-place arithmetic critical for financial comparisons.

## Decision: use embedded SQLite for zero-configuration portability
-Rejected: PostgreSQL or MySQL requiring external server daemon
-Why: SQLite ships natively with Python and Django, enabling the reviewer to clone and run the application instantly with zero external infrastructure setup.
