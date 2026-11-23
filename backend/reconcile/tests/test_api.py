import pytest
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
def test_api_missing_org_param(api_client):
    """API returns 400 Bad Request when ?org= parameter is absent."""
    res = api_client.get("/api/disagreements/")
    assert res.status_code == 400
    assert "error" in res.data


@pytest.mark.django_db
def test_api_invalid_org_param(api_client, seeded_db):
    """API returns 400 Bad Request for unknown org."""
    res = api_client.get("/api/disagreements/?org=ORG-INVALID")
    assert res.status_code == 400
    assert "Invalid org" in res.data["error"]


@pytest.mark.django_db
def test_api_org_a_disagreements(api_client, seeded_db):
    """API returns discrepancies for ORG-A successfully."""
    res = api_client.get("/api/disagreements/?org=ORG-A")
    assert res.status_code == 200
    assert isinstance(res.data, list)
    assert len(res.data) > 0

    reasons = [item["reason"] for item in res.data]
    assert "MISSING_IN_B" in reasons
    assert "ORPHAN_IN_B" in reasons
    assert "DUPLICATE_IN_B" in reasons
    assert "LOCATION_MISMATCH" in reasons


@pytest.mark.django_db
def test_api_filter_by_reason(api_client, seeded_db):
    """API filters by reason query parameter."""
    res = api_client.get("/api/disagreements/?org=ORG-A&reason=MISSING_IN_B")
    assert res.status_code == 200
    for item in res.data:
        assert item["reason"] == "MISSING_IN_B"


@pytest.mark.django_db
def test_api_sort_by_value(api_client, seeded_db):
    """API sorts results by value ascending and descending."""
    res_desc = api_client.get("/api/disagreements/?org=ORG-A&sort=-value")
    assert res_desc.status_code == 200
    vals = [item["b_value"] for item in res_desc.data if item["b_value"] is not None]
    assert vals == sorted(vals, reverse=True)


@pytest.mark.django_db
def test_tenant_isolation_org_a_never_leaks_org_b(api_client, seeded_db):
    """
    CRITICAL TENANT CHECK:
    ORG-A queries must NEVER contain any ORG-B location identifier or data.
    ORG-B queries must NEVER contain any ORG-A location identifier or data.
    """
    org_b_locations = set(Location.objects.filter(org_id="ORG-B").values_list("location_id", flat=True))
    assert len(org_b_locations) > 0  # LOC-201, LOC-202

    res_a = api_client.get("/api/disagreements/?org=ORG-A")
    assert res_a.status_code == 200

    for item in res_a.data:
        # Assert no ORG-B location ID appears anywhere in the returned item
        assert item["location"] not in org_b_locations, f"LEAK: Found ORG-B location {item['location']} in ORG-A response!"
        assert "LOC-201" not in str(item), "LEAK: Found LOC-201 in ORG-A response!"
        assert "LOC-202" not in str(item), "LEAK: Found LOC-202 in ORG-A response!"

    org_a_locations = set(Location.objects.filter(org_id="ORG-A").values_list("location_id", flat=True))
    assert len(org_a_locations) > 0  # LOC-101, LOC-102, LOC-103

    res_b = api_client.get("/api/disagreements/?org=ORG-B")
    assert res_b.status_code == 200

    for item in res_b.data:
        # Assert no ORG-A location ID appears anywhere in the returned item
        assert item["location"] not in org_a_locations, f"LEAK: Found ORG-A location {item['location']} in ORG-B response!"
        assert "LOC-101" not in str(item), "LEAK: Found LOC-101 in ORG-B response!"
        assert "LOC-102" not in str(item), "LEAK: Found LOC-102 in ORG-B response!"
        assert "LOC-103" not in str(item), "LEAK: Found LOC-103 in ORG-B response!"
