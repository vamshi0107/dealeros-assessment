import React, { useState, useEffect, useMemo } from 'react';
import './App.css';

const REASON_LABELS = {
  MISSING_IN_B: 'Missing in System B',
  ORPHAN_IN_B: 'Orphan in System B',
  DUPLICATE_IN_B: 'Duplicate in System B',
  VALUE_MISMATCH: 'Value Mismatch',
  LOCATION_MISMATCH: 'Location Mismatch',
  DATE_MISMATCH: 'Date Mismatch',
};

const getBadgeClass = (reason) => {
  switch (reason) {
    case 'MISSING_IN_B': return 'badge-pill badge-missing';
    case 'ORPHAN_IN_B': return 'badge-pill badge-orphan';
    case 'DUPLICATE_IN_B': return 'badge-pill badge-duplicate';
    case 'VALUE_MISMATCH': return 'badge-pill badge-mismatch';
    case 'LOCATION_MISMATCH': return 'badge-pill badge-location';
    case 'DATE_MISMATCH': return 'badge-pill badge-date';
    default: return 'badge-pill';
  }
};

export default function App() {
  const [org, setOrg] = useState('ORG-A');
  const [reason, setReason] = useState('');
  const [sortField, setSortField] = useState(''); // '', 'value', '-value'
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDisagreements();
  }, [org, reason, sortField]);

  const fetchDisagreements = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (org) params.append('org', org);
      if (reason) params.append('reason', reason);
      if (sortField) params.append('sort', sortField);

      const res = await fetch(`/api/disagreements/?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`API error: ${res.status} ${res.statusText}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to load reconciliation data');
    } finally {
      setLoading(false);
    }
  };

  const handleSortToggle = () => {
    if (!sortField) {
      setSortField('value'); // ascending
    } else if (sortField === 'value') {
      setSortField('-value'); // descending
    } else {
      setSortField(''); // unsorted
    }
  };

  const renderSortIndicator = () => {
    if (sortField === 'value') return <span className="sort-icon">▲</span>;
    if (sortField === '-value') return <span className="sort-icon">▼</span>;
    return <span className="sort-icon">⇅</span>;
  };

  const formatAmount = (val) => {
    if (val === null || val === undefined || val === '') {
      return <span className="empty-val">—</span>;
    }
    const num = Number(val);
    if (isNaN(num)) return <span className="empty-val">—</span>;
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const calculateDifference = (aVal, bVal) => {
    if (aVal === null || aVal === undefined || bVal === null || bVal === undefined) {
      return <span className="empty-val">—</span>;
    }
    const a = Number(aVal);
    const b = Number(bVal);
    if (isNaN(a) || isNaN(b)) return <span className="empty-val">—</span>;
    const diff = b - a;
    const formatted = Math.abs(diff).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (diff > 0.001) return <span className="diff-positive">+{formatted}</span>;
    if (diff < -0.001) return <span className="diff-negative">-{formatted}</span>;
    return <span className="diff-neutral">0.00</span>;
  };

  // Metrics calculation
  const metrics = useMemo(() => {
    const total = data.length;
    const missing = data.filter(d => d.reason === 'MISSING_IN_B' || d.reason === 'ORPHAN_IN_B').length;
    const valueMismatches = data.filter(d => d.reason === 'VALUE_MISMATCH').length;
    const duplicates = data.filter(d => d.reason === 'DUPLICATE_IN_B').length;
    return { total, missing, valueMismatches, duplicates };
  }, [data]);

  return (
    <div className="app-wrapper">
      {/* Top Professional Navbar */}
      <nav className="top-navbar">
        <div className="nav-container">
          <div className="brand-section">
            <div className="brand-logo">DealerOS</div>
            <div className="brand-titles">
              <h1>Ledger Reconciliation Console</h1>
              <p>Dual-Ledger Audit & Multi-Tenant Discrepancy Detector</p>
            </div>
          </div>
          <div className="system-status">
            <span className="pulse-dot"></span>
            <span>Reconciliation Engine Active</span>
          </div>
        </div>
      </nav>

      {/* Main App Container */}
      <main className="main-content">
        {/* Metric Overview Cards */}
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-label">Total Discrepancies</div>
            <div className="metric-value">{metrics.total}</div>
            <div className="metric-sub">Across active filters</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Value Imbalances</div>
            <div className="metric-value">{metrics.valueMismatches}</div>
            <div className="metric-sub">Differing transaction sums</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Missing & Orphans</div>
            <div className="metric-value">{metrics.missing}</div>
            <div className="metric-sub">Unmatched ledger entries</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Active Tenant Scoping</div>
            <div className="metric-value" style={{ color: '#2563eb' }}>{org}</div>
            <div className="metric-sub">Zero cross-tenant leakage</div>
          </div>
        </div>

        {/* Toolbar & Filter Bar */}
        <div className="toolbar-card">
          <div className="controls-left">
            <div className="control-item">
              <label htmlFor="org-select">Tenant Organization:</label>
              <select
                id="org-select"
                className="custom-select"
                value={org}
                onChange={(e) => setOrg(e.target.value)}
              >
                <option value="ORG-A">ORG-A (HQ & Branches 101-103)</option>
                <option value="ORG-B">ORG-B (Branches 201-202)</option>
              </select>
            </div>

            <div className="control-item">
              <label htmlFor="reason-filter">Disagreement Category:</label>
              <select
                id="reason-filter"
                className="custom-select"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              >
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

          <div className="toolbar-right">
            <span className="tenant-pill">
              Scope: {org} (Isolated DB Query)
            </span>
          </div>
        </div>

        {error && <div className="alert-banner">{error}</div>}

        {/* Reconciliation Table */}
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Discrepancy Category</th>
                <th>Record Identifier</th>
                <th>Location</th>
                <th>System A Value</th>
                <th
                  className="sortable-header"
                  onClick={handleSortToggle}
                  title="Click to sort by System B Value"
                >
                  System B Value{renderSortIndicator()}
                </th>
                <th>Variance (B − A)</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" className="state-container">
                    <div className="state-title">Analyzing ledgers...</div>
                    <div className="state-desc">Fetching discrepancies from SQLite database</div>
                  </td>
                </tr>
              ) : data.length === 0 ? (
                <tr>
                  <td colSpan="6" className="state-container">
                    <div className="state-title">No Discrepancies Found</div>
                    <div className="state-desc">Both systems agree on all records for this view.</div>
                  </td>
                </tr>
              ) : (
                data.map((row, idx) => (
                  <tr key={`${row.record_id}-${row.reason}-${idx}`}>
                    <td>
                      <span className={getBadgeClass(row.reason)}>
                        {REASON_LABELS[row.reason] || row.reason}
                      </span>
                    </td>
                    <td>
                      <span className="record-id">
                        {row.record_id || <span className="empty-val">—</span>}
                      </span>
                    </td>
                    <td>
                      <span className="location-tag">
                        {row.location || <span className="empty-val">—</span>}
                      </span>
                    </td>
                    <td className="mono-cell">{formatAmount(row.a_value)}</td>
                    <td className="mono-cell">{formatAmount(row.b_value)}</td>
                    <td className="mono-cell">{calculateDifference(row.a_value, row.b_value)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
