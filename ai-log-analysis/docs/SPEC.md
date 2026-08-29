# AI-Powered Monitoring Assistant for VS Code
## Technical Specification

**Version:** 2.0 (MVP)  
**Date:** February 6, 2026  
**Status:** Ready for Implementation  

---

## Executive Summary

A lightweight, two-component system that brings New Relic monitoring insights directly into VS Code through GitHub Copilot custom agents.

**What it does:**
1. Python script fetches New Relic APM data → stores as JSON files locally
2. Two custom GitHub Copilot agents analyze the data and generate markdown reports

**Key Benefits:**
- ✅ **Simple:** No extensions to build, just Python script + agent prompts
- ✅ **Fast:** Can be implemented in 2-3 days
- ✅ **Cost-effective:** Only uses AI when you trigger analysis
- ✅ **Practical:** Works in VS Code where you already code
- ✅ **Manual control:** You decide when to analyze

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component 1: Data Crawler](#2-component-1-data-crawler)
3. [Component 2: GitHub Copilot Custom Agents](#3-component-2-github-copilot-custom-agents)
4. [Data Models](#4-data-models)
5. [Implementation Guide](#5-implementation-guide)
6. [Testing](#6-testing)

---

## 1. System Overview

### 1.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Data Collection                                         │
│                                                                  │
│  ┌──────────────────┐         ┌─────────────────┐             │
│  │  New Relic API   │─────────>│ crawler.py      │             │
│  │  (NerdGraph)     │         │ (Python script) │             │
│  └──────────────────┘         └────────┬────────┘             │
│                                         │                        │
│                                         ▼                        │
│                              ┌────────────────────┐             │
│                              │ data/              │             │
│                              │ ├── app1.json      │             │
│                              │ ├── app2.json      │             │
│                              │ └── ...            │             │
│                              └────────────────────┘             │
│                                                                  │
│  Runs: Manually or via cron (hourly)                           │
└─────────────────────────────────────────────────────────────────┘

                              ↓ (You review JSON files)

┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Analysis in VS Code                                     │
│                                                                  │
│  You open VS Code Copilot Chat                                 │
│                                                                  │
│  Agent 1: @analysis-agent                                       │
│  ┌───────────────────────────────────────┐                     │
│  │ User: @analysis-agent analyze data/   │                     │
│  │                                        │                     │
│  │ Agent reads: JSON files                │                     │
│  │ Agent calculates: health scores        │                     │
│  │ Agent detects: issues & anomalies      │                     │
│  │ Agent generates: assessment.md         │                     │
│  └─────────────────┬─────────────────────┘                     │
│                    │                                             │
│                    ▼                                             │
│  ┌──────────────────────────────────────┐                      │
│  │ assessment.md                         │                      │
│  │ - Health score: 65/100                │                      │
│  │ - Issues: 2 critical, 3 warnings      │                      │
│  │ - Trends & insights                   │                      │
│  └──────────────────────────────────────┘                      │
│                    │                                             │
│                    ▼                                             │
│  Agent 2: @recommend-agent                                      │
│  ┌───────────────────────────────────────┐                     │
│  │ User: @recommend-agent review          │                     │
│  │       assessment.md                    │                     │
│  │                                        │                     │
│  │ Agent reads: assessment.md + code      │                     │
│  │ Agent analyzes: root causes            │                     │
│  │ Agent generates: recommendations.md    │                     │
│  └─────────────────┬─────────────────────┘                     │
│                    │                                             │
│                    ▼                                             │
│  ┌──────────────────────────────────────┐                      │
│  │ recommendations.md                    │                      │
│  │ - Specific code fixes with diffs      │                      │
│  │ - Implementation steps                │                      │
│  │ - Expected impact                     │                      │
│  └──────────────────────────────────────┘                      │
│                                                                  │
│  You implement the fixes manually                               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Workflow

1. **Data Collection** (Automated or Manual)
   ```bash
   python crawler.py  # Fetches from New Relic → stores JSON
   ```

2. **Analysis** (Manual in VS Code)
   ```
   @analysis-agent analyze the data/ folder
   → Generates assessment.md
   ```

3. **Recommendations** (Manual in VS Code)
   ```
   @recommend-agent review assessment.md and suggest fixes
   → Generates recommendations.md
   ```

4. **Implementation** (Manual)
   - Review recommendations.md
   - Apply code fixes
   - Deploy
   - Re-run crawler to verify

### 1.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Local JSON storage** | Simple, no database needed, easy to inspect |
| **Manual workflow** | Full control, no automation overhead |
| **Custom Copilot agents** | No extension development needed |
| **Python crawler** | Simple, standard libraries, easy to maintain |
| **Markdown reports** | Easy to read, version control, share with team |

---

## 2. Component 1: Data Crawler

### 2.1 Purpose

Python script that fetches APM data from New Relic and stores it as JSON files locally.

### 2.2 Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| CR-1 | Fetch APM metrics (response time, error rate, throughput, Apdex) | P0 |
| CR-2 | Fetch error details with stack traces | P0 |
| CR-3 | Fetch slow transaction traces | P0 |
| CR-4 | Fetch infrastructure metrics (CPU, memory) | P1 |
| CR-5 | Store as timestamped JSON files | P0 |
| CR-6 | Support multiple applications | P0 |
| CR-7 | Configurable via YAML file | P0 |
| CR-8 | Handle API errors gracefully | P0 |

### 2.3 CLI Interface

```bash
# Basic usage - fetch all configured apps
python crawler.py

# Use custom config file
python crawler.py --config custom-config.yaml

# Fetch specific app only
python crawler.py --app-id prod-web-app

# Override timeframe
python crawler.py --hours 48

# Force fetch (ignore cache)
python crawler.py --now

# Clean old data files
python crawler.py --clean --days 30

# Test connection
python crawler.py --test-connection

# Validate config
python crawler.py --validate-config

# List configured apps
python crawler.py --list-apps

# Dry run
python crawler.py --dry-run
```

### 2.4 Output Format

**File naming:**
```
data/{app_name}-{timestamp}.json

Example:
data/prod-web-app-2026-02-06-14-30.json
```

**JSON structure:**
```json
{
  "app_id": "12345678",
  "app_name": "prod-web-app",
  "days": 1,
  "collected_at": "2026-02-06T14:30:00Z",
  
  "performance": {
    "app_id": "12345678",
    "timestamp": "2026-02-06T14:30:00Z",
    "performance": {
      "response_time": 185.5,
      "p50_ms": 150.2,
      "p95_ms": 270.8,
      "p99_ms": 450.1,
      "throughput": 1250.0,
      "total_requests": 1800000,
      "apdex_score": 0.87,
      "apdex_satisfied": 1530000,
      "apdex_tolerating": 180000,
      "apdex_frustrated": 90000
    }
  },
  
  "errors": {
    "app_id": "12345678",
    "timestamp": "2026-02-06T14:30:00Z",
    "errors": {
      "error_rate": 0.068,
      "error_count": 1234,
      "total_transactions": 18150,
      "error_types": ["NullReferenceException", "TimeoutException"]
    }
  },
  
  "infrastructure": {
    "app_id": "12345678",
    "timestamp": "2026-02-06T14:30:00Z",
    "infrastructure": {
      "cpu_usage": 0.452,
      "memory_usage": null,
      "memory_physical_mb": 2048.5,
      "disk_io": null
    }
  },
  
  "database": {
    "app_id": "12345678",
    "timestamp": "2026-02-06T14:30:00Z",
    "database": {
      "query_time": 45.2,
      "slow_queries": 12,
      "connection_pool_usage": 0.35,
      "database_calls": 856
    }
  },
  
  "transactions": {
    "app_id": "12345678",
    "timestamp": "2026-02-06T14:30:00Z",
    "transactions": {
      "transaction_time": 185.5,
      "external_calls": 4,
      "external_latency": 120.3,
      "api_endpoints": ["Controller/users/show", "Controller/orders/create"]
    }
  },
  
  "error_details": {
    "error_details": [
      {
        "error_class": "NullReferenceException",
        "count": 856,
        "message": "Object reference not set to an instance of an object",
        "stack_trace": "at PaymentProcessor.Process()..."
      }
    ]
  },
  
  "slow_transactions": {
    "slow_transactions": [
      {
        "name": "Controller/users/show",
        "avg_duration_ms": 850.0,
        "p95_ms": 1200.0,
        "call_count": 5000,
        "db_time_ms": 780.0,
        "db_call_count": 45,
        "external_time_ms": 50.0,
        "external_call_count": 2
      }
    ]
  },
  
  "database_details": {
    "database_details": [
      {
        "datastore_type": "MSSQL",
        "table": "Orders",
        "operation": "select",
        "avg_duration_ms": 25.3,
        "p95_ms": 45.1,
        "call_count": 12500
      }
    ]
  },
  
  "external_services": {
    "external_services": [
      {
        "host": "api.payment.com",
        "avg_duration_ms": 120.5,
        "p95_ms": 350.0,
        "call_count": 8500
      }
    ]
  },
  
  "application_logs": {
    "application_logs": [
      {
        "timestamp": "2026-02-06T14:25:00Z",
        "level": "ERROR",
        "message": "Connection timeout after 30000ms",
        "error_class": "TimeoutException"
      }
    ]
  },
  
  "log_volume": {
    "log_volume": [
      {"level": "INFO", "count": 125000},
      {"level": "ERROR", "count": 1234},
      {"level": "WARN", "count": 456}
    ]
  },
  
  "alerts": {
    "alerts": [
      {
        "title": "High Error Rate",
        "priority": "CRITICAL",
        "state": "closed",
        "condition_name": "Error percentage",
        "policy_name": "Production",
        "open_time": "2026-02-06T12:00:00Z",
        "close_time": "2026-02-06T12:15:00Z",
        "duration_seconds": 900
      }
    ]
  },
  
  "hourly_trends": {
    "hourly_trends": [
      {
        "timestamp": "2026-02-06T00:00:00Z",
        "avg_response_ms": 180.5,
        "throughput_rpm": 1200.0,
        "error_rate": 0.02
      }
    ]
  },
  
  "baselines": {
    "baselines": {
      "response_time_7d_avg_ms": 200.0,
      "throughput_7d_avg_rpm": 1200.0,
      "error_rate_7d_avg": 0.025,
      "total_requests_7d": 12096000
    }
  },
  
  "deployments": {
    "deployments": [
      {
        "timestamp": "2026-02-05T16:30:00Z",
        "revision": "v2.1.4",
        "description": "Fix payment timeout",
        "user": "deploy-bot",
        "changelog": "Increased timeout to 60s"
      }
    ]
  }
}
```

### 2.5 Configuration

**File:** `config.yaml` (place in project root)

```yaml
# New Relic API Configuration
new_relic:
  # API Key - can use env var ${NEW_RELIC_API_KEY} or paste directly
  # Get from: New Relic → Account Settings → API Keys → User Key
  api_key: ${NEW_RELIC_API_KEY}
  
  # Account ID from New Relic account settings
  # Get from: New Relic → Account Settings → Account Information
  account_id: "1234567"
  
  # NerdGraph API endpoint (default: US datacenter)
  api_endpoint: "https://api.newrelic.com/graphql"
  # EU datacenter: "https://api.eu.newrelic.com/graphql"
  
  # API timeout in seconds
  timeout: 30
  
  # Retry configuration
  max_retries: 3
  retry_delay: 5  # seconds between retries

# APM Applications to monitor
apps:
  - id: "12345678"              # New Relic Application ID
    name: "prod-web-app"        # Friendly name (used in filenames)
    enabled: true                # Set false to skip temporarily
    tags:
      - production
      - web
    
  - id: "87654321"
    name: "prod-api"
    enabled: true
    tags:
      - production
      - api

# Data Collection Settings
data_collection:
  # Time range for each collection (hours)
  # How far back to fetch data
  timeframe_hours: 24
  
  # Baseline period for comparison (days)
  # Used to calculate "normal" behavior
  baseline_days: 7
  
  # Metrics to collect (comment out to disable)
  metrics:
    - performance      # Response time, throughput, Apdex
    - errors          # Error count, rate, stack traces
    - transactions    # Slow transactions, database queries
    - infrastructure  # CPU, memory, disk I/O
  
  # Limits for data retrieval
  limits:
    max_errors: 100           # Max error types to fetch per app
    max_transactions: 20      # Max slow transactions to fetch
    max_error_traces: 50      # Max error trace details
  
  # Data freshness
  min_collection_interval: 3600  # seconds (1 hour)
  # Won't re-fetch if data exists from last X seconds

# Crawler Behavior
crawler:
  # Output directory for JSON files
  data_dir: "./data"
  
  # Data retention (auto-cleanup)
  retention_days: 30
  
  # Concurrent requests (careful with API rate limits)
  max_workers: 3
  
  # Rate limiting
  requests_per_minute: 100
  
  # Cache settings
  cache_enabled: true
  cache_ttl: 3600  # seconds

# Logging Configuration
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "logs/crawler.log"
  console: true  # Also print to console
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  max_size_mb: 10
  backup_count: 5  # Keep 5 old log files
```

### 2.6 Configuration Details

#### Finding Your Configuration Values

**1. API Key:**
```
New Relic → Account Settings → API Keys → User Key
Look for: NRAK-XXX...
```

**2. Account ID:**
```
New Relic → Account Settings → Account Information
Look for: Account ID (numeric)
```

**3. Application ID:**
```
New Relic → APM & Services → Click your app
URL will contain the app ID
Example: https://one.newrelic.com/nr1-core?filters=(domain%20IN%20('APM')%20AND%20type%20IN%20('APPLICATION'))&state=12345678-xxxx-xxxx
                                                                                            ^^^^^^^^
```

#### Recommended Settings by Use Case

**Real-time monitoring (frequent checks):**
```yaml
data_collection:
  timeframe_hours: 1
  baseline_days: 1
  min_collection_interval: 900  # 15 minutes
```

**Daily analysis (default):**
```yaml
data_collection:
  timeframe_hours: 24
  baseline_days: 7
  min_collection_interval: 3600  # 1 hour
```

**Weekly review:**
```yaml
data_collection:
  timeframe_hours: 168  # 7 days
  baseline_days: 30
  min_collection_interval: 86400  # 1 day
```

#### Data Limits by App Size

**Small app (<100 req/min):**
```yaml
limits:
  max_errors: 50
  max_transactions: 10
  max_error_traces: 25
```

**Medium app (100-1000 req/min):**
```yaml
limits:
  max_errors: 100
  max_transactions: 20
  max_error_traces: 50
```

**Large app (>1000 req/min):**
```yaml
limits:
  max_errors: 200
  max_transactions: 50
  max_error_traces: 100
```

#### Environment Variable Overrides

```bash
# Override any config value with environment variables
export NEW_RELIC_API_KEY="NRAK-YOUR-KEY"
export DATA_COLLECTION_TIMEFRAME_HOURS="48"
export CRAWLER_DATA_DIR="/var/data/monitoring"

python crawler.py
```

**Naming convention:**
```
config.yaml path: new_relic.api_key
Environment var:  NEW_RELIC_API_KEY

config.yaml path: data_collection.timeframe_hours
Environment var:  DATA_COLLECTION_TIMEFRAME_HOURS
```

### 2.7 Implementation Notes

**Technology:**
- Python 3.11+
- `requests` library for HTTP
- `pyyaml` for config
- Standard library only (no heavy dependencies)

**Key Features:**
- Incremental collection (only fetch if >1h since last run)
- Automatic retry with exponential backoff
- Structured logging
- Graceful error handling

**Deployment:**
```bash
# Crontab for hourly execution
0 * * * * cd /path/to/ai-monitor && /path/to/venv/bin/python crawler.py >> logs/cron.log 2>&1
```

---

## 3. Component 2: GitHub Copilot Custom Agents

### 3.1 Overview

Two custom agents defined via prompts in `.github/copilot-instructions.md`:
- **`analysis-agent`** - Analyzes JSON data, generates `assessment.md`
- **`recommend-agent`** - Reviews assessment + code, generates `recommendations.md`

**No extension development needed** - just configuration files!

### 3.2 Setup

**Step 1: Create `.github/copilot-instructions.md`**

Place this file in your repository root:

```markdown
# Custom Agent: analysis-agent

## Role
You are an expert SRE analyzing production monitoring data from New Relic.

## When Activated
User mentions `@analysis-agent` in Copilot Chat

## Instructions

### Step 1: Read Input Data
- Read ALL JSON files in the `data/` directory
- Each file contains: metadata, performance, errors, transactions, infrastructure, baselines

### Step 2: Calculate Health Score (0-100)

For each application:
```
health_score = (
    performance_score * 0.30 +
    reliability_score * 0.30 +
    resource_score * 0.20 +
    satisfaction_score * 0.20
)

Where:
- performance_score = 100 - (avg_response_time_ms / 10)
- reliability_score = 100 - (error_rate * 1000)
- resource_score = 100 - MAX(cpu_percent, memory_percent)
- satisfaction_score = apdex_score * 100
```

**Thresholds:**
- 90-100: Excellent 🟢
- 70-89: Good ✓
- 50-69: Warning 🟡
- 0-49: Critical 🔴

### Step 3: Detect Issues

**Error Detection:**
- Error rate >1% → HIGH priority
- Error count >100/hour → MEDIUM priority
- New error class → HIGH priority

**Performance Detection:**
- Response time >1000ms → MEDIUM
- Response time >2000ms → HIGH
- P95 >2x P50 → MEDIUM "High variance"

**Database Detection:**
- Queries per transaction >10 → WARNING "Possible N+1"
- Database time >70% total time → MEDIUM "Database bottleneck"

**Resource Detection:**
- CPU >80% sustained → HIGH
- Memory >85% sustained → HIGH
- Memory increasing >10%/hour → HIGH "Possible leak"

### Step 4: Generate assessment.md

**Format:**
```markdown
# System Health Assessment
**Generated:** [timestamp]
**Data Range:** [time range]

## Executive Summary
- **Overall Health:** [score]/100 ([status])
- **Applications Monitored:** [count]
- **Critical Issues:** [count]
- **Warnings:** [count]

## Health Scores by Application

### [app_name] - [score]/100 ([status icon])

**Metrics:**
- **Error Rate:** [value]% ([trend])
- **Response Time:** [avg]ms (P95: [value]ms)
- **Apdex Score:** [value]
- **Throughput:** [value] rpm
- **CPU:** [value]%
- **Memory:** [value]%

**Issues Detected:**
1. **[🔴 HIGH/🟡 MEDIUM] [Title]**
   - **Started:** [when]
   - **Count:** [number]
   - **Affected:** [endpoints/users]
   - **Evidence:** [specific data]
   - **Location:** [file:line if available]

---

## Critical Issues (Immediate Action Required)
[List all HIGH priority issues with full details]

## Warnings (Monitor Closely)
[List MEDIUM/WARNING issues]

## Trends & Insights
[Notable patterns, comparisons with baseline]

## Recommended Next Steps
1. Focus on critical issues first
2. Invoke `@recommend-agent` for code fixes
3. Monitor trends

## What's Working Well ✅
[List healthy metrics]
```

### Quality Guidelines

**Be Specific:**
✅ "Error rate 8.2% (856 errors/hour), up from 0.5% baseline"  
❌ "Error rate is high"

✅ "NullPointerException in PaymentProcessor.java:145"  
❌ "Some errors in payment code"

**Show Evidence:**
- Include actual error messages
- Reference file:line from stack traces
- Show current vs baseline numbers

**Prioritize by Impact:**
- HIGH: Blocking users, data loss
- MEDIUM: Degraded experience, slow
- WARNING: Trending bad, not critical yet

---

# Custom Agent: recommend-agent

## Role
You are an expert software engineer providing actionable solutions.

## When Activated
User mentions `@recommend-agent` in Copilot Chat

## Instructions

### Step 1: Read Input
1. Read `assessment.md` - identified issues
2. Workspace code - automatically available
3. Git history (optional) - recent commits

### Step 2: Root Cause Analysis

For each CRITICAL or HIGH issue:

**A. Find Affected Code:**
- Use stack traces to find exact files
- Search workspace for patterns
- Identify 3-10 most relevant files

**B. Analyze the Problem:**
- Missing null checks
- N+1 queries
- No error handling
- Small connection pools
- Missing indexes
- No caching

**C. Design Solution:**
- Specific fix with exact code
- Backward compatible when possible
- Include config/database changes needed

### Step 3: Generate recommendations.md

**Format:**
```markdown
# Code Fix Recommendations
**Generated:** [timestamp]
**Based on:** assessment.md

## Summary
[2-3 sentences: issues found, main causes, expected improvements]

---

## Critical Issues - Immediate Action Required

### 1. [Issue Title] ([App Name])

**Problem:**
[Brief from assessment with metrics]

**Root Cause:**
- **File:** `[path/file.ext]:[lines]`
- **Cause:** [Specific issue]
- **Why:** [Explanation]

**Current Code:**
```[language]
// File: [path/file.ext]
// Lines: [start]-[end]
[EXACT current code - NO placeholders]
```

**Recommended Fix:**
```[language]
// File: [path/file.ext]
// Lines: [start]-[end]
[EXACT new code with comments]
```

**Explanation:**
[Why this fixes the issue]

**Impact Estimate:**
- **Error Rate:** [before] → [after]
- **Response Time:** [before] → [after]
- **Users Affected:** [before] → [after]

**Implementation:**
- **Effort:** [15min | 1hr | 4hrs | 1day]
- **Risk:** [Low | Medium | High]
- **Testing:** [How to verify]
- **Rollback:** [How to revert]

**Dependencies:**
- Config changes: [if any]
- Database migrations: [if any]
- Library updates: [if any]

---

### 2. [Next Issue...]

---

## Warnings - Proactive Improvements

### 3. [Medium Priority Issue...]

---

## Implementation Plan

**Recommended Order:**
1. [Issue #1] - [priority], [time] → [expected result]
2. [Issue #2] - [priority], [time] → [expected result]

**Success Metrics:**
- Error rate: [current] → [target]
- Response time: [current] → [target]
- Health score: [current] → [target]

**Verification:**
1. Apply fixes in staging
2. Run tests
3. Deploy
4. Monitor 30 mins
5. Re-run crawler
6. Use `@analysis-agent` to verify
```

### Quality Guidelines

**Must Include:**
- ✅ Exact file paths with line numbers
- ✅ Complete, runnable code
- ✅ Explanation of WHY
- ✅ Quantified impact
- ✅ Effort estimate
- ✅ Risk assessment
- ✅ Testing strategy

**Must Avoid:**
- ❌ Generic advice
- ❌ Pseudo-code or "..."
- ❌ Recommendations without code
- ❌ Fixes without root cause
```

**Step 2: Configure VS Code**

Add to `.vscode/settings.json`:
```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    {
      "file": ".github/copilot-instructions.md"
    }
  ]
}
```

**Step 3: Verify Setup**

In VS Code Copilot Chat:
```
@analysis-agent are you ready?
```

Should respond confirming its role.

### 3.3 Usage Examples

**Daily Monitoring:**
```
1. Run: python crawler.py
2. In VS Code: @analysis-agent analyze data/ folder
3. Review: assessment.md
4. If issues: @recommend-agent review assessment.md
5. Implement fixes
```

**Incident Investigation:**
```
1. Run: python crawler.py --now
2. @analysis-agent analyze latest data for critical issues
3. @recommend-agent provide fixes for the critical issue
4. Apply recommended fix
5. Deploy and verify
```

**Post-Deployment Check:**
```
1. Deploy your changes
2. Wait 30 mins
3. Run: python crawler.py
4. @analysis-agent compare latest with 1 hour ago
5. Verify no regressions
```

### 3.4 Expected Outputs

**assessment.md:**
- 200-500 lines
- Focuses on WHAT is wrong
- Health scores, issues, evidence
- Easy to scan quickly

**recommendations.md:**
- 300-800 lines
- Focuses on HOW to fix
- Specific code with diffs
- Implementation steps
- Impact estimates

---

## 4. Data Models

### 4.1 Health Score Calculation

```python
def calculate_health_score(data: dict) -> float:
    """Calculate overall health score (0-100)."""
    
    # Performance Score (0-100)
    avg_rt = data["performance"]["response_time"]["average_ms"]
    performance_score = max(0, 100 - (avg_rt / 10))
    
    # Reliability Score (0-100)
    error_rate = data["errors"]["error_rate"]
    reliability_score = max(0, 100 - (error_rate * 1000))
    
    # Resource Score (0-100)
    cpu = data["infrastructure"]["cpu_percent"]
    memory = data["infrastructure"]["memory_percent"]
    resource_score = 100 - max(cpu, memory)
    
    # Satisfaction Score (0-100)
    apdex = data["performance"]["apdex"]["score"]
    satisfaction_score = apdex * 100
    
    # Weighted average
    health_score = (
        performance_score * 0.30 +
        reliability_score * 0.30 +
        resource_score * 0.20 +
        satisfaction_score * 0.20
    )
    
    return round(health_score, 1)
```

### 4.2 Issue Classification

| Type | Severity | Condition |
|------|----------|-----------|
| Error Spike | HIGH | error_rate >5x baseline |
| Error Spike | MEDIUM | error_rate >2x baseline |
| High Error Rate | HIGH | error_rate >1% |
| Slow Response | HIGH | response_time >2000ms |
| Slow Response | MEDIUM | response_time >1000ms |
| N+1 Query | WARNING | database_queries >10 per transaction |
| Database Bottleneck | MEDIUM | database_time >70% of total time |
| CPU High | HIGH | cpu_percent >80% sustained |
| Memory High | HIGH | memory_percent >85% sustained |
| Memory Leak | HIGH | memory increasing >10%/hour |
| Low Apdex | CRITICAL | apdex_score <0.5 |
| Low Apdex | MEDIUM | apdex_score <0.7 |

### 4.3 New Relic GraphQL Queries

All queries use the NerdGraph GraphQL API (`https://api.newrelic.com/graphql`) with NRQL embedded in the `nrql(query:)` field.

**1. Performance Metrics (response time in ms, percentiles, Apdex, throughput):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(duration) * 1000 as 'avg_response_ms', percentile(duration, 50) * 1000 as 'p50_ms', percentile(duration, 95) * 1000 as 'p95_ms', percentile(duration, 99) * 1000 as 'p99_ms', rate(count(*), 1 minute) as 'throughput_rpm', count(*) as 'total_requests', apdex(duration, t:0.5) as 'apdex_score', filter(count(*), WHERE apdexPerfZone = 'S') as 'apdex_satisfied', filter(count(*), WHERE apdexPerfZone = 'T') as 'apdex_tolerating', filter(count(*), WHERE apdexPerfZone = 'F') as 'apdex_frustrated' FROM Transaction WHERE appId = 'APP_ID' SINCE 'SINCE_ISO'") {
        results
      }
    }
  }
}
```

**2. Error Metrics (rate, count, types):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT percentage(count(*), WHERE error IS true) as 'error.rate', filter(count(*), WHERE error IS true) as 'error.count', count(*) as 'total.transactions', uniques(error.class) as 'error.types' FROM Transaction WHERE appId = 'APP_ID' SINCE 'SINCE_ISO'") {
        results
      }
    }
  }
}
```

**3. Infrastructure Metrics (CPU, Memory via APM Metric events):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(apm.service.cpu.usertime.utilization) as 'cpu.utilization', average(apm.service.memory.physical) / 1048576 as 'memory.mb' FROM Metric WHERE appName = 'APP_NAME' SINCE 'SINCE_ISO'") {
        results
      }
    }
  }
}
```
> Note: SystemSample events are keyed by hostname, not appId. APM Metric events are used instead for reliable APM-linked infrastructure data. `cpu.utilization` is 0.0-1.0, `memory.mb` is absolute MB.

**4. Database Metrics:**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(databaseDuration) * 1000 as 'query_time_ms', filter(count(*), WHERE databaseDuration > 0.5) as 'slow_queries', percentage(count(*), WHERE databaseCallCount > 10) as 'high_db_call_pct', average(databaseCallCount) as 'avg_db_calls' FROM Transaction WHERE appId = 'APP_ID' SINCE 'SINCE_ISO'") {
        results
      }
    }
  }
}
```

