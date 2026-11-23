from django.db import models


class Location(models.Model):
    """
    Authoritative source mapping physical locations to tenants (orgs).
    LOC-101 to LOC-103 belong to ORG-A.
    LOC-201 and LOC-202 belong to ORG-B.
    """
    location_id = models.CharField(max_length=50, primary_key=True)
    org_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ['location_id']

    def __str__(self):
        return f"{self.location_id} ({self.org_id}) - {self.name}"


class SystemARecord(models.Model):
    """
    One row per business event as recorded by System A.
    """
    record_id = models.CharField(max_length=50, primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='system_a_records')
    event_date = models.DateField()
    category_code = models.CharField(max_length=50)
    actor_id = models.CharField(max_length=50, null=True, blank=True)
    base_value = models.DecimalField(max_digits=14, decimal_places=2)
    adjustment = models.DecimalField(max_digits=14, decimal_places=2)
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    state = models.CharField(max_length=50)  # CONFIRMED or VOIDED

    class Meta:
        ordering = ['record_id']

    def __str__(self):
        return f"{self.record_id} [{self.state}] total={self.total_value}"


class SystemBEntry(models.Model):
    """
    One row per entry in System B.
    record_ref points back to System A's record_id.
    Note: No Foreign Key to SystemARecord is used because orphan entries in B
    reference record IDs that do not exist in System A, which would fail FK constraints.
    Multiple B entries can also reference the same A record (splits or duplicates).
    """
    entry_id = models.CharField(max_length=50, primary_key=True)
    record_ref_raw = models.CharField(max_length=100, null=True, blank=True)
    record_ref = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='system_b_entries')
    recorded_on = models.DateField()
    value_raw = models.CharField(max_length=100, null=True, blank=True)
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    label = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['entry_id']

    def __str__(self):
        return f"{self.entry_id} -> {self.record_ref} value={self.value}"
