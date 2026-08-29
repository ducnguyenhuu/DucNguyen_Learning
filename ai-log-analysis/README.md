# New Relic APM Health Assessment Tool

A Python-based tool for assessing the health of applications monitored by New Relic APM. This tool collects performance metrics, analyzes health scores, and generates comprehensive reports with AI-powered insights.

## Features

- 📊 **Multi-Metric Health Analysis** - Analyzes 5 key metric categories (Performance, Errors, Infrastructure, Database, API/Transactions)
- 🔄 **Multi-Profile Configuration** - Supports separate dev and prod environments
- 📈 **Weighted Health Scoring** - 0-100 health scores with severity categorization
- 🤖 **AI-Powered Insights** - GitHub Copilot agents for analysis and code recommendations
- 📝 **Markdown Reports** - Executive summaries with actionable recommendations
- 💾 **Smart Caching** - Reduces redundant API calls with configurable cache retention

## Requirements

- **Python 3.11+** (required)
- New Relic account with APM data
- New Relic User API key (NRAK-...)
- GitHub Copilot (optional, for AI-powered insights)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-log-analysis
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure New Relic Credentials

#### Create Dev Configuration

```bash
# Copy the example template
cp .newrelic_config.example.json .newrelic_config.dev.json

# Edit with your credentials
nano .newrelic_config.dev.json
```

Update the file with your New Relic credentials:

```json
{
  "api_key": "NRAK-YOUR_NEW_RELIC_USER_KEY_HERE",
  "account_id": "1234567",
  "app_ids": ["9876543", "1111111"],
  "app_name": "my-dev-application",
  "description": "Development environment"
}
```

#### Create Prod Configuration (Optional)

```bash
cp .newrelic_config.example.json .newrelic_config.prod.json
# Edit with production credentials
```

### 5. Run Health Assessment

```bash
# Default: dev profile, 1-day window
python main.py

# Specify profile and time period
python main.py --profile prod --days 7

# Analyze previously cached data offline
python main.py --from-file data/PROD_TMS-1d-2026-03-06-223409.json

# Validate configuration without running assessment
python main.py --validate-config --profile prod

# Skip saving data to cache
python main.py --no-cache --days 3

# Custom report output directory
python main.py --output-dir ./my-reports
```

## Configuration

### Profile Configuration Files

Configuration files are environment-specific and stored as `.newrelic_config.{profile}.json`:

- `.newrelic_config.dev.json` - Development environment
- `.newrelic_config.prod.json` - Production environment

**Required Fields:**
- `api_key` (string) - Your New Relic User API key
- `account_id` (string) - Your New Relic account ID (numeric)
- `app_ids` (array) - List of application IDs to assess
- `app_name` (string) - Application name for report generation
- `description` (string) - Optional description

### Application Defaults (config.yaml)

The `config.yaml` file contains application-wide default settings:

```yaml
api:
  timeout: 30                # API request timeout in seconds
  max_retries: 2            # Number of retry attempts for failed requests
  retry_delay: 5            # Delay between retries in seconds
  
cache:
  staleness: 3600           # Cache validity in seconds (1 hour)
  retention_days: 30        # Keep old data files for 30 days
  
logging:
  level: INFO               # Console log level (DEBUG, INFO, WARNING, ERROR)
  file_level: DEBUG         # Log file level (capture everything)
  
defaults:
  days: 30                  # Default time period for data collection
  profile: dev              # Default profile if not specified
```

**Configuration Priority:**
1. CLI arguments (highest priority)
2. Profile-specific JSON file (`.newrelic_config.{profile}.json`)
3. Application defaults (`config.yaml`)

### Time Period Options

The `--days` parameter accepts only these values:
- `3` - Last 3 days
- `7` - Last 7 days (one week)
- `14` - Last 14 days (two weeks)
- `30` - Last 30 days (one month, default)

## Project Structure

