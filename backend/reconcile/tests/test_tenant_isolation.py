import pytest
import json
from rest_framework.test import APIClient
from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.importer import import_all_csvs


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def seeded_db(db):
    """Seed the database with real imported CSV data."""
    import_all_csvs()


@pytest.mark.django_db
class TestTenantIsolation:
    """
    Exhaustive tenant isolation test suite verifying Section 7 requirements:
    'ORG-A users must never see anything that belongs to ORG-B, and the reverse.'
    """

    def test_strict_database_filtering_org_a(self, api_client, seeded_db):
        """Verify that ORG-A responses contain zero ORG-B locations or records."""
        org_b_locations = set(Location.objects.filter(org_id="ORG-B").values_list("location_id", flat=True))
        assert "LOC-201" in org_b_locations
        assert "LOC-202" in org_b_locations

        res = api_client.get("/api/disagreements/?org=ORG-A")
        assert res.status_code == 200

        payload_str = json.dumps(res.data)
        for loc in org_b_locations:
            assert loc not in payload_str, f"CRITICAL: Tenant leak detected! {loc} found in ORG-A response."

    def test_strict_database_filtering_org_b(self, api_client, seeded_db):
        """Verify that ORG-B responses contain zero ORG-A locations or records."""
        org_a_locations = set(Location.objects.filter(org_id="ORG-A").values_list("location_id", flat=True))
        assert "LOC-101" in org_a_locations
        assert "LOC-102" in org_a_locations
        assert "LOC-103" in org_a_locations

        res = api_client.get("/api/disagreements/?org=ORG-B")
        assert res.status_code == 200

        payload_str = json.dumps(res.data)
        for loc in org_a_locations:
            assert loc not in payload_str, f"CRITICAL: Tenant leak detected! {loc} found in ORG-B response."

    def test_trap_row_rec_1077_handling(self, api_client, seeded_db):
        """
        The Trap Row:
        REC-1077 exists in System A at LOC-102 (ORG-A), but System B has it at LOC-201 (ORG-B).
        1. When queried as ORG-A, REC-1077 must show its own location (LOC-102).
           Under no circumstances may LOC-201 or ORG-B be exposed.
        2. When queried as ORG-B, REC-1077 must NOT be returned, as ORG-B does not own the primary record.
        """
        # Query as ORG-A
        res_a = api_client.get("/api/disagreements/?org=ORG-A")
        assert res_a.status_code == 200
        trap_items_a = [item for item in res_a.data if item["record_id"] == "REC-1077"]
        assert len(trap_items_a) > 0, "Expected REC-1077 to be reported to ORG-A"

        for item in trap_items_a:
            assert item["location"] == "LOC-102", "ORG-A must only see its own location LOC-102"
            assert "LOC-201" not in str(item), "CRITICAL: Foreign location LOC-201 leaked to ORG-A!"
            assert "ORG-B" not in str(item), "CRITICAL: Foreign tenant ORG-B leaked to ORG-A!"

        # Query as ORG-B
        res_b = api_client.get("/api/disagreements/?org=ORG-B")
        assert res_b.status_code == 200
        trap_items_b = [item for item in res_b.data if item["record_id"] == "REC-1077"]
        assert len(trap_items_b) == 0, "REC-1077 does not belong to ORG-B and must not be visible to ORG-B."

    def test_orphan_scoping_by_own_location(self, api_client, seeded_db):
        """
        Orphan B entry ENT/2026/4901 has no A record.
        Its org is determined solely via its own location (LOC-102 -> ORG-A).
        It must appear in ORG-A and never in ORG-B.
        """
        res_a = api_client.get("/api/disagreements/?org=ORG-A")
        assert res_a.status_code == 200
        orphan_a = [item for item in res_a.data if item.get("entry_id") == "ENT/2026/4901"]
        assert len(orphan_a) == 1
        assert orphan_a[0]["reason"] == "ORPHAN_IN_B"

        res_b = api_client.get("/api/disagreements/?org=ORG-B")
        assert res_b.status_code == 200
        orphan_b = [item for item in res_b.data if item.get("entry_id") == "ENT/2026/4901"]
        assert len(orphan_b) == 0
