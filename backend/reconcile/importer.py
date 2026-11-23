import csv
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.db import transaction
from reconcile.models import Location, SystemARecord, SystemBEntry

logger = logging.getLogger(__name__)


def normalize_ref(raw):
    """
    Normalizes 'rec1034', ' REC - 1070 ', '1112' -> 'REC-1034', 'REC-1070', 'REC-1112'.
    Returns None if no digits are found.
    """
    if not raw:
        return None
    m = re.search(r"\d+", str(raw))
    return f"REC-{m.group()}" if m else None


def parse_amount(raw):
    """
    Parses amount string to Decimal, removing formatting commas (including Indian numbering e.g. '1,25,400.00').
    Blank or unparseable junk -> None, NEVER 0.
    """
    s = (str(raw) if raw is not None else "").strip().replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        logger.warning(f"Failed to parse amount '{raw}' into Decimal; stored as None.")
        return None


def parse_date(raw):
    """
    Parses YYYY-MM-DD date string.
    """
    s = (str(raw) if raw is not None else "").strip()
    return s if s else None


def import_all_csvs(data_dir=None):
    """
    Imports locations.csv, system_a.csv, and system_b.csv from data_dir.
    Idempotent: uses update_or_create on primary keys.
    Returns a dictionary of counts and statistics.
    """
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
    else:
        data_dir = Path(data_dir)

    loc_path = data_dir / "locations.csv"
    a_path = data_dir / "system_a.csv"
    b_path = data_dir / "system_b.csv"

    stats = {
        "locations_read": 0,
        "locations_saved": 0,
        "a_read": 0,
        "a_saved": 0,
        "b_read": 0,
        "b_saved": 0,
        "b_values_empty": 0,
        "b_refs_cleaned": 0,
    }

    # 1. Import Locations
    with open(loc_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["locations_read"] += 1
            cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
            loc_id = cleaned_row.get("location_id")
            org_id = cleaned_row.get("org_id")
            name = cleaned_row.get("location_name") or cleaned_row.get("name") or loc_id

            Location.objects.update_or_create(
                location_id=loc_id,
                defaults={"org_id": org_id, "name": name},
            )
            stats["locations_saved"] += 1

    # Map locations for quick lookup
    location_cache = {loc.location_id: loc for loc in Location.objects.all()}

    # 2. Import System A Records
    with open(a_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["a_read"] += 1
            cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
            record_id = cleaned_row["record_id"]
            loc_id = cleaned_row["location_id"]
            location = location_cache.get(loc_id)
            if not location:
                # Create a placeholder location if unknown
                location, _ = Location.objects.get_or_create(
                    location_id=loc_id,
                    defaults={"org_id": "UNKNOWN", "name": f"Location {loc_id}"}
                )
                location_cache[loc_id] = location

            actor_id = cleaned_row.get("actor_id") or None
            base_value = parse_amount(cleaned_row.get("base_value")) or Decimal("0.00")
            adjustment = parse_amount(cleaned_row.get("adjustment")) or Decimal("0.00")
            total_value = parse_amount(cleaned_row.get("total_value"))
            if total_value is None:
                total_value = base_value + adjustment

            SystemARecord.objects.update_or_create(
                record_id=record_id,
                defaults={
                    "location": location,
                    "event_date": parse_date(cleaned_row.get("event_date")),
                    "category_code": cleaned_row.get("category_code", ""),
                    "actor_id": actor_id,
                    "base_value": base_value,
                    "adjustment": adjustment,
                    "total_value": total_value,
                    "state": cleaned_row.get("state", "CONFIRMED"),
                },
            )
            stats["a_saved"] += 1

    # 3. Import System B Entries
    with open(b_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["b_read"] += 1
            cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
            entry_id = cleaned_row["entry_id"]
            raw_ref = cleaned_row.get("record_ref", "")
            norm_ref = normalize_ref(raw_ref)

            if raw_ref != norm_ref and raw_ref != "":
                stats["b_refs_cleaned"] += 1

            loc_id = cleaned_row["location_id"]
            location = location_cache.get(loc_id)
            if not location:
                location, _ = Location.objects.get_or_create(
                    location_id=loc_id,
                    defaults={"org_id": "UNKNOWN", "name": f"Location {loc_id}"}
                )
                location_cache[loc_id] = location

            val_raw = cleaned_row.get("value", "")
            parsed_val = parse_amount(val_raw)
            if parsed_val is None:
                stats["b_values_empty"] += 1

            SystemBEntry.objects.update_or_create(
                entry_id=entry_id,
                defaults={
                    "record_ref_raw": raw_ref,
                    "record_ref": norm_ref,
                    "location": location,
                    "recorded_on": parse_date(cleaned_row.get("recorded_on")),
                    "value_raw": val_raw,
                    "value": parsed_val,
                    "label": cleaned_row.get("label", ""),
                },
            )
            stats["b_saved"] += 1

    return stats