```
ai-log-analysis/
├── config.yaml                      # Application defaults
├── demo.py                          # Data collection & report generation
├── .newrelic_config.example.json   # Template (committed)
├── .newrelic_config.dev.json       # Dev credentials (gitignored)
├── .newrelic_config.prod.json      # Prod credentials (gitignored)
├── requirements.txt                 # Python dependencies
├── modules/                         # Core application modules
│   ├── __init__.py
│   ├── config_loader.py            # Configuration loading and validation
│   ├── api_client.py               # New Relic NerdGraph API wrapper
│   ├── health_calculator.py        # Health scoring engine (5-category weighted)
│   └── report_generator.py         # Markdown report generation
├── agents/                          # AI agent instruction files
│   ├── analysis-agent.md           # @analysis-agent full instructions
│   └── recommend-agent.md          # @recommend-agent full instructions
├── .github/agents/                  # VS Code Copilot Chat integration
│   ├── analysis-agent.agent.md     # @analysis-agent activation
│   └── recommend-agent.agent.md    # @recommend-agent activation
├── data/                           # Cached APM data JSON files (gitignored)
├── logs/                           # Application logs (gitignored)
├── reports/                        # Generated reports
│   ├── health-report-*.md          # Automated health reports
│   ├── assessment-*.md             # AI analysis assessments
│   └── recommendations-*.md        # AI fix recommendations
└── tests/                          # Test suite (399 tests)
    ├── __init__.py
    ├── test_config_loader.py
    ├── test_api_client.py
    ├── test_health_calculator.py
    ├── test_report_generator.py
    ├── test_analysis_agent.py
    ├── test_recommend_agent.py
    ├── test_documentation.py
    └── test_project_structure.py
```

## Usage Examples

### Basic Usage

```bash
# Run with default settings (dev profile, 30 days)
python crawler.py

# Specify time period
python crawler.py --days 7

# Use production profile
python crawler.py --profile prod
```

### Advanced Usage

```bash
# Production assessment with 14-day window
python crawler.py --profile prod --days 14

# Override timeout for slow networks
python crawler.py --profile dev --timeout 60

# Custom application assessment
python crawler.py --profile dev --app critical-service --days 3
```

## Testing

Run the test suite to verify your setup:

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_config_loader.py -v

# Run with coverage report
python3 -m pytest tests/ --cov=modules --cov-report=html
```

**Current Test Coverage:** 399 tests, 100% passing

## Troubleshooting

### Common Issues

#### Configuration Validation Errors

**Error:** `API key missing in configuration file`

**Solution:**
```bash
# Ensure you created the profile configuration file
cp .newrelic_config.example.json .newrelic_config.dev.json

# Edit and add your New Relic API key
nano .newrelic_config.dev.json
```

---

**Error:** `Account ID must be numeric. Expected format: 1234567`

**Solution:**
- Ensure `account_id` is a string containing only digits
- Example: `"account_id": "1234567"` ✅
- Invalid: `"account_id": "abc123"` ❌

---

**Error:** `app_ids must be a non-empty list`

**Solution:**
- Ensure `app_ids` is an array with at least one application ID
- Example: `"app_ids": ["9876543"]` ✅
- Invalid: `"app_ids": []` ❌

---

**Error:** `days must be one of [3, 7, 14, 30]`

**Solution:**
- Use only allowed values: 3, 7, 14, or 30
- Example: `python crawler.py --days 7` ✅
- Invalid: `python crawler.py --days 10` ❌

---

**Error:** `Profile file '.newrelic_config.prod.json' not found`

**Solution:**
```bash
# Create the missing profile configuration
cp .newrelic_config.example.json .newrelic_config.prod.json

# Edit with your production credentials
nano .newrelic_config.prod.json
```

#### Installation Issues

**Error:** `ModuleNotFoundError: No module named 'yaml'`

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

---

**Error:** `Python version mismatch`

**Solution:**
```bash
# Check Python version (must be 3.11+)
python3 --version

# If version is too old, install Python 3.11+
# macOS (using Homebrew):
brew install python@3.11

# Ubuntu/Debian:
sudo apt update
sudo apt install python3.11
```

#### API Connection Issues

**Error:** `Connection timeout to New Relic API`

**Solution:**
- Check your internet connection
- Increase timeout in config.yaml or via CLI:
  ```bash
  python crawler.py --timeout 60
  ```
- Verify firewall settings allow HTTPS connections

---

**Error:** `Invalid API key`

**Solution:**
- Verify your API key is a User API key (starts with `NRAK-`)
- Generate a new key at: `https://one.newrelic.com/api-keys`
- Ensure the key has appropriate permissions