**5. Transaction/API Metrics:**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(duration) * 1000 as 'avg_duration_ms', average(externalCallCount) as 'ext_calls', average(externalDuration) * 1000 as 'ext_latency_ms', uniques(name) as 'endpoints' FROM Transaction WHERE appId = 'APP_ID' SINCE 'SINCE_ISO'") {
        results
      }
    }
  }
}
```

**6. Error Details with Stack Traces:**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT count(*) as 'count', latest(error.message) as 'message', latest(stackTrace) as 'stack_trace' FROM TransactionError WHERE appId = 'APP_ID' SINCE 'SINCE_ISO' FACET error.class LIMIT 50") {
        results
      }
    }
  }
}
```

**7. Slow Transactions (per-endpoint breakdown):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(duration) * 1000 as 'avg_duration_ms', percentile(duration, 95) * 1000 as 'p95_ms', count(*) as 'call_count', average(databaseDuration) * 1000 as 'db_time_ms', average(databaseCallCount) as 'db_call_count', average(externalDuration) * 1000 as 'external_time_ms', average(externalCallCount) as 'external_call_count' FROM Transaction WHERE appId = 'APP_ID' SINCE 'SINCE_ISO' FACET name LIMIT 20") {
        results
      }
    }
  }
}
```

**8. Database Details (by type/table/operation):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(duration) * 1000 as 'avg_duration_ms', percentile(duration, 95) * 1000 as 'p95_ms', count(*) as 'call_count' FROM DatastoreSegment WHERE appId = 'APP_ID' SINCE 'SINCE_ISO' FACET datastoreType, table, operation LIMIT 20") {
        results
      }
    }
  }
}
```

