from decimal import Decimal
from typing import Dict, List, Optional, Any


def compare_records(
    a_rows: Dict[str, Dict[str, Any]],
    b_rows: List[Dict[str, Any]],
    include_location_mismatch: bool = True,
    include_date_mismatch: bool = True,
) -> List[Dict[str, Any]]:
    """
    Pure Python reconciliation comparison logic.
    Decoupled from database, ORM, and HTTP layers.

    :param a_rows: Dict of {record_id: {'total': Decimal, 'location': str, 'org': str, 'date': str, 'state': str}}
    :param b_rows: List of [{'entry_id': str, 'ref': str, 'value': Optional[Decimal], 'location': str, 'org': str, 'date': str, 'label': str}]
    :param include_location_mismatch: Whether to flag location differences as disagreements
    :param include_date_mismatch: Whether to flag date differences as disagreements
    :return: List of disagreement dicts:
             [{'reason': str, 'record_id': str, 'location': str, 'a_value': Optional[Decimal], 'b_value': Optional[Decimal], 'entry_id': Optional[str], 'details': str}]
    """
    disagreements = []
    by_ref: Dict[str, List[Dict[str, Any]]] = {}

    # Group B entries by normalized reference
    for entry in b_rows:
        ref = entry.get("ref")
        if ref:
            by_ref.setdefault(ref, []).append(entry)
        else:
            # Entry has no valid reference -> Orphan
            disagreements.append({
                "reason": "ORPHAN_IN_B",
                "record_id": entry.get("record_ref_raw") or "UNKNOWN",
                "location": entry.get("location"),
                "a_value": None,
                "b_value": entry.get("value"),
                "entry_id": entry.get("entry_id"),
                "org": entry.get("org"),
                "details": f"System B entry {entry.get('entry_id')} has no valid record reference.",
            })

    # 1. Identify Orphan entries in B (referenced record not in System A)
    for ref, entries in by_ref.items():
        if ref not in a_rows:
            for e in entries:
                disagreements.append({
                    "reason": "ORPHAN_IN_B",
                    "record_id": ref,
                    "location": e.get("location"),
                    "a_value": None,
                    "b_value": e.get("value"),
                    "entry_id": e.get("entry_id"),
                    "org": e.get("org"),
                    "details": f"System B entry {e.get('entry_id')} references '{ref}' which does not exist in System A.",
                })

    # 2. Check each System A record against B entries
    for rid, a in a_rows.items():
        entries = by_ref.get(rid, [])
        a_total = a.get("total")
        a_loc = a.get("location")
        a_org = a.get("org")
        a_date = a.get("date")

        # Check MISSING_IN_B
        if not entries:
            disagreements.append({
                "reason": "MISSING_IN_B",
                "record_id": rid,
                "location": a_loc,
                "a_value": a_total,
                "b_value": None,
                "entry_id": None,
                "org": a_org,
                "details": f"System A record {rid} has no corresponding entry in System B.",
            })
            continue

        # Check for None/Blank values in B entries
        vals = [e.get("value") for e in entries]
        if any(v is None for v in vals):
            for e in entries:
                if e.get("value") is None:
                    disagreements.append({
                        "reason": "VALUE_MISMATCH",
                        "record_id": rid,
                        "location": a_loc,
                        "a_value": a_total,
                        "b_value": None,
                        "entry_id": e.get("entry_id"),
                        "org": a_org,
                        "details": f"System B entry {e.get('entry_id')} has a blank/null value (unknown).",
                    })
            continue

        # Check multiple B entries for a single A record: Split vs. Duplicate
        if len(entries) > 1:
            total_b_val = sum(vals)
            # A split that sums exactly to A's total is valid and NOT an error
            if total_b_val != a_total:
                disagreements.append({
                    "reason": "DUPLICATE_IN_B",
                    "record_id": rid,
                    "location": a_loc,
                    "a_value": a_total,
                    "b_value": total_b_val,
                    "entry_id": ", ".join(e.get("entry_id", "") for e in entries),
                    "org": a_org,
                    "details": f"Record {rid} has {len(entries)} entries in System B summing to {total_b_val}, which does not equal System A total {a_total}.",
                })
            # Continue checking location/date discrepancies for split/duplicate if needed
            continue

        # Single entry in B: Compare values
        e = entries[0]
        b_val = e.get("value")
        b_loc = e.get("location")
        b_date = e.get("date")

        if b_val != a_total:
            disagreements.append({
                "reason": "VALUE_MISMATCH",
                "record_id": rid,
                "location": a_loc,
                "a_value": a_total,
                "b_value": b_val,
                "entry_id": e.get("entry_id"),
                "org": a_org,
                "details": f"Value mismatch for {rid}: System A={a_total}, System B={b_val} (diff={b_val - a_total}).",
            })

        # Location mismatch
        if include_location_mismatch and b_loc != a_loc:
            # Handle potential cross-org leak: do not expose another org's location ID
            b_org = e.get("org")
            safe_b_loc = b_loc if b_org == a_org else "REDACTED_CROSS_ORG"
            disagreements.append({
                "reason": "LOCATION_MISMATCH",
                "record_id": rid,
                "location": a_loc,
                "a_value": a_total,
                "b_value": b_val,
                "entry_id": e.get("entry_id"),
                "org": a_org,
                "details": f"Location mismatch for {rid}: System A={a_loc}, System B={safe_b_loc}.",
            })

        # Date mismatch
        if include_date_mismatch and b_date != a_date:
            disagreements.append({
                "reason": "DATE_MISMATCH",
                "record_id": rid,
                "location": a_loc,
                "a_value": a_total,
                "b_value": b_val,
                "entry_id": e.get("entry_id"),
                "org": a_org,
                "details": f"Date mismatch for {rid}: System A event_date={a_date}, System B recorded_on={b_date}.",
            })

    return disagreements