## Security Best Practices

**⚠️ CRITICAL SECURITY WARNINGS:**

### Never Commit API Keys

- **DO NOT** commit `.newrelic_config.*.json` files to version control
- The `.gitignore` file automatically excludes `*.json` files
- Only commit `.newrelic_config.example.json` (template with placeholders)

### Verify .gitignore Protection

```bash
# Verify JSON files are ignored
git status

# Should NOT show:
# - .newrelic_config.dev.json
# - .newrelic_config.prod.json

# Should show (if not committed):
# ?? .newrelic_config.example.json (template only)
```

### Creating Profile Configurations

**Safe Workflow:**

1. Copy the example template:
   ```bash
   cp .newrelic_config.example.json .newrelic_config.dev.json
   ```

2. Edit the new file with real credentials:
   ```bash
   nano .newrelic_config.dev.json
   ```

3. Verify it's gitignored:
   ```bash
   git status  # Should NOT appear in changes
   ```

4. Never use `git add -A` or `git add .` - always specify files explicitly

### Environment-Specific Credentials

- Use `.newrelic_config.dev.json` for development/testing
- Use `.newrelic_config.prod.json` for production assessments
- Keep credentials separate and secure
- Rotate API keys periodically

### API Key Permissions

Your New Relic User API key needs:
- ✅ Read access to APM data
- ✅ Read access to NRQL queries
- ❌ No write permissions required (read-only operation)

## AI-Powered Insights

This tool integrates with GitHub Copilot custom agents for AI-powered health analysis and code fix recommendations. Two agents work together in a pipeline:

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **@analysis-agent** | Expert SRE — analyzes collected data, calculates health scores, detects issues | JSON data file in `data/` | `reports/assessment-{app}-{timestamp}.md` |
| **@recommend-agent** | Expert software engineer — reads assessments, finds affected code, generates fixes | Assessment file in `reports/` | `reports/recommendations-{app}-{timestamp}.md` |

### Prerequisites

- **GitHub Copilot** subscription (individual or business)
- **VS Code** with GitHub Copilot Chat extension installed
- Agent files already included in this repository (no additional setup needed)

### Agent Files

The agent instruction files are pre-configured in the repository:

```
agents/
├── analysis-agent.md          # Full analysis instructions, scoring methodology, output format
└── recommend-agent.md         # Full recommendation instructions, root cause patterns, fix template

.github/agents/
├── analysis-agent.agent.md    # VS Code Copilot Chat integration for @analysis-agent
└── recommend-agent.agent.md   # VS Code Copilot Chat integration for @recommend-agent
```

### VS Code Setup

The `.github/agents/` directory is automatically recognized by VS Code Copilot Chat. No additional configuration is required — just open the workspace and the agents are available.

To verify the agents are loaded, type `@` in the Copilot Chat input and you should see `analysis-agent` and `recommend-agent` in the autocomplete list.

### End-to-End Workflow

#### Daily Health Monitoring

```bash
# 1. Collect fresh data from New Relic
python demo.py --profile prod --days 1

# 2. In VS Code Copilot Chat:
#    @analysis-agent analyze the latest data file in data/
#    → Generates: reports/assessment-{app}-{timestamp}.md

# 3. If issues found:
#    @recommend-agent review the latest assessment
#    → Generates: reports/recommendations-{app}-{timestamp}.md

# 4. Implement fixes following the recommendations
# 5. Check off items in the recommendations file as they are applied
```

#### Incident Investigation

```bash
# 1. Collect data for the incident period
python demo.py --profile prod --days 1

# 2. In VS Code Copilot Chat:
#    @analysis-agent analyze the latest data — focus on critical issues
#    → Review the Critical Issues 🔴 section

# 3. Get targeted fix recommendations:
#    @recommend-agent provide fixes for the critical issues in the latest assessment
#    → Get exact code changes with file paths and line numbers

# 4. Apply the recommended fix, deploy, verify
```

#### Post-Deployment Verification