**9. External Services (by host):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(duration) * 1000 as 'avg_duration_ms', count(*) as 'call_count', percentile(duration, 95) * 1000 as 'p95_ms' FROM ExternalSegment WHERE appId = 'APP_ID' SINCE 'SINCE_ISO' FACET host LIMIT 15") {
        results
      }
    }
  }
}
```

**10. Application Logs (errors/warnings/exceptions):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT timestamp, level, message, error.class FROM Log WHERE entity.name = 'APP_NAME' AND (level IN ('ERROR','WARN','FATAL','SEVERE') OR message LIKE '%exception%' OR message LIKE '%timeout%' OR message LIKE '%fail%') SINCE 'SINCE_ISO' LIMIT 500") {
        results
      }
    }
  }
}
```

**11. Log Volume (by level):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT count(*) as 'count' FROM Log WHERE entity.name = 'APP_NAME' SINCE 'SINCE_ISO' FACET level") {
        results
      }
    }
  }
}
```

**12. Alerts/Incidents:**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT title, priority, state, conditionName, policyName, openTime, closeTime, durationSeconds FROM NrAiIncident WHERE entity.name = 'APP_NAME' SINCE 'SINCE_ISO' LIMIT 50") {
        results
      }
    }
  }
}
```

**13. Hourly Performance Trends (time series):**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(duration) * 1000 as 'avg_response_ms', rate(count(*), 1 minute) as 'throughput_rpm', percentage(count(*), WHERE error IS true) as 'error_rate' FROM Transaction WHERE appId = 'APP_ID' SINCE 'SINCE_ISO' TIMESERIES 1 hour") {
        results
      }
    }
  }
}
```

**14. 7-Day Baselines:**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT average(duration) * 1000 as 'response_time_7d_avg_ms', rate(count(*), 1 minute) as 'throughput_7d_avg_rpm', percentage(count(*), WHERE error IS true) / 100 as 'error_rate_7d_avg', count(*) as 'total_requests_7d' FROM Transaction WHERE appId = 'APP_ID' SINCE 7 days ago") {
        results
      }
    }
  }
}
```

