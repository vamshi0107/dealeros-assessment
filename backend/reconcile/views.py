import os
from decimal import Decimal
from django.core.management import call_command
from django.db.models import Q
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from reconcile.models import Location, SystemARecord, SystemBEntry
from reconcile.compare import compare_records
from reconcile.importer import import_all_csvs


def ensure_initialized():
    """
    Ensures the SQLite database is migrated and populated with CSV records.
    Essential for serverless environments (e.g. Vercel) where /tmp/db.sqlite3
    starts fresh on a cold start.
    """
    try:
        if Location.objects.count() == 0:
            import_all_csvs()
    except Exception:
        try:
            call_command("migrate", interactive=False)
            import_all_csvs()
        except Exception as e:
            print(f"Initialization error: {e}")


class DisagreementsAPIView(APIView):
    """
    GET /api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH&sort=-value
    Returns reconciliation discrepancies scoped strictly to the requested tenant (org).
    """

    def get(self, request):
        ensure_initialized()

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
            item_loc = d["location"]
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
                def get_sort_val(x):
                    v = x["b_value"] if x["b_value"] is not None else x["a_value"]
                    return v if v is not None else float("-inf" if not reverse else "inf")
                formatted.sort(key=get_sort_val, reverse=reverse)
            elif key_field in ("record_id", "reason", "location"):
                formatted.sort(key=lambda x: str(x.get(key_field) or ""), reverse=reverse)

        return Response(formatted, status=status.HTTP_200_OK)


