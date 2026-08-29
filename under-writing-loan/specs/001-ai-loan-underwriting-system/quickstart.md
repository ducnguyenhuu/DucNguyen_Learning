# Quickstart Guide

**Feature**: Multi-Agent AI Loan Underwriting System  
**Last Updated**: November 19, 2025

## Overview

This guide will walk you through setting up your development environment and running your first loan underwriting workflow. Expected setup time: **20-30 minutes**.

---

## Prerequisites

### Required Software

| Software | Version | Purpose | Download |
|----------|---------|---------|----------|
| **Python** | 3.10+ | Core language | https://www.python.org/downloads/ |
| **VS Code** or **JupyterLab** | Latest | Notebook development | https://code.visualstudio.com/ |
| **Git** | Any | Version control | https://git-scm.com/downloads |
| **Azure Account** | Free tier | OpenAI + Document Intelligence + AI Search | https://azure.microsoft.com/free/ |

### Azure Resources Needed

You'll create these during setup (all have free tier or pay-as-you-go):

1. **Azure OpenAI Service**
   - Models: `gpt-4`, `gpt-4-vision-preview`, `text-embedding-ada-002`
   - Free tier: No (pay per token)
   - Estimated cost: <$10 for 50 test applications
   
2. **Azure Document Intelligence**
   - Prebuilt models: Invoice, Tax W-2, ID Document
   - Free tier: 500 pages/month first month
   - Estimated cost: ~$0.10 for 100 documents after free tier
   
3. **Azure AI Search**
   - Tier: Free (F0)
   - Limitations: 50 MB storage, 3 indexes
   - Cost: $0 (sufficient for educational use)

---

## Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/under-writing-loan.git
cd under-writing-loan

# Verify structure
ls -la
# Expected: notebooks/, data/, src/, docs/, specs/, tests/
```

---

## Step 2: Set Up Python Environment

### Option A: Using `venv` (Recommended)

```bash
# Create virtual environment
python3.10 -m venv venv

# Activate
source venv/bin/activate  # macOS/Linux
# OR
.\venv\Scripts\activate   # Windows

# Upgrade pip
pip install --upgrade pip
```

### Option B: Using `conda`

```bash
# Create environment
conda create -n loan-underwriting python=3.10

# Activate
conda activate loan-underwriting
```

---

## Step 3: Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Verify installation
python -c "import openai, langchain, langgraph, azure.ai.formrecognizer, azure.search.documents, mlflow; print('All imports successful')"
```

**Expected `requirements.txt` content** (if not present, create it):
```txt
openai>=1.0.0
langchain>=0.1.0
langgraph>=0.0.20
azure-ai-formrecognizer>=3.3.0
azure-search-documents>=11.4.0
pydantic>=2.0.0
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
mlflow>=2.8.0
pdfplumber>=0.10.0
plotly>=5.17.0
python-dotenv>=1.0.0
jupyter>=1.0.0
ipykernel>=6.25.0
pytest>=7.4.0
requests>=2.31.0
```

---

## Step 4: Configure Azure Services

### 4.1 Create Azure OpenAI Service

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **"Create a resource"** → Search **"Azure OpenAI"**
3. Click **"Create"**:
   - **Subscription**: Choose your subscription
   - **Resource Group**: Create new: `rg-loan-underwriting`
   - **Region**: `East US` (check model availability)
   - **Name**: `openai-loan-underwriting`
   - **Pricing Tier**: Standard S0
4. Click **"Review + Create"** → **"Create"**
5. Once deployed, go to resource → **"Keys and Endpoint"**:
   - Copy **Key 1** → Save as `AZURE_OPENAI_API_KEY`
   - Copy **Endpoint** → Save as `AZURE_OPENAI_ENDPOINT`

### 4.2 Deploy Models

1. In Azure OpenAI resource, click **"Model deployments"** → **"Manage Deployments"**
2. Deploy 3 models:

| Model | Deployment Name | Use Case | Tokens/Min |
|-------|----------------|----------|------------|
| `gpt-4` | `gpt-4` | Document extraction, risk analysis, decisions | 30K |
| `gpt-4-vision-preview` | `gpt-4-vision` | Fallback OCR for complex documents | 10K |
| `text-embedding-ada-002` | `text-embedding-ada-002` | RAG embeddings | 120K |

**Important**: Use exact deployment names shown above (code expects these).

### 4.3 Create Document Intelligence