**15. Deployments:**
```graphql
{
  actor {
    account(id: ACCOUNT_ID) {
      nrql(query: "SELECT timestamp, revision, description, user, changelog FROM Deployment WHERE entity.name = 'APP_NAME' SINCE 'SINCE_ISO' LIMIT 20") {
        results
      }
    }
  }
}
```

---

## 5. Implementation Guide

### 5.1 Setup Steps

**1. Install Dependencies:**
```bash
pip install requests pyyaml
```

**2. Create Directory Structure:**
```bash
mkdir -p ai-monitoring/{data,logs,.github,.vscode}
cd ai-monitoring
```

**3. Create config.yaml:**
```bash
# Copy configuration from section 2.5 above
```

**4. Set API Key:**
```bash
export NEW_RELIC_API_KEY="NRAK-YOUR-KEY"
```

**5. Create .github/copilot-instructions.md:**
```bash
# Copy agent instructions from section 3.2 above
```

**6. Create .vscode/settings.json:**
```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    {
      "file": ".github/copilot-instructions.md"
    }
  ]
}
```

**7. Create crawler.py:**
```python
# Implementation in next section
```

### 5.2 Crawler Implementation Outline

**File: crawler.py**

```python
#!/usr/bin/env python3
"""
New Relic Data Crawler
Fetches APM data and stores as JSON files.
"""

import os
import sys
import json
import yaml
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Main components:
# 1. Config loader (YAML + env vars)
# 2. New Relic API client (NerdGraph GraphQL)
# 3. Data collectors (metrics, errors, transactions, infrastructure)
# 4. Data normalizer
# 5. File writer
# 6. CLI argument parser
# 7. Main orchestrator

class Config:
    """Load and validate configuration."""
    pass

class NewRelicClient:
    """New Relic NerdGraph API client."""
    pass

class MetricsCollector:
    """Collect APM metrics."""
    pass

class ErrorsCollector:
    """Collect error data."""
    pass

class TransactionsCollector:
    """Collect transaction traces."""
    pass

class InfrastructureCollector:
    """Collect infrastructure metrics."""
    pass

class DataNormalizer:
    """Normalize collected data."""
    pass

class FileWriter:
    """Write JSON files with proper naming."""
    pass

def main():
    """Main entry point."""
    # Parse CLI arguments
    # Load configuration
    # Initialize collectors
    # Fetch data for each app
    # Normalize data
    # Write JSON files
    # Clean old files
    pass

if __name__ == "__main__":
    main()
```