def home_view(request):
    """
    Renders the live interactive DealerOS Reconciliation Console directly at root '/'.
    Ensures that visitors on cloud deployments (such as Vercel) can interact with the app immediately.
    """
    ensure_initialized()

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DealerOS - Ledger Reconciliation</title>
  <style>
    :root {
      --primary: #2563eb;
      --slate-900: #0f172a;
      --slate-800: #1e293b;
      --slate-700: #334155;
      --slate-600: #475569;
      --slate-500: #64748b;
      --slate-400: #94a3b8;
      --slate-300: #cbd5e1;
      --slate-200: #e2e8f0;
      --slate-100: #f1f5f9;
      --slate-50: #f8fafc;
      --font-mono: 'SF Mono', 'Fira Code', 'Roboto Mono', Menlo, Consolas, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background-color: var(--slate-50); color: var(--slate-800); font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, sans-serif; line-height: 1.5; }
    .top-navbar { background: var(--slate-900); color: white; padding: 0.875rem 2rem; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
    .nav-container { max-width: 1320px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
    .brand-section { display: flex; align-items: center; gap: 0.85rem; }
    .brand-logo { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: white; font-weight: 800; font-size: 1.05rem; padding: 0.35rem 0.65rem; border-radius: 6px; }
    .brand-titles h1 { font-size: 1.15rem; font-weight: 700; color: #f8fafc; }
    .brand-titles p { font-size: 0.775rem; color: var(--slate-400); margin-top: 2px; }
    .system-status { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--slate-300); background: rgba(255, 255, 255, 0.08); padding: 0.35rem 0.85rem; border-radius: 9999px; }
    .pulse-dot { width: 8px; height: 8px; background-color: #10b981; border-radius: 50%; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.35); }
    .main-content { max-width: 1320px; width: 100%; margin: 1.75rem auto; padding: 0 1.5rem; }
    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .metric-card { background: white; border: 1px solid var(--slate-200); border-radius: 10px; padding: 1.15rem 1.25rem; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04); }
    .metric-label { font-size: 0.775rem; font-weight: 600; text-transform: uppercase; color: var(--slate-500); margin-bottom: 0.35rem; }
    .metric-value { font-size: 1.65rem; font-weight: 700; color: var(--slate-900); }
    .metric-sub { font-size: 0.75rem; color: var(--slate-400); margin-top: 0.2rem; }
    .toolbar-card { background: white; border: 1px solid var(--slate-200); border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 1.25rem; }
    .controls-left { display: flex; flex-wrap: wrap; align-items: center; gap: 1.5rem; }
    .control-item { display: flex; align-items: center; gap: 0.65rem; }
    .control-item label { font-size: 0.825rem; font-weight: 600; color: var(--slate-600); }
    select { padding: 0.55rem 1rem; border: 1px solid var(--slate-300); border-radius: 7px; font-size: 0.875rem; font-weight: 500; background: white; cursor: pointer; }
    .tenant-pill { font-size: 0.8rem; font-weight: 600; background: #eff6ff; color: var(--primary); padding: 0.4rem 0.85rem; border-radius: 6px; border: 1px solid rgba(37, 99, 235, 0.2); }
    .table-container { background: white; border: 1px solid var(--slate-200); border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05); }
    table { width: 100%; border-collapse: separate; border-spacing: 0; text-align: left; }
    th { background: #f8fafc; color: var(--slate-600); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 0.95rem 1.25rem; border-bottom: 1px solid var(--slate-200); }
    th.sortable { cursor: pointer; user-select: none; }
    th.sortable:hover { color: var(--primary); background: var(--slate-100); }
    td { padding: 1rem 1.25rem; border-bottom: 1px solid var(--slate-100); font-size: 0.875rem; color: var(--slate-700); vertical-align: middle; }
    tr:hover td { background-color: #f8fafc; }
    .mono { font-family: var(--font-mono); font-size: 0.85rem; }
    .record-id { font-family: var(--font-mono); font-weight: 600; color: var(--slate-900); background: var(--slate-100); padding: 0.2rem 0.45rem; border-radius: 4px; border: 1px solid var(--slate-200); }
    .badge { display: inline-flex; padding: 0.3rem 0.7rem; border-radius: 9999px; font-size: 0.725rem; font-weight: 600; }
    .badge-missing { background: #fff1f2; color: #be123c; border: 1px solid #fecdd3; }
    .badge-orphan { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
    .badge-duplicate { background: #faf5ff; color: #7e22ce; border: 1px solid #e9d5ff; }
    .badge-mismatch { background: #fff7ed; color: #c2410c; border: 1px solid #ffedd5; }
    .badge-location { background: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd; }
    .badge-date { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }
    .diff-pos { color: #15803d; font-weight: 600; font-family: var(--font-mono); }
    .diff-neg { color: #b91c1c; font-weight: 600; font-family: var(--font-mono); }
    .diff-neutral { color: var(--slate-400); font-family: var(--font-mono); }
  </style>
</head>
<body>
  <div class="top-navbar">
    <div class="nav-container">
      <div class="brand-section">
        <div class="brand-logo">DealerOS</div>
        <div class="brand-titles">
          <h1>Ledger Reconciliation Console</h1>
          <p>Dual-Ledger Audit & Multi-Tenant Discrepancy Detector</p>
        </div>
      </div>
      <div class="system-status">
        <span class="pulse-dot"></span>
        <span>Reconciliation Engine Active</span>
      </div>
    </div>
  </div>

  <div class="main-content">
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Total Discrepancies</div>
        <div class="metric-value" id="metric-total">0</div>
        <div class="metric-sub">Across active filters</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Value Imbalances</div>
        <div class="metric-value" id="metric-values">0</div>
        <div class="metric-sub">Differing transaction sums</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Missing & Orphans</div>
        <div class="metric-value" id="metric-missing">0</div>
        <div class="metric-sub">Unmatched ledger entries</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Active Tenant Scoping</div>
        <div class="metric-value" style="color:#2563eb;" id="metric-org">ORG-A</div>
        <div class="metric-sub">Zero cross-tenant leakage</div>
      </div>
    </div>

    <div class="toolbar-card">
      <div class="controls-left">
        <div class="control-item">
          <label for="org-select">Tenant Organization:</label>
          <select id="org-select" onchange="loadData()">
            <option value="ORG-A">ORG-A (HQ & Branches 101-103)</option>
            <option value="ORG-B">ORG-B (Branches 201-202)</option>
          </select>
        </div>
        <div class="control-item">
          <label for="reason-filter">Disagreement Category:</label>
          <select id="reason-filter" onchange="loadData()">
            <option value="">All Disagreement Types</option>
            <option value="MISSING_IN_B">Missing in System B</option>
            <option value="ORPHAN_IN_B">Orphan in System B</option>
            <option value="DUPLICATE_IN_B">Duplicate in System B</option>
            <option value="VALUE_MISMATCH">Value Mismatch</option>
            <option value="LOCATION_MISMATCH">Location Mismatch</option>
            <option value="DATE_MISMATCH">Date Mismatch</option>
          </select>
        </div>
      </div>
      <div class="toolbar-right">
        <span class="tenant-pill" id="tenant-pill">Scope: ORG-A (Isolated DB Query)</span>
      </div>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Discrepancy Category</th>
            <th>Record Identifier</th>
            <th>Location</th>
            <th>System A Value</th>
            <th class="sortable" onclick="toggleSort()">System B Value <span id="sort-icon">⇅</span></th>
            <th>Variance (B − A)</th>
          </tr>
        </thead>
        <tbody id="table-body">
          <tr><td colspan="6" style="text-align:center; padding:3rem; color:#94a3b8;">Loading reconciliation data...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <script>
    let currentSort = '';
    const REASON_LABELS = {
      MISSING_IN_B: 'Missing in System B',
      ORPHAN_IN_B: 'Orphan in System B',
      DUPLICATE_IN_B: 'Duplicate in System B',
      VALUE_MISMATCH: 'Value Mismatch',
      LOCATION_MISMATCH: 'Location Mismatch',
      DATE_MISMATCH: 'Date Mismatch'
    };

    function getBadge(reason) {
      const cls = {
        MISSING_IN_B: 'badge-missing',
        ORPHAN_IN_B: 'badge-orphan',
        DUPLICATE_IN_B: 'badge-duplicate',
        VALUE_MISMATCH: 'badge-mismatch',
        LOCATION_MISMATCH: 'badge-location',
        DATE_MISMATCH: 'badge-date'
      }[reason] || '';
      return `<span class="badge ${cls}">${REASON_LABELS[reason] || reason}</span>`;
    }

    function formatAmount(val) {
      if (val === null || val === undefined) return '<span style="color:#94a3b8">—</span>';
      return Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function calcDiff(aVal, bVal) {
      if (aVal === null || aVal === undefined || bVal === null || bVal === undefined) return '<span style="color:#94a3b8">—</span>';
      const diff = Number(bVal) - Number(aVal);
      const str = Math.abs(diff).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      if (diff > 0.001) return `<span class="diff-pos">+${str}</span>`;
      if (diff < -0.001) return `<span class="diff-neg">-${str}</span>`;
      return `<span class="diff-neutral">0.00</span>`;
    }

    function toggleSort() {
      if (!currentSort) currentSort = 'value';
      else if (currentSort === 'value') currentSort = '-value';
      else currentSort = '';
      document.getElementById('sort-icon').innerText = currentSort === 'value' ? '▲' : (currentSort === '-value' ? '▼' : '⇅');
      loadData();
    }

    async function loadData() {
      const org = document.getElementById('org-select').value;
      const reason = document.getElementById('reason-filter').value;
      document.getElementById('metric-org').innerText = org;
      document.getElementById('tenant-pill').innerText = `Scope: ${org} (Isolated DB Query)`;

      const params = new URLSearchParams({ org });
      if (reason) params.append('reason', reason);
      if (currentSort) params.append('sort', currentSort);

      const tbody = document.getElementById('table-body');
      try {
        const res = await fetch(`/api/disagreements/?${params.toString()}`);
        const data = await res.json();
        
        document.getElementById('metric-total').innerText = data.length;
        document.getElementById('metric-values').innerText = data.filter(d => d.reason === 'VALUE_MISMATCH').length;
        document.getElementById('metric-missing').innerText = data.filter(d => d.reason === 'MISSING_IN_B' || d.reason === 'ORPHAN_IN_B').length;

        if (data.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:3rem; color:#94a3b8;">No discrepancies found for this view.</td></tr>';
          return;
        }

        tbody.innerHTML = data.map(row => `
          <tr>
            <td>${getBadge(row.reason)}</td>
            <td><span class="record-id">${row.record_id || '—'}</span></td>
            <td><span class="mono">${row.location || '—'}</span></td>
            <td class="mono">${formatAmount(row.a_value)}</td>
            <td class="mono">${formatAmount(row.b_value)}</td>
            <td class="mono">${calcDiff(row.a_value, row.b_value)}</td>
          </tr>
        `).join('');
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" style="color:#b91c1c; text-align:center; padding:2rem;">Error: ${e.message}</td></tr>`;
      }
    }

    window.onload = loadData;
  </script>
</body>
</html>
"""
    return HttpResponse(html, content_type="text/html")
