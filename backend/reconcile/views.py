from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.compare import compare_records


class DisagreementsAPIView(APIView):
    """
    GET /api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH&sort=-value
    Returns reconciliation discrepancies scoped strictly to the requested tenant (org).
    """

    def get(self, request):
        org = request.query_params.get("org")
        if not org:
            return Response(
                {"error": "The 'org' query parameter is required (e.g. ?org=ORG-A or ?org=ORG-B)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org = org.strip().upper()
        # Verify valid tenant exists
        valid_orgs = set(Location.objects.values_list("org_id", flat=True).distinct())
        if org not in valid_orgs:
            return Response(
                {"error": f"Invalid org '{org}'. Valid tenants are: {', '.join(sorted(valid_orgs))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason_filter = request.query_params.get("reason", "").strip()
        sort_param = request.query_params.get("sort", "").strip()

        # 1. Fetch System A records strictly owned by this tenant in DB query
        a_records = SystemARecord.objects.filter(location__org_id=org).select_related("location")

        a_rows = {
            rec.record_id: {
                "total": rec.total_value,
                "location": rec.location_id,
                "org": rec.location.org_id,
                "date": str(rec.event_date),
                "state": rec.state,
            }
            for rec in a_records
        }

        # 2. Fetch System B entries associated with this tenant
        # A System B entry belongs to this org if:
        #  a) It points to a record_id owned by this org (matched via record_ref)
        #  b) OR it is an orphan (record_ref not in any A record) and its own location belongs to this org
        # Under no circumstance do we query or load records belonging to another org.
        all_a_record_ids = set(SystemARecord.objects.values_list("record_id", flat=True))
        org_a_record_ids = set(a_rows.keys())

        b_entries_query = SystemBEntry.objects.filter(
            Q(record_ref__in=org_a_record_ids) |
            (Q(location__org_id=org) & ~Q(record_ref__in=all_a_record_ids))
        ).select_related("location")

        b_rows = [
            {
                "entry_id": entry.entry_id,
                "record_ref_raw": entry.record_ref_raw,
                "ref": entry.record_ref,
                "value": entry.value,
                "location": entry.location_id,
                "org": entry.location.org_id,
                "date": str(entry.recorded_on),
                "label": entry.label,
            }
            for entry in b_entries_query
        ]

        # 3. Run comparison engine
        raw_disagreements = compare_records(a_rows, b_rows)

        # 4. Filter by reason if requested
        if reason_filter:
            raw_disagreements = [d for d in raw_disagreements if d["reason"] == reason_filter]

        # 5. Format outputs and sanitize against cross-org leakage
        formatted = []
        for d in raw_disagreements:
            # Trap row safeguard: Ensure location displayed to this org never reveals another tenant's location ID
            item_loc = d["location"]
            # If item location belongs to another org, redact it
            loc_obj = Location.objects.filter(location_id=item_loc).first()
            safe_location = item_loc
            if loc_obj and loc_obj.org_id != org:
                safe_location = "REDACTED"

            a_val = float(d["a_value"]) if d["a_value"] is not None else None
            b_val = float(d["b_value"]) if d["b_value"] is not None else None

            formatted.append({
                "reason": d["reason"],
                "record_id": d["record_id"],
                "location": safe_location,
                "a_value": a_val,
                "b_value": b_val,
                "entry_id": d.get("entry_id"),
                "details": d.get("details"),
            })

        # 6. Sort if requested
        if sort_param:
            reverse = sort_param.startswith("-")
            key_field = sort_param.lstrip("-")

            if key_field == "value":
                # Sort primarily by b_value, then a_value
                def get_sort_val(x):
                    v = x["b_value"] if x["b_value"] is not None else x["a_value"]
                    return v if v is not None else float("-inf" if not reverse else "inf")
                formatted.sort(key=get_sort_val, reverse=reverse)
            elif key_field in ("record_id", "reason", "location"):
                formatted.sort(key=lambda x: str(x.get(key_field) or ""), reverse=reverse)

        return Response(formatted, status=status.HTTP_200_OK)
