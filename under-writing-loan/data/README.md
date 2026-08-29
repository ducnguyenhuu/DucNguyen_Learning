# Data Directory

This directory contains all data storage for the loan underwriting system.

## Contents

### Databases

- **`mock_credit_bureau.db`** (SQLite) - Mock credit bureau database
  - Created by: `src/mcp/create_credit_db.py`
  - Populated by: `src/mcp/seed_data.py`
  - Purpose: Simulates credit bureau data for Risk Agent testing
  - Table: `credit_reports` (SSN, credit scores, payment history, etc.)
  - Access: MCP server endpoint `GET /credit/{ssn}`

- **`database.db`** (SQLite) - Application metadata storage
  - Created by: `src/mcp/create_app_db.py`
  - Purpose: Track loan application workflow status through multi-agent processing
  - Table: `applications` (application_id, status, timestamps, completion flags, MLflow run IDs)
  - Access: MCP server endpoints `GET/PUT /application/{application_id}`

### Directories

- **`applications/`** - Uploaded loan application documents
  - Format: PDFs organized by application ID
  - Example: `applications/app-001/paystub.pdf`
  - Access: MCP server endpoint `GET /files/{filename}`

- **`extracted/`** - Extracted document data (JSON outputs)
  - Format: JSON files from Document Agent
  - Example: `extracted/app-001-doc-001.json`
  - Purpose: Caching and debugging

- **`policies/`** - Lending policy documents for RAG system
  - Format: PDF policy documents
  - Example: `policies/underwriting_standards.pdf`
  - Indexed: Azure AI Search vector database
  - Purpose: Compliance Agent policy retrieval

## Database Schemas

### mock_credit_bureau.db

```sql
CREATE TABLE credit_reports (
    ssn TEXT PRIMARY KEY,                     -- Social Security Number (XXX-XX-XXXX)
    name TEXT NOT NULL,                       -- Applicant full name
    credit_score INTEGER NOT NULL,            -- FICO score (300-850)
    credit_utilization REAL NOT NULL,         -- % of available credit used (0.0-100.0)
    accounts_open INTEGER NOT NULL,           -- Number of active credit accounts
    derogatory_marks INTEGER NOT NULL,        -- Collections, bankruptcies, etc.
    credit_age_months INTEGER NOT NULL,       -- Age of oldest account
    payment_history TEXT NOT NULL,            -- excellent|good|fair|poor
    late_payments_12mo INTEGER DEFAULT 0,     -- Late payments in last 12 months
    hard_inquiries_12mo INTEGER DEFAULT 0,    -- Hard credit pulls in last year
    bureau_source TEXT DEFAULT 'mock_credit_bureau',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### database.db

**Purpose**: Track application workflow state through multi-agent processing

```sql
CREATE TABLE applications (
    application_id TEXT PRIMARY KEY,          -- Format: APP-YYYY-NNN
    status TEXT NOT NULL,                     -- pending|processing|completed|failed (CHECK constraint)
    created_at TEXT NOT NULL,                 -- ISO 8601 timestamp
    updated_at TEXT NOT NULL,                 -- ISO 8601 timestamp
    document_extraction_complete INTEGER NOT NULL DEFAULT 0,  -- Boolean (0/1)
    risk_assessment_complete INTEGER NOT NULL DEFAULT 0,      -- Boolean (0/1)
    compliance_check_complete INTEGER NOT NULL DEFAULT 0,     -- Boolean (0/1)
    decision_complete INTEGER NOT NULL DEFAULT 0,             -- Boolean (0/1)
    final_decision TEXT,                      -- approved|conditional_approval|denied|refer_to_manual (CHECK constraint)
    mlflow_run_id TEXT,                       -- Experiment tracking reference
    total_processing_time_seconds REAL,       -- Total workflow duration
    total_cost_usd REAL,                      -- Total Azure API costs
    error_messages TEXT DEFAULT '[]'          -- JSON array of error strings
);

-- Indexes for common queries
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_created_at ON applications(created_at DESC);
CREATE INDEX idx_applications_mlflow_run_id ON applications(mlflow_run_id);
```

**Workflow Tracking**:
- **pending**: Application submitted, awaiting processing
- **processing**: Multi-agent workflow in progress
- **completed**: All agents finished successfully
- **failed**: Error occurred during processing

**Completion Flags** track which agents have finished:
- `document_extraction_complete`: Document Agent completed
- `risk_assessment_complete`: Risk Agent completed
- `compliance_check_complete`: Compliance Agent completed
- `decision_complete`: Decision Agent completed

**Integration**:
- MCP server `GET /application/{id}` endpoint queries this table
- MCP server `PUT /application/{id}` endpoint updates progress
- Orchestrator persists state after each agent execution
- MLflow run IDs link experiments to applications

## Setup Instructions

### 1. Create Databases

```bash
# Create mock credit bureau database
python3 src/mcp/create_credit_db.py

