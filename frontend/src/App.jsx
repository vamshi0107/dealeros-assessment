import React, { useState, useEffect } from 'react';
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
    case 'MISSING_IN_B': return 'badge badge-missing';
    case 'ORPHAN_IN_B': return 'badge badge-orphan';
    case 'DUPLICATE_IN_B': return 'badge badge-duplicate';
    case 'VALUE_MISMATCH': return 'badge badge-mismatch';
    case 'LOCATION_MISMATCH': return 'badge badge-location';
    case 'DATE_MISMATCH': return 'badge badge-date';
    default: return 'badge badge-default';
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
    if (sortField === 'value') return ' ▲';
    if (sortField === '-value') return ' ▼';
    return ' ⇅';
  };

  const formatAmount = (val) => {
    if (val === null || val === undefined || val === '') {
      return <span className="empty-cell">—</span>;
    }
    const num = Number(val);
    if (isNaN(num)) return <span className="empty-cell">—</span>;
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const calculateDifference = (aVal, bVal) => {
    if (aVal === null || aVal === undefined || bVal === null || bVal === undefined) {
      return <span className="empty-cell">—</span>;
    }
    const a = Number(aVal);
    const b = Number(bVal);
    if (isNaN(a) || isNaN(b)) return <span className="empty-cell">—</span>;
    const diff = b - a;
    const formatted = Math.abs(diff).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (diff > 0) return `+${formatted}`;
    if (diff < 0) return `-${formatted}`;
    return '0.00';
  };

  return (
    <div className="app-container">
      <header>
        <h1>DealerOS Ledger Reconciliation</h1>
        <p>Reconciling business events between System A and System B</p>
      </header>

      <div className="controls-bar">
        <div className="control-group">
          <label htmlFor="org-select">Tenant (Org):</label>
          <select id="org-select" value={org} onChange={(e) => setOrg(e.target.value)}>
            <option value="ORG-A">ORG-A</option>
            <option value="ORG-B">ORG-B</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="reason-filter">Disagreement Reason:</label>
          <select id="reason-filter" value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">All Reasons</option>
            <option value="MISSING_IN_B">Missing in B</option>
            <option value="ORPHAN_IN_B">Orphan in B</option>
            <option value="DUPLICATE_IN_B">Duplicate in B</option>
            <option value="VALUE_MISMATCH">Value Mismatch</option>
            <option value="LOCATION_MISMATCH">Location Mismatch</option>
            <option value="DATE_MISMATCH">Date Mismatch</option>
          </select>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="stats-bar">
        Showing <strong>{data.length}</strong> discrepancy record{data.length === 1 ? '' : 's'} for <strong>{org}</strong>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Reason</th>
              <th>Record ID</th>
              <th>Location</th>
              <th>System A Value</th>
              <th className="sortable" onClick={handleSortToggle} title="Click to sort by System B value">
                System B Value{renderSortIndicator()}
              </th>
              <th>Difference</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="6" className="loading">Loading reconciliation data...</td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan="6" className="empty-state">No discrepancies found for this view.</td>
              </tr>
            ) : (
              data.map((row, idx) => (
                <tr key={`${row.record_id}-${row.reason}-${idx}`}>
                  <td>
                    <span className={getBadgeClass(row.reason)}>
                      {REASON_LABELS[row.reason] || row.reason}
                    </span>
                  </td>
                  <td><strong>{row.record_id || <span className="empty-cell">—</span>}</strong></td>
                  <td>{row.location || <span className="empty-cell">—</span>}</td>
                  <td>{formatAmount(row.a_value)}</td>
                  <td>{formatAmount(row.b_value)}</td>
                  <td>{calculateDifference(row.a_value, row.b_value)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