1. Azure Portal → **"Create a resource"** → **"Document Intelligence"**
2. **Create**:
   - **Resource Group**: `rg-loan-underwriting` (same as OpenAI)
   - **Region**: Same as OpenAI
   - **Name**: `doc-intelligence-loan`
   - **Pricing Tier**: Free F0 (or Standard S0)
3. Deploy → **"Keys and Endpoint"**:
   - Copy **Key 1** → Save as `AZURE_DOCUMENT_INTELLIGENCE_KEY`
   - Copy **Endpoint** → Save as `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`

### 4.4 Create Azure AI Search

1. Azure Portal → **"Create a resource"** → **"Azure AI Search"**
2. **Create**:
   - **Resource Group**: `rg-loan-underwriting`
   - **Service name**: `search-loan-policies`
   - **Location**: Same region
   - **Pricing Tier**: **Free** (F0)
3. Deploy → **"Keys"**:
   - Copy **Primary admin key** → Save as `AZURE_SEARCH_ADMIN_KEY`
   - Copy **URL** → Save as `AZURE_SEARCH_ENDPOINT`

---

## Step 5: Configure Environment Variables

Create `.env` file in project root:

```bash
# Navigate to project root
cd /path/to/under-writing-loan

# Create .env file
touch .env
```

Edit `.env` with your Azure credentials:

```bash
# Azure OpenAI
AZURE_OPENAI_API_KEY=your_openai_key_here
AZURE_OPENAI_ENDPOINT=https://openai-loan-underwriting.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_GPT4=gpt-4
AZURE_OPENAI_DEPLOYMENT_GPT4_VISION=gpt-4-vision
AZURE_OPENAI_DEPLOYMENT_EMBEDDING=text-embedding-ada-002

# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_doc_intelligence_key_here
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://doc-intelligence-loan.cognitiveservices.azure.com/

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://search-loan-policies.search.windows.net
AZURE_SEARCH_ADMIN_KEY=your_search_admin_key_here
AZURE_SEARCH_INDEX_NAME=lending-policies-index

# MLflow
MLFLOW_TRACKING_URI=http://127.0.0.1:5000

# MCP Server
MCP_SERVER_URL=http://localhost:8000
```

**Security Note**: Add `.env` to `.gitignore` to prevent committing credentials.

---

## Step 6: Initialize Project Directories

```bash
# Create required directories
mkdir -p data/uploaded
mkdir -p data/extracted
mkdir -p data/policies
mkdir -p data/mlflow-artifacts

# Create SQLite databases (empty for now)
touch data/mock_credit_bureau.db
touch data/database.sqlite

# Verify structure
tree data -L 2
# Expected:
# data/
# ├── uploaded/
# ├── extracted/
# ├── policies/
# ├── mlflow-artifacts/
# ├── mock_credit_bureau.db
# └── database.sqlite
```

---

## Step 7: Start MLflow Tracking Server

Open a **new terminal** (keep it running):

```bash
# Activate environment
source venv/bin/activate  # or conda activate loan-underwriting

# Start MLflow server
mlflow server \
  --backend-store-uri sqlite:///data/mlflow.db \
  --default-artifact-root ./data/mlflow-artifacts \
  --host 127.0.0.1 \
  --port 5000

# Keep this terminal open - server must run during development
```

**Verify**: Open browser to http://localhost:5000 → Should see MLflow UI

---

## Step 8: Seed Mock Credit Bureau Database

Open **another new terminal**:

```bash
# Activate environment
source venv/bin/activate

# Start MCP server
uvicorn src.mcp.server:app --reload --port 8000

# Keep this terminal open
```

In **yet another terminal**, seed database:

```bash
# Activate environment
source venv/bin/activate

# Run seed script
python src/mcp/seed_data.py

# Expected output:
# Successfully seeded 4 credit profiles:
#   - Test Excellent (111-11-1111): Score 780
#   - Test Good (222-22-2222): Score 720
#   - Test Fair (333-33-3333): Score 670
#   - Test Poor (444-44-4444): Score 590
```

**Verify**: 
```bash
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "database": {"credit_bureau": true, "application_db": true}
# }
```

---

## Step 9: Run First Notebook

### Open Jupyter

**Option A: VS Code**
```bash
# Open VS Code
code .

# Install Python extension if not installed
# Open: notebooks/00_setup_and_test.ipynb
# Select kernel: Python 3.10 (venv or conda environment)
```

