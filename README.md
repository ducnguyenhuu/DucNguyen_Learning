Duc Nguyen Huu — AI Engineering Projects
Hands-on projects I build to learn and apply agentic AI: multi-agent orchestration, RAG, MCP, coding agents, and AI-assisted operations.

I'm a Senior Software Engineer (.NET, Azure/AWS) and an M.S. in Computer Science (AI & Machine Learning) student at Georgia Tech. Most projects here are built with Spec-Driven Development: I write the spec, plan, and tasks with GitHub Spec Kit, then implement with Claude Code and GitHub Copilot under review. You'll see the .specify/, spec.md, plan.md, and tasks.md files that come out of that workflow.

Contact: duc.nguyenhuu.vn@gmail.com · LinkedIn · Carmel, IN

Featured Projects
Project	What it does	Key tech
Multi-Agent Loan Underwriting	Four specialized agents (Document, Risk, Compliance, Decision) process a loan application end to end and explain the decision	LangGraph, Azure OpenAI, Azure Document Intelligence, Azure AI Search (RAG), MCP, MLflow
One-Shot Coding Agent	Takes a plain-text task, explores the codebase, writes code, runs tests, and opens a pull request with no human input during the run	Python, LLM tool use, Git/GitHub automation
AI Log & APM Analysis	Pulls New Relic APM metrics, computes weighted 0–100 health scores, and uses Copilot agents to write findings and fix recommendations	Python, New Relic API, GitHub Copilot agents
Knowledge Base AI	Local, privacy-first document Q&A (like NotebookLM): ingest PDF/Word/Markdown/Excel and chat with cited answers, fully offline	FastAPI, React/TypeScript, Ollama, sentence-transformers, SQLAlchemy
More Projects
Project	What it does	Key tech
Human-AI Collaboration Platform	An agent breaks a project into tasks, assigns each to a human or an AI, and runs the workflow, pausing for human steps. Uses folder-based orchestration (Interpretable Context Methodology) instead of a multi-agent framework	Spec Kit, Claude Code, backend + frontend (in progress)
Consultant Board AI	A Copilot Chat skill that acts as a board of experts: clarifies a decision, debates it from several perspectives, and returns a structured decision report	GitHub Copilot agent skills, prompt design
Retail Shelf Monitoring	Computer-vision system for common retail shelf problems, built on public datasets	Python, Azure AI Vision
./stocktrader	Console stock analysis that combines ensemble forecasting, sentiment, and fundamental scoring	Python, Yahoo Finance data
Python Calculator	Small warm-up project for testing and agent workflows	Python, pytest
What These Projects Show
Agent orchestration: LangGraph state graphs, single-agent vs. multi-agent trade-offs, human-in-the-loop handoffs
Retrieval & grounding: RAG over policy documents, vector search, cited answers, swappable embedding/LLM providers
Tooling & integration: MCP for clean data access, OCR with Azure Document Intelligence, the New Relic API
Engineering discipline: spec-first development, tests, experiment tracking with MLflow, cost awareness in LLM design
Each project folder has its own README with setup and run instructions.