```bash
# 1. Deploy your changes
# 2. Wait 30 minutes for metrics to stabilize
# 3. Collect fresh data
python demo.py --profile prod --days 1

# 4. In VS Code Copilot Chat:
#    @analysis-agent analyze the latest data and compare with the previous assessment
#    → Verify health scores improved and no regressions introduced
```

### Expected Outputs

**Assessment files** (`reports/assessment-{app}-{timestamp}.md`):
- 200–500 lines
- Executive summary with overall health score (0–100)
- 5-category score breakdown (Performance, Errors, Infrastructure, Database, API)
- Critical issues and warnings with specific metric values
- Slow endpoint analysis, database deep dive, trend analysis
- Checkbox tracking for identified issues

**Recommendation files** (`reports/recommendations-{app}-{timestamp}.md`):
- 300–800 lines
- Fix tracking checklist with checkboxes per issue
- Exact file paths, current code, and recommended fix code
- Impact estimates, effort estimates, risk assessment
- Implementation plan with priority ordering
- Context section for other agents/developers to implement fixes

**Automated health reports** (`reports/health-report-{app}-{timestamp}.md`):
- Generated by `demo.py` during data collection
- Metric breakdowns and severity indicators
- Serves as a quick reference; agents provide deeper analysis

## Roadmap

### ✅ Completed (Epic 1) — Configuration Management
- [x] Project structure initialization
- [x] Configuration loader with multi-profile support
- [x] Configuration validation with fail-fast
- [x] Setup documentation and templates

### ✅ Completed (Epic 2) — Data Collection
- [x] New Relic API client with retry logic
- [x] Performance metrics collection
- [x] Error metrics collection
- [x] Infrastructure metrics collection
- [x] Database metrics collection
- [x] API/Transaction metrics collection
- [x] Data caching with auto-cleanup
- [x] Comprehensive logging with progress indicators

### ✅ Completed (Epic 3) — Health Analysis Engine
- [x] Health score calculation engine with weighted algorithm
- [x] Severity categorization with visual indicators
- [x] Issue detection and findings generation

### ✅ Completed (Epic 4) — Report Generation
- [x] Report generator with executive summary
- [x] Detailed metric breakdown sections
- [x] Findings and recommendations sections with file naming

### ✅ Completed (Epic 5) — AI Agent Integration
- [x] @analysis-agent instruction file with health scoring logic
- [x] @recommend-agent instruction file with code-specific fixes
- [x] AI agent usage workflow documentation

### ✅ Completed (Epic 6) — Testing & Finalization
- [x] Comprehensive test suite with 94% coverage (512 tests)
- [x] Main CLI orchestrator with full workflow (`main.py`)
- [x] Code quality review and documentation finalization

## Contributing

This is a learning project. Contributions and suggestions are welcome!

## License

[Specify your license here]

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review test suite: `python3 -m pytest tests/ -v`
3. Check logs in `/logs` directory for detailed error messages

## Changelog

### v1.0.0 (2026-03-09)
- **Epic 6 complete** — project finalized
- Comprehensive test suite: 530+ tests, 94% coverage
- Production CLI orchestrator (`main.py`) with `--from-file`, `--no-cache`, `--validate-config`
- Added pytest-cov to requirements
- Code quality review and documentation finalization

### v0.5.0 (2026-03-09)
- AI agent integration (@analysis-agent, @recommend-agent)
- VS Code Copilot Chat agent files
- End-to-end workflow documentation
- 399 tests passing

### v0.4.0 (2026-03-06)
- Report generator with executive summary and metric breakdowns
- Findings and recommendations sections
- Timestamped markdown reports in reports/ directory

### v0.3.0 (2026-02-28)
- Health score calculation engine with 5-category weighted algorithm
- Severity categorization (Excellent/Good/Warning/Critical)
- Issue detection and findings generation

### v0.2.0 (2026-02-20)
- New Relic NerdGraph API client with retry logic
- Performance, error, infrastructure, database, API metrics collection
- Data caching with auto-cleanup
- Comprehensive logging with progress indicators

### v0.1.0 (2026-02-16)
- Initial project setup
- Configuration management system
- Multi-profile environment support
- Comprehensive test suite (59 tests)
- Setup documentation

---

**Built with Python 3.11+ | Powered by New Relic APM | Enhanced by GitHub Copilot**