**Option B: JupyterLab**
```bash
jupyter lab

# Navigate to notebooks/00_setup_and_test.ipynb
```

### Run Setup Notebook

Execute all cells in `00_setup_and_test.ipynb`:

**Expected output**:
- ✅ Azure OpenAI connection successful
- ✅ Document Intelligence connection successful
- ✅ Azure AI Search connection successful
- ✅ MLflow tracking server reachable
- ✅ MCP server health check passed
- ✅ All 4 test models listed

**If any checks fail**, see [Troubleshooting](#troubleshooting) below.

---

## Step 10: Process Your First Application

### Run Document Agent Notebook

1. Open `notebooks/01_document_agent.ipynb`
2. Execute cells sequentially
3. This notebook will:
   - Load a sample pay stub PDF
   - Extract structured data using Document Intelligence
   - Demonstrate fallback to GPT-4 Vision (if needed)
   - Validate extraction quality
   - Log results to MLflow

**Expected output**:
```python
{
  "document_id": "DOC-001-1",
  "document_type": "pay_stub",
  "extraction_method": "document_intelligence",
  "confidence_score": 0.92,
  "structured_data": {
    "employer_name": "Acme Corp",
    "gross_income": 8500.00,
    "net_income": 6200.00,
    ...
  }
}
```

### View Results in MLflow

1. Open http://localhost:5000
2. Click **"loan-underwriting"** experiment
3. See your first run with metrics:
   - `extraction_time_seconds`
   - `confidence_score`
   - `total_cost_usd`

---

## Verification Checklist

Before proceeding to advanced notebooks, ensure:

- [ ] Python 3.10+ installed and virtual environment active
- [ ] All dependencies installed (`pip list | grep langchain` shows packages)
- [ ] Azure OpenAI service created with 3 models deployed
- [ ] Azure Document Intelligence service created
- [ ] Azure AI Search service created (Free tier)
- [ ] `.env` file configured with all credentials
- [ ] MLflow server running at http://localhost:5000
- [ ] MCP server running at http://localhost:8000 (health check passes)
- [ ] Mock credit database seeded (4 test profiles)
- [ ] `00_setup_and_test.ipynb` all cells pass ✅
- [ ] `01_document_agent.ipynb` successfully extracts document data

---

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'openai'`

**Solution**:
```bash
# Verify virtual environment is activated
which python  # Should show venv path, not system Python

# Reinstall dependencies
pip install -r requirements.txt
```

---

### Issue: Azure OpenAI 401 Unauthorized

**Causes**:
1. Incorrect API key in `.env`
2. Wrong endpoint format
3. Model not deployed

**Solution**:
```bash
# Verify credentials
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('AZURE_OPENAI_API_KEY'))"

# Test endpoint manually
curl -X POST "https://YOUR_ENDPOINT/openai/deployments/gpt-4/chat/completions?api-version=2024-02-15-preview" \
  -H "api-key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}],"max_tokens":5}'

# Should return JSON response, not 401
```

---

### Issue: Document Intelligence 403 Forbidden

**Cause**: Wrong endpoint or key, or service not provisioned

**Solution**:
```bash
# Verify endpoint format (must end with /)
echo $AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
# Should be: https://YOUR_NAME.cognitiveservices.azure.com/

# Test with curl
curl -X GET "https://YOUR_ENDPOINT/formrecognizer/v2.1/prebuilt/invoice/analyzeResults/test" \
  -H "Ocp-Apim-Subscription-Key: YOUR_KEY"

# Should return 400 (wrong ID) not 403
```

---

### Issue: MLflow UI not loading

**Cause**: Server not started or port conflict

**Solution**:
```bash
# Check if server is running
ps aux | grep mlflow

# If not running, restart
mlflow server --backend-store-uri sqlite:///data/mlflow.db \
              --default-artifact-root ./data/mlflow-artifacts \
              --host 127.0.0.1 \
              --port 5000

# If port 5000 in use, change to 5001 (update .env MLFLOW_TRACKING_URI)
```

---

### Issue: MCP Server 404 on `/credit/{ssn}`

**Cause**: Database not seeded

**Solution**:
```bash
# Run seed script
python src/mcp/seed_data.py

# Verify database has data
sqlite3 data/mock_credit_bureau.db "SELECT ssn, credit_score FROM credit_reports;"