### 5.3 Development Workflow

**Phase 1: Basic Crawler (Day 1)**
- Config loading
- New Relic API client
- Basic metrics collection
- JSON file writing

**Phase 2: Complete Data Collection (Day 2)**
- Error collection
- Transaction traces
- Infrastructure metrics
- Baseline calculation

**Phase 3: Agent Setup (Day 3)**
- Create copilot-instructions.md
- Test analysis-agent
- Test recommend-agent
- Refine prompts

### 5.4 Cron Setup

**Edit crontab:**
```bash
crontab -e
```

**Add hourly job:**
```bash
# Run New Relic crawler every hour
0 * * * * cd /path/to/ai-monitoring && /path/to/venv/bin/python crawler.py >> logs/cron.log 2>&1
```

---

## 6. Testing

### 6.1 Crawler Tests

**Test Configuration:**
```bash
python crawler.py --validate-config
```

**Test Connection:**
```bash
python crawler.py --test-connection
```

**Dry Run:**
```bash
python crawler.py --dry-run
# Should show what would be collected without actual API calls
```

**Single App Test:**
```bash
python crawler.py --app-id prod-web-app
```

### 6.2 Agent Tests

**Test analysis-agent:**
```
1. Create sample JSON in data/ folder
2. In VS Code Copilot Chat:
   @analysis-agent analyze data/sample.json
3. Verify assessment.md generated
4. Check format and content
```

