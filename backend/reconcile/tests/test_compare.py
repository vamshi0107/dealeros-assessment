from decimal import Decimal
import pytest
from reconcile.compare import compare_records
from reconcile.importer import normalize_ref, parse_amount


def test_clean_matching_row():
    """A matching pair produces zero disagreements."""
    a_rows = {
        "REC-1001": {
            "total": Decimal("100.00"),
            "location": "LOC-101",
            "org": "ORG-A",
            "date": "2026-03-01",
            "state": "CONFIRMED",
        }
    }
    b_rows = [
        {
            "entry_id": "ENT-1",
            "ref": "REC-1001",
            "value": Decimal("100.00"),
            "location": "LOC-101",
            "org": "ORG-A",
            "date": "2026-03-01",
            "label": "Regular entry",
        }
    ]
    disagreements = compare_records(a_rows, b_rows)
    assert disagreements == []


def test_missing_in_b():
    """An A record with no B entry is flagged as MISSING_IN_B."""
    a_rows = {
        "REC-1015": {
            "total": Decimal("41095.33"),
            "location": "LOC-103",
            "org": "ORG-A",
            "date": "2026-04-02",
            "state": "CONFIRMED",
        }
    }
    b_rows = []
    disagreements = compare_records(a_rows, b_rows)
    assert len(disagreements) == 1
    assert disagreements[0]["reason"] == "MISSING_IN_B"
    assert disagreements[0]["record_id"] == "REC-1015"
    assert disagreements[0]["a_value"] == Decimal("41095.33")


def test_orphan_in_b():
    """A B entry with an unknown reference is flagged as ORPHAN_IN_B."""
    a_rows = {}
    b_rows = [
        {
            "entry_id": "ENT/2026/4901",
            "ref": "REC-1999",
            "value": Decimal("41250.00"),
            "location": "LOC-102",
            "org": "ORG-A",
            "date": "2026-03-18",
            "label": "Entry for CAT-05",
        }
    ]
    disagreements = compare_records(a_rows, b_rows)
    assert len(disagreements) == 1
    assert disagreements[0]["reason"] == "ORPHAN_IN_B"
    assert disagreements[0]["record_id"] == "REC-1999"
    assert disagreements[0]["entry_id"] == "ENT/2026/4901"


def test_duplicate_in_b():
    """The same amount entered twice (or multi-entries not summing to total) is flagged as DUPLICATE_IN_B."""
    a_rows = {
        "REC-1042": {
            "total": Decimal("112837.06"),
            "location": "LOC-101",
            "org": "ORG-A",
            "date": "2026-03-04",
            "state": "CONFIRMED",
        }
    }
    b_rows = [
        {
            "entry_id": "ENT/2026/4042",
            "ref": "REC-1042",
            "value": Decimal("112837.06"),
            "location": "LOC-101",
            "org": "ORG-A",
            "date": "2026-03-04",
            "label": "Entry 1",
        },
        {
            "entry_id": "ENT/2026/4902",
            "ref": "REC-1042",
            "value": Decimal("112837.06"),
            "location": "LOC-101",
            "org": "ORG-A",
            "date": "2026-03-04",
            "label": "Duplicate Entry 2",
        },
    ]
    disagreements = compare_records(a_rows, b_rows)
    assert len(disagreements) == 1
    assert disagreements[0]["reason"] == "DUPLICATE_IN_B"
    assert disagreements[0]["record_id"] == "REC-1042"


def test_split_that_sums_is_not_an_error():
    """Two B entries that sum exactly to A's total (a split) must NOT be flagged as DUPLICATE_IN_B."""
    a_rows = {
        "REC-1055": {
            "total": Decimal("179877.32"),
            "location": "LOC-103",
            "org": "ORG-A",
            "date": "2026-03-14",
            "state": "CONFIRMED",
        }
    }
    b_rows = [
        {
            "entry_id": "ENT/2026/4055",
            "ref": "REC-1055",
            "value": Decimal("71950.93"),
            "location": "LOC-103",
            "org": "ORG-A",
            "date": "2026-03-14",
            "label": "Entry 1 of 2",
        },
        {
            "entry_id": "ENT/2026/4903",
            "ref": "REC-1055",
            "value": Decimal("107926.39"),
            "location": "LOC-103",
            "org": "ORG-A",
            "date": "2026-03-14",
            "label": "Entry part 2 of 2",
        },
    ]
    # Sum: 71950.93 + 107926.39 == 179877.32
    disagreements = compare_records(a_rows, b_rows)
    assert disagreements == []