# Create application metadata database
python3 src/mcp/create_app_db.py
```

### 2. Seed Test Data

```bash
# Populate credit bureau with 4 test profiles
python3 src/mcp/seed_data.py
```

### 3. Verify Setup

```bash
# Check database files exist
ls -lh data/*.db

# Verify credit records
sqlite3 data/mock_credit_bureau.db "SELECT ssn, name, credit_score FROM credit_reports;"

# Verify application table
sqlite3 data/database.db ".schema applications"
```

## Usage Examples

### Query Credit Report

```python
import sqlite3

conn = sqlite3.connect('data/mock_credit_bureau.db')
cursor = conn.cursor()

cursor.execute("SELECT * FROM credit_reports WHERE ssn = ?", ("111-11-1111",))
credit_report = cursor.fetchone()

conn.close()
```

### Track Application Status

```python
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

# Create new application
cursor.execute("""
    INSERT INTO applications (
        application_id, status, created_at, updated_at
    ) VALUES (?, ?, ?, ?)
""", ("APP-2025-001", "pending", datetime.now().isoformat(), datetime.now().isoformat()))

conn.commit()

# Update progress as agents complete
cursor.execute("""
    UPDATE applications 
    SET status = 'processing', 
        document_extraction_complete = 1,
        updated_at = ?
    WHERE application_id = ?
""", (datetime.now().isoformat(), "APP-2025-001"))

conn.commit()

# Query final status
cursor.execute("""
    SELECT application_id, status, final_decision, 
           total_processing_time_seconds, total_cost_usd
    FROM applications 
    WHERE application_id = ?
""", ("APP-2025-001",))

result = cursor.fetchone()
print(f"Application: {result[0]}, Status: {result[1]}, Decision: {result[2]}")

conn.close()
```

## Test Data

### Mock Credit Profiles (after seeding)

| SSN | Name | Credit Score | Profile |
|-----|------|--------------|---------|
| 111-11-1111 | Test Excellent | 780 | Excellent credit |
| 222-22-2222 | Test Good | 720 | Good credit |
| 333-33-3333 | Test Fair | 670 | Fair credit |
| 444-44-4444 | Test Poor | 590 | Poor credit |

See `src/mcp/seed_data.py` for complete profile details.

## Maintenance

### Reset Databases

```bash
# WARNING: Deletes all data

# Reset credit bureau and reseed
python3 src/mcp/create_credit_db.py --reset
python3 src/mcp/seed_data.py

# Reset application metadata
python3 src/mcp/create_app_db.py --reset
```

### Backup Database

```bash
# Create backup
cp data/mock_credit_bureau.db data/mock_credit_bureau.db.backup
cp data/database.sqlite data/database.sqlite.backup
```

### Verify Integrity

```bash
# Check database integrity
sqlite3 data/mock_credit_bureau.db "PRAGMA integrity_check;"
sqlite3 data/database.sqlite "PRAGMA integrity_check;"
```

## Git Ignore

The following files are gitignored to prevent committing sensitive or generated data:

- `*.db` (SQLite databases)
- `*.sqlite` (SQLite databases)
- `applications/` (uploaded PDFs)
- `extracted/` (generated JSON outputs)

The `policies/` directory contains sample policy documents that ARE committed for educational purposes.

## Notes

- **Educational Use Only**: This is mock data for learning purposes, not production-ready
- **No Real PII**: All SSNs and names are fictional test data
- **Local Only**: Databases are stored locally, not in cloud
- **SQLite Limits**: Single-user, file-based database - sufficient for learning, not for production scale
- **MCP Pattern**: Databases accessed through MCP server API, not directly by agents (teaches abstraction)

## Related Files

- Schema creation: `src/mcp/create_credit_db.py`
- Data seeding: `src/mcp/seed_data.py`
- MCP server: `src/mcp/server.py`
- API contracts: `specs/001-ai-loan-underwriting-system/contracts/mcp-server.yaml`
- Data models: `src/models.py`