**Test recommend-agent:**
```
1. Create sample assessment.md with known issue
2. In VS Code Copilot Chat:
   @recommend-agent review assessment.md
3. Verify recommendations.md generated
4. Check code quality and specificity
```

### 6.3 End-to-End Test

**Full Workflow:**
```bash
# 1. Fetch data
python crawler.py

# 2. Analyze (in VS Code)
@analysis-agent analyze data/

# 3. Get recommendations
@recommend-agent review assessment.md

# 4. Verify outputs
ls -lh assessment.md recommendations.md
```

### 6.4 Validation Checklist

**Crawler:**
- [ ] Config loads correctly
- [ ] API authentication works
- [ ] Data fetched for all apps
- [ ] JSON files created with correct naming
- [ ] Old files cleaned up
- [ ] Errors logged properly

**analysis-agent:**
- [ ] Reads all JSON files
- [ ] Calculates health scores correctly
- [ ] Detects known issues
- [ ] Generates assessment.md
- [ ] Format matches specification
- [ ] Includes evidence and metrics

**recommend-agent:**
- [ ] Reads assessment.md
- [ ] Finds relevant code files
- [ ] Generates specific fixes
- [ ] Includes file paths and line numbers
- [ ] Code is syntactically valid
- [ ] Provides implementation steps

