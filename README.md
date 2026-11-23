# DealerOS Ledger Reconciliation Web Application

A full-stack financial reconciliation application that compares business transactions recorded across two independent ledgers (**System A** and **System B**), identifies discrepancies, and displays them in a filtered, sortable interface with strict multi-tenant boundary isolation.

---

## 1. How to Run It (Clean Clone Instructions)

Prerequisites:
- Python 3.11 or newer (tested on Python 3.12)
- Node.js 18 or newer
- Git

### A. Backend Setup
```bash
# 1. Clone repository and navigate into project directory
git clone <repo-url> dealeros
cd dealeros

# 2. Create and activate a Python virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
# source .venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Run database migrations (creates SQLite tables)
cd backend
python manage.py migrate

# 5. Run idempotent CSV data import
python manage.py import_data

# 6. Run test suite (19 unit & tenant isolation tests)
pytest

# 7. Start the backend development server (runs on http://127.0.0.1:8000)
python manage.py runserver
```

### B. Frontend Setup (In a second terminal window)
```bash
# 1. Navigate to the frontend directory
cd dealeros/frontend

# 2. Install frontend dependencies
npm install

# 3. Start the Vite React development server
npm run dev
# Open your browser at http://localhost:5173
```

---

## 2. What Was Built
- **Idempotent Data Ingestion Engine:** `import_data` management command that ingests 5 locations, 120 System A records, and 121 System B entries into SQLite using `DecimalField`. Raw inputs and unparseable values are stored safely as `null` without crashing or dropping rows. Running the command repeatedly produces identical row counts without duplication.
- **Pure Python Comparison Engine (`compare.py`):** Completely decoupled from database and HTTP layers. Categorizes disagreements into `MISSING_IN_B`, `ORPHAN_IN_B`, `DUPLICATE_IN_B`, `VALUE_MISMATCH`, `LOCATION_MISMATCH`, and `DATE_MISMATCH`, while recognizing legitimate multi-part splits (e.g., REC-1055) as valid non-errors.
- **Multi-Tenant REST API (`GET /api/disagreements/`):** Implemented in Django REST Framework. Tenant boundaries are strictly enforced inside database queries via `locations.csv`. Includes active prevention of cross-tenant information leaks (e.g. redacting foreign location IDs on trap row REC-1077).
- **Responsive React UI (`frontend/src/App.jsx`):** Single-page interface with an Org selector, reason filter dropdown, sortable Value column, and clean empty/null cell formatting.
- **Comprehensive Pytest Suite (`reconcile/tests/`):** 19 unit and integration tests verifying comparison rules, parsing logic, idempotence, and tenant isolation assertions.

---

## 3. What Was Deliberately Not Built
To stay strictly within the 1-day time-box and focus on correctness and data safety, the following were intentionally omitted:
- **Authentication & User Login:** Replaced with an explicit, secure tenant selector (`?org=ORG-A` / `?org=ORG-B`) verified at the database query layer.
- **Pagination:** With ~120 records per side, the full dataset transfers in <15ms; server-side pagination was deferred.
- **Docker / Containerization:** SQLite and native virtual environments were preferred for instant zero-config cloning.
- **Complex UI Component Libraries / Heavy CSS:** Kept styling clean, semantic, and functional without external UI frameworks.

---

## 4. How I Worked with the AI Agent
- **Agent Utilized:** Antigravity AI Agent (powered by Gemini 3.8).
- **Workflow & Division of Labor:**
  1. I directed the agent to inspect the raw CSV files row-by-row before writing code, noting dirty rows, blanks, and formatting variations.
  2. I had the agent scaffold the models, importer, pure Python comparison function, and unit tests sequentially, following the 10-step commit roadmap.
  3. I verified and tested the Python logic and row counts using independent sanity checks (`analyze.js` and direct SQLite shell queries).
  4. I designed the cross-tenant mitigation strategy for the trap row (`REC-1077`) to guarantee that foreign branch IDs never leak across tenant boundaries.

---

## 5. The Three Required Questions

### a. One thing the AI agent got wrong. How did you notice?
During early test scaffolding, the agent initially proposed checking duplicates simply by testing whether `len(entries) > 1` for a given record. I caught this because I had inspected the CSV rows beforehand and noticed `REC-1055` in System B had two entries (`ENT/2026/4055` for 71,950.93 and `ENT/2026/4903` labeled "Entry part 2 of 2" for 107,926.39). Summing them yields exactly 179,877.32, matching System A's `total_value`. I corrected the logic so that multi-entry payments that sum to the total are recognized as valid splits and only flagged as `DUPLICATE_IN_B` when the sum diverges from System A.

### b. The part you are least confident about, and why
The handling of the cross-tenant trap row (`REC-1077`). In System A, the transaction is booked under `LOC-102` (`ORG-A`), but System B has recorded it under `LOC-201` (`ORG-B`). While our backend redacts `LOC-201` to protect `ORG-B`'s internal location hierarchy when viewed by `ORG-A`, an operational question remains in real-world accounting: should `ORG-B` also be alerted that an entry with their location code was submitted for an external company's invoice? In production, I would verify with domain auditors whether a dual-blind alert or manual clearing queue is required.

### c. If you had a second day, what would you fix first?
I would implement an automated **Reconciliation Audit Trail & Resolution Workflow**. Currently, the app displays discrepancies read-only. On a second day, I would add the ability for finance operators to click a row, view the raw unparsed payloads (`record_ref_raw`, `value_raw`), attach reconciliation notes, and mark rows as "Approved Split", "Flagged for Vendor Dispute", or "Resolved", backed by an audit log table in SQLite.
