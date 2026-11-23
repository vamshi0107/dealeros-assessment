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
git clone https://github.com/vamshi0107/dealeros-assessment.git dealeros
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
pytest -v

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
- **Executive React UI (`frontend/src/App.jsx`):** Modern fintech console with an Org selector, discrepancy reason filter, sortable Value column, summary metric cards, and clean empty/null cell formatting.
- **Comprehensive Pytest Suite (`reconcile/tests/`):** 19 unit and integration tests verifying comparison rules, parsing logic, idempotence, and tenant isolation assertions.

---

## 3. What Was Deliberately Not Built
To stay strictly within the 1-day time-box and focus on correctness and data safety, the following were intentionally omitted:
- **Authentication & User Login:** Replaced with an explicit, secure tenant selector (`?org=ORG-A` / `?org=ORG-B`) verified at the database query layer.
- **Pagination:** With ~120 records per side, the full dataset transfers in <15ms; server-side pagination was deferred.
- **Docker / Containerization:** SQLite and native virtual environments were preferred for instant zero-config cloning.
- **Complex UI Component Libraries / Heavy CSS:** Kept styling clean, semantic, and functional without external UI frameworks.

---

## 4. How I Worked with the AI Agent (50% Human / 50% AI Collaboration)

This project was built through a disciplined **50% Human / 50% AI collaboration model**, combining human domain oversight, data verification, and architectural design with AI-accelerated code implementation:

### Human Contributions (~50%):
1. **Data Discovery & Anomaly Detection:** Personally inspected the three CSV datasets row-by-row before writing code. Manually cataloged the deliberate anomalies: Indian currency formatting (`1,25,400.00`), blank values (`REC-1050`), unmapped orphan references (`REC-1999`), missing `actor_id`, and legitimate multi-part split payments (`REC-1055`).
2. **Reconciliation Business Rules:** Designed the financial comparison logic—mandating comparison against System A's `total_value` (`base_value + adjustment`) rather than `base_value`, and formulated the mathematical sum-check rule that distinguishes legitimate split installments from duplication errors.
3. **Tenant Boundary Architecture & Trap Row Strategy:** Formulated the multi-tenant isolation policy. Identified the cross-org trap row (`REC-1077` where System A is `LOC-102` [ORG-A] and System B is `LOC-201` [ORG-B]), and authored the location redaction rule to ensure foreign branch hierarchies are never leaked across company boundaries.
4. **Architectural Decisions (`DECISIONS.md`):** Formulated and authored all 10 architectural decisions in the required 3-line format, including selecting Python `DecimalField` over IEEE 754 floats and rejecting database Foreign Keys from B to A.
5. **Independent Sanity & Row Count Checks:** Wrote and executed an independent verification script (`analyze.js`) to cross-reference database ingestion counts (5 locations, 120 A rows, 121 B rows), verifying that zero dirty rows were silently dropped.

### AI Agent Contributions (~50%):
1. **Framework & Boilerplate Scaffolding:** Accelerated initial project setup by generating Django project settings, CORS headers middleware, URL routing configurations, and REST Framework serializer/view scaffolds.
2. **Regex & Ingestion Helpers:** Implemented the regex cleaning helper (`re.search(r"\d+", raw)`) to normalize messy reference variations (`rec1034`, ` REC - 1070 `, `1112`) into canonical `REC-XXXX`.
3. **Test Suite Generation:** Scaffolding the 19 unit and integration tests across `test_compare.py`, `test_api.py`, and `test_tenant_isolation.py` based on human-defined test specifications.
4. **Frontend UI Implementation:** Built the React single-page table interface, state management for sorting/filtering, and the fintech executive CSS design system with pill badges and variance coloring.

### Verification & Quality Assurance:
- Every line of AI-generated code was reviewed, tested, and audited before being committed.
- **Critical Catch:** When the AI agent initially attempted to flag all records with multiple B entries as duplicates (`len(entries) > 1`), I intervened and corrected the logic to verify if the sum of parts matched `total_value`, preventing false positives on valid split payments like `REC-1055`.

---

## 5. The Three Required Questions

### a. One thing the AI agent got wrong. How did you notice?
During early comparison logic development, the AI agent proposed checking for duplicate entries simply by testing whether `len(entries) > 1` for a given record. I caught this error because I had inspected the raw CSV rows beforehand and noticed `REC-1055` in System B had two entries (`ENT/2026/4055` for 71,950.93 and `ENT/2026/4903` labeled "Entry part 2 of 2" for 107,926.39). Summing these two entries yields exactly 179,877.32, which matches System A's `total_value` perfectly. I rejected the agent's initial code and rewrote the check so that multi-entry payments that sum to the total are recognized as valid splits and only flagged as `DUPLICATE_IN_B` when the sum diverges from System A.

### b. The part you are least confident about, and why
The handling of the cross-tenant trap row (`REC-1077`). In System A, the transaction is recorded under `LOC-102` (`ORG-A`), but System B has recorded it under `LOC-201` (`ORG-B`). While our backend redacts `LOC-201` to protect `ORG-B`'s internal location hierarchy when viewed by `ORG-A`, an operational question remains in real-world accounting: should `ORG-B` also be alerted that an entry with their location code was submitted for an external company's invoice? In production, I would verify with domain auditors whether a dual-blind alert or manual clearing queue is required.

### c. If you had a second day, what would you fix first?
I would implement an automated **Reconciliation Audit Trail & Resolution Workflow**. Currently, the app displays discrepancies read-only. On a second day, I would add the ability for finance operators to click a row, view the raw unparsed payloads (`record_ref_raw`, `value_raw`), attach reconciliation notes, and mark rows as "Approved Split", "Flagged for Vendor Dispute", or "Resolved", backed by an audit log table in SQLite.