---

## Appendix A: File Structure

```
ai-monitoring/
├── config.yaml                      # Configuration
├── crawler.py                       # Data crawler script
├── requirements.txt                 # Python dependencies
├── README.md                        # Project documentation
│
├── .github/
│   └── copilot-instructions.md     # Custom agent definitions
│
├── .vscode/
│   └── settings.json               # VS Code settings
│
├── data/                           # Collected data (gitignore)
│   ├── prod-web-app-2026-02-06-14-30.json
│   ├── prod-api-2026-02-06-14-30.json
│   └── ...
│
├── logs/                           # Log files (gitignore)
│   ├── crawler.log
│   └── cron.log
│
├── assessment.md                   # Generated by analysis-agent
└── recommendations.md              # Generated by recommend-agent
```

## Appendix B: Troubleshooting

**Issue: API authentication failed**
```bash
# Check API key
echo $NEW_RELIC_API_KEY

# Test with curl
curl -X POST https://api.newrelic.com/graphql \
  -H "Content-Type: application/json" \
  -H "API-Key: $NEW_RELIC_API_KEY" \
  -d '{"query": "{ actor { user { name } } }"}'
```

**Issue: Agent not responding**
```
1. Check .vscode/settings.json exists
2. Check .github/copilot-instructions.md exists
3. Reload VS Code window
4. Try: @analysis-agent hello (should respond)
```

**Issue: Empty JSON files**
```bash
# Check config.yaml app IDs are correct
python crawler.py --list-apps

# Check New Relic account ID
python crawler.py --test-connection
```

**Issue: Crawler runs but no issues detected**
```
1. Check timeframe - might be looking at wrong period
2. Check baseline calculation - might need more historical data
3. Manually inspect JSON files to verify data quality
```

---

**End of Specification**

This is the complete technical specification for the AI-Powered Monitoring Assistant MVP. The system is designed to be:
- Simple (2 components, no complex infrastructure)
- Fast (2-3 days implementation)
- Practical (works in existing VS Code workflow)
- Maintainable (minimal dependencies, clear structure)