# Expected output:
# 111-11-1111|780
# 222-22-2222|720
# 333-33-3333|670
# 444-44-4444|590
```

---

### Issue: Azure AI Search index creation fails

**Cause**: Free tier limit reached (3 indexes max) or wrong credentials

**Solution**:
```bash
# List existing indexes
curl -X GET "https://YOUR_SEARCH_NAME.search.windows.net/indexes?api-version=2023-11-01" \
  -H "api-key: YOUR_ADMIN_KEY"

# Delete unused indexes (if needed)
curl -X DELETE "https://YOUR_SEARCH_NAME.search.windows.net/indexes/old-index?api-version=2023-11-01" \
  -H "api-key: YOUR_ADMIN_KEY"

# Free tier allows only 3 indexes total
```

---

### Issue: Jupyter kernel won't start

**Solution**:
```bash
# Install ipykernel in environment
pip install ipykernel

# Register kernel
python -m ipykernel install --user --name=loan-underwriting --display-name="Python (Loan Underwriting)"

# Restart VS Code or JupyterLab
# Select the new kernel from dropdown
```

---

### Issue: "Rate limit exceeded" from Azure OpenAI

**Cause**: Exceeded tokens-per-minute quota (30K for GPT-4)

**Solution**:
```bash
# Add retry logic with exponential backoff (already in src/utils/retry.py)
# Or request quota increase:
# Azure Portal → OpenAI resource → "Quotas" → "Request quota increase"

# Temporary: Reduce concurrent requests or test with fewer documents
```

---

## Next Steps

Once setup is complete:

1. **Continue with Notebooks**:
   - `02_risk_agent.ipynb` - Analyze creditworthiness using extracted data + credit report
   - `03_rag_system.ipynb` - Set up policy document retrieval
   - `04_compliance_agent.ipynb` - Check policies with RAG
   - `05_decision_agent.ipynb` - Make final lending decisions
   - `06_orchestration.ipynb` - LangGraph multi-agent workflow
   - `07_end_to_end_demo.ipynb` - Complete application processing

2. **Explore MLflow**:
   - Compare runs with different prompts
   - Track cost per application
   - Analyze extraction confidence patterns

3. **Customize System**:
   - Add your own lending policies to `data/policies/`
   - Create custom document extraction templates
   - Tune risk assessment thresholds

4. **Read Documentation**:
   - `docs/SIMPLIFIED_ARCHITECTURE.md` - System design
   - `specs/001-ai-loan-underwriting-system/spec.md` - Requirements
   - `specs/001-ai-loan-underwriting-system/research.md` - Technology decisions

---

## Cost Management

**Estimated Costs for 100 Test Applications**:

| Service | Usage | Cost |
|---------|-------|------|
| Azure OpenAI (GPT-4) | ~1.2M tokens | $12-18 |
| Azure OpenAI (Vision) | ~10 images (fallback) | $0.20-0.30 |
| Azure OpenAI (Embeddings) | ~50K tokens | $0.002 |
| Document Intelligence | ~100 pages (after free tier) | $0.10 |
| Azure AI Search | Free tier | $0 |
| **Total** | | **~$12-20** |

**Cost Reduction Tips**:
- Use GPT-3.5-turbo for non-critical agents (10x cheaper)
- Cache embeddings (don't re-embed same policy chunks)
- Process documents in batches during off-peak hours
- Use Document Intelligence aggressively (100x cheaper than Vision)

---

## Support

**Issues or Questions**:
1. Check [Troubleshooting](#troubleshooting) section above
2. Review `docs/SIMPLIFIED_ARCHITECTURE.md` for design clarifications
3. Search Azure documentation for service-specific issues
4. Open GitHub issue with error logs and steps to reproduce

**Logs to Include**:
- Jupyter notebook cell output (copy entire traceback)
- MLflow run details (run ID, error messages)
- Azure service error responses (sanitize credentials)
- `.env` file structure (DO NOT share actual keys)

---

## Summary

You now have:
- ✅ Fully configured Azure services (OpenAI, Document Intelligence, AI Search)
- ✅ Running MLflow tracking server for experiment management
- ✅ Running MCP server with seeded mock credit data
- ✅ Validated setup with first document extraction

**Ready to build**: Proceed to `02_risk_agent.ipynb` to continue the learning path.

**Development workflow**:
1. Make changes in notebooks or `src/` modules
2. Run cells to test (MLflow auto-logs results)
3. Check MLflow UI to compare experiments
4. Iterate on prompts and thresholds
5. Document learnings in notebook markdown cells

**Happy underwriting!** 🏦🤖
