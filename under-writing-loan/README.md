# Multi-Agent AI Loan Underwriting System

An educational project for learning AI agent orchestration, generative AI reasoning, hybrid OCR strategies, RAG (Retrieval Augmented Generation), and MCP (Model Context Protocol) integration through building a loan underwriting system.

## 🎯 Learning Objectives

- **Multi-agent orchestration**: Coordinate specialized AI agents using LangGraph
- **Document extraction**: Process loan documents with Azure Document Intelligence
- **RAG implementation**: Semantic policy retrieval using Azure AI Search
- **MCP pattern**: Abstract data access for clean agent architecture
- **Experiment tracking**: Log and compare AI experiments with MLflow
- **Cost optimization**: Understand economic tradeoffs in AI system design

## 🏗️ Architecture

The system processes loan applications through 4 specialized agents:

1. **Document Agent**: Extracts structured data from PDFs (pay stubs, bank statements, tax returns)
2. **Risk Agent**: Calculates financial metrics (DTI, LTV, PTI) and performs creditworthiness analysis
3. **Compliance Agent**: Checks application against lending policies using RAG
4. **Decision Agent**: Makes final lending decision with transparent reasoning

All agents are coordinated by **LangGraph** with state management and error handling.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Azure account with:
  - Azure OpenAI (GPT-4o, text-embedding-ada-002)
  - Azure Document Intelligence
  - Azure AI Search (Free tier)
- Jupyter environment (VS Code + Jupyter extension OR JupyterLab)

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd under-writing-loan
```

2. **Create virtual environment**
```bash
python3.10 -m venv venv
source venv/bin/activate  # macOS/Linux
# OR
.\venv\Scripts\activate   # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your Azure credentials
```

5. **Seed mock data**
```bash
python src/mcp/seed_data.py
```

6. **Start services**

Terminal 1 - MLflow tracking server:
```bash
mlflow server \
  --backend-store-uri sqlite:///data/mlflow.db \
  --default-artifact-root ./data/mlflow-artifacts \
  --host 127.0.0.1 \
  --port 5000
```

Terminal 2 - MCP server:
```bash
uvicorn src.mcp.server:app --reload --port 8000
```

7. **Validate setup**
```bash
# Open notebooks/00_setup_and_test.ipynb
# Run all cells to validate Azure connections
```

## 📓 Notebook Learning Path

Follow notebooks in sequence for progressive learning:

1. **00_setup_and_test.ipynb** - Validate Azure connections
2. **01_document_agent.ipynb** - Document extraction with Document Intelligence
3. **02_risk_agent.ipynb** - Financial analysis and MCP integration
4. **03_rag_system.ipynb** - Policy indexing and semantic search
5. **04_compliance_agent.ipynb** - RAG-powered policy compliance
6. **05_decision_agent.ipynb** - Final lending decisions
7. **06_orchestration.ipynb** - LangGraph multi-agent workflow
8. **07_end_to_end_demo.ipynb** - Complete pipeline with MLflow tracking

## 📁 Project Structure

```
under-writing-loan/
├── notebooks/              # Jupyter notebooks (primary interface)
├── src/
│   ├── agents/            # AI agent implementations
│   ├── mcp/               # Model Context Protocol server
│   ├── rag/               # RAG system components
│   ├── models.py          # Pydantic data models
│   ├── config.py          # Configuration management
│   └── utils.py           # Shared utilities
├── data/
│   ├── applications/      # Uploaded documents
│   ├── extracted/         # Extraction results
│   ├── policies/          # Lending policies for RAG
│   ├── mock_credit_bureau.db  # Mock credit data
│   └── database.sqlite    # Application metadata
├── tests/                 # Automated tests
└── docs/                  # Documentation
```

## 💰 Cost Optimization

The system demonstrates cost-effective AI strategies:

- **Document Intelligence first** (~$0.001/page): Handles document extraction
- **GPT-4o** (~$0.10-0.15/application): Efficient reasoning and analysis
- **Cost-effective approach**: Focus on Document Intelligence for reliable extraction

Expected cost for 100 test applications: **~$12-18**

## 🧪 Testing

Run unit tests:
```bash
pytest tests/
```

Test MCP server:
```bash
pytest tests/test_mcp_server.py
```

## 📚 Documentation

- [Simplified Architecture](docs/SIMPLIFIED_ARCHITECTURE.md) - System design overview
- [Specification](specs/001-ai-loan-underwriting-system/spec.md) - Feature requirements
- [Implementation Plan](specs/001-ai-loan-underwriting-system/plan.md) - Technical approach
- [Quickstart Guide](specs/001-ai-loan-underwriting-system/quickstart.md) - Detailed setup

## 🎓 Learning Outcomes

After completing all notebooks, you will understand:

- ✅ How to extract structured data from unstructured documents with Document Intelligence
- ✅ How to calculate and interpret financial risk metrics (DTI, LTV, PTI)
- ✅ How RAG improves AI accuracy by grounding responses in specific policies
- ✅ How to make transparent AI decisions with explainable reasoning
- ✅ How to orchestrate multi-agent workflows with state management
- ✅ How to track and compare AI experiments for continuous improvement
- ✅ How to optimize AI system costs through smart tool selection

## 🤝 Contributing

This is an educational project. Feel free to:
- Experiment with different prompts
- Add new test cases
- Modify risk analysis thresholds
- Contribute additional lending policies
- Share learnings and improvements

## 📄 License

MIT License - See LICENSE file for details

## 🆘 Troubleshooting

**Azure connection errors**: Verify credentials in `.env` and check Azure service quotas

**MCP server not responding**: Ensure server is running on port 8000 (`lsof -i :8000`)

**MLflow UI not loading**: Check if server is running on port 5000 (`lsof -i :5000`)

**Module import errors**: Activate virtual environment and reinstall dependencies

See [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for detailed solutions.

## 📞 Support

- Review notebook markdown cells for concept explanations
- Check [Quickstart Guide](specs/001-ai-loan-underwriting-system/quickstart.md) for setup issues
- Search Azure documentation for service-specific problems

---

**Happy learning!** 🏦🤖