def test_value_mismatch():
    """Different amounts between System A total_value and System B are flagged as VALUE_MISMATCH."""
    a_rows = {
        "REC-1003": {
            "total": Decimal("121388.01"),
            "location": "LOC-202",
            "org": "ORG-B",
            "date": "2026-03-04",
            "state": "CONFIRMED",
        }
    }
    b_rows = [
        {
            "entry_id": "ENT/2026/4003",
            "ref": "REC-1003",
            "value": Decimal("94834.38"),
            "location": "LOC-202",
            "org": "ORG-B",
            "date": "2026-03-04",
            "label": "Entry for CAT-03",
        }
    ]
    disagreements = compare_records(a_rows, b_rows)
    assert len(disagreements) == 1
    assert disagreements[0]["reason"] == "VALUE_MISMATCH"
    assert disagreements[0]["a_value"] == Decimal("121388.01")
    assert disagreements[0]["b_value"] == Decimal("94834.38")


def test_blank_value_flagged_not_treated_as_zero():
    """A blank B value is flagged as VALUE_MISMATCH and stored as None, never 0."""
    # Verifying parser helper
    assert parse_amount("") is None
    assert parse_amount("   ") is None
    assert parse_amount(None) is None

    a_rows = {
        "REC-1050": {
            "total": Decimal("160405.85"),
            "location": "LOC-202",
            "org": "ORG-B",
            "date": "2026-03-20",
            "state": "CONFIRMED",
        }
    }
    b_rows = [
        {
            "entry_id": "ENT/2026/4050",
            "ref": "REC-1050",
            "value": None,  # Blank value
            "location": "LOC-202",
            "org": "ORG-B",
            "date": "2026-03-20",
            "label": "Entry for CAT-03",
        }
    ]
    disagreements = compare_records(a_rows, b_rows)
    assert len(disagreements) == 1
    assert disagreements[0]["reason"] == "VALUE_MISMATCH"
    assert disagreements[0]["b_value"] is None
    assert disagreements[0]["b_value"] != Decimal("0.00")


def test_messy_references():
    """rec1034, ' REC - 1070 ', and 1112 normalize and match their records without error."""
    assert normalize_ref("rec1034") == "REC-1034"
    assert normalize_ref(" REC - 1070 ") == "REC-1070"
    assert normalize_ref("1112") == "REC-1112"

    a_rows = {
        "REC-1034": {"total": Decimal("84939.99"), "location": "LOC-101", "org": "ORG-A", "date": "2026-03-22", "state": "CONFIRMED"},
        "REC-1070": {"total": Decimal("1608.95"), "location": "LOC-202", "org": "ORG-B", "date": "2026-03-18", "state": "CONFIRMED"},
        "REC-1112": {"total": Decimal("52028.74"), "location": "LOC-101", "org": "ORG-A", "date": "2026-03-19", "state": "CONFIRMED"},
    }
    b_rows = [
        {"entry_id": "E1", "ref": normalize_ref("rec1034"), "value": Decimal("84939.99"), "location": "LOC-101", "org": "ORG-A", "date": "2026-03-22"},
        {"entry_id": "E2", "ref": normalize_ref(" REC - 1070 "), "value": Decimal("1608.95"), "location": "LOC-202", "org": "ORG-B", "date": "2026-03-18"},
        {"entry_id": "E3", "ref": normalize_ref("1112"), "value": Decimal("52028.74"), "location": "LOC-101", "org": "ORG-A", "date": "2026-03-19"},
    ]
    disagreements = compare_records(a_rows, b_rows)
    assert disagreements == []


def test_indian_comma_amount_parsing():
    """Indian number formatting '1,25,400.00' is parsed into Decimal('125400.00')."""
    parsed = parse_amount("1,25,400.00")
    assert parsed == Decimal("125400.00")
