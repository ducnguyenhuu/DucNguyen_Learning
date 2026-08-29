# Retail Shelf Monitoring Constitution

## Core Principles

### I. Learning-First Approach (FOUNDATIONAL)
<!-- This is a research project for learning Azure AI, ML, and Computer Vision -->
Target audience: Junior Python developers; Complexity must serve educational value, not production requirements; Simple, focused scenarios for 4 challenges only; Public datasets - no complex data pipelines; Clear, readable code over clever abstractions; No production-scale complexity (microservices, K8s, real-time streaming, edge deployment); Start simple → iterate → add complexity only when understood

### II. Production-Standard Structure, Simple Implementation
<!-- Code organization follows professional Python standards, implementations stay simple -->
Standard Python package layout: `src/`, `tests/`, proper `__init__.py`; One class per file (unless tightly coupled helpers); Clear separation of concerns (models, services, core logic); Type hints + docstrings (Google/NumPy style) mandatory; Modular design: single responsibility per module

### III. Educational Documentation (MANDATORY)
<!-- Every code generation must include explanatory markdown for learning -->
Required markdown format in `docs/guides/` or `docs/implementations/`: What (brief description), Why (approach rationale and tradeoffs), How It Works (step-by-step explanation), Key Concepts (Python/Azure concepts taught), Usage Example (working code example), Next Steps (extension suggestions)

### IV. Code Quality for Learning
<!-- Code must be educational first, performant second -->
Clear variable names (avoid abbreviations); Small functions (<50 lines preferred); Comments explain "why", not "what"; Flat structure over deep nesting; Error messages that teach (explain what + why); Print/log intermediate steps for visibility


## Python Standards

### Required Practices
- Python 3.10+, type hints for all function signatures
- Virtual environment for isolation
- Docstrings for all public functions/classes
- PEP 8 style guide compliance
- Use `pathlib` for file paths (not string concat)
- Context managers (`with`) for resources
- Pin versions in `requirements.txt`, separate `requirements-dev.txt`

### Testing
- Unit tests with pytest for core logic only
- Test structure mirrors `src/` structure
- Naming: `test_<function>_<scenario>`

## Azure Integration

### Service Usage
- Free Tier services prioritized
- Credentials in `.env` (never commit)
- Official Azure SDK libraries only
- Handle API rate limits gracefully
- Log Azure API calls for debugging
- Document estimated costs
- Shutdown unused compute resources

## Task Completion Checklist

For each feature implementation:

- [ ] Clear Python code with type hints
- [ ] Explanatory markdown (What/Why/How)
- [ ] Production package organization
- [ ] Basic unit tests (if applicable)
- [ ] Working usage example
- [ ] Code comments for non-obvious decisions

## Code Review Criteria

Verify all generated code:

1. **Educational?** Junior developer can understand?
2. **Simple?** Could it be simpler while teaching the concept?
3. **Structured?** Follows Python best practices?
4. **Documented?** Explanatory markdown included?
5. **Working?** Runnable with provided example?

## Scope Boundaries

### In Scope
- 4 challenges with public datasets (SKU-110K, etc.)
- Azure AI services (Custom Vision, Document Intelligence, Azure ML)
- Local development with Jupyter notebooks for demonstration
- Python modules with production-standard structure
- Basic MLOps with Azure ML

### Out of Scope (Too Complex for Learning)
- UI development (web/mobile interfaces)
- Real-time camera feeds, IoT Hub, Edge deployment
- Multi-region deployment, Kubernetes
- Microservices architecture
- Enterprise patterns (unless explicitly learning them)
- Advanced monitoring beyond basics

## Governance

**Authority**: This constitution supersedes feature complexity preferences.

**Decision Framework**:
1. Choose simpler approach
2. Prioritize learning value over production features
3. Generate explanatory documentation
4. Ask: "Would a junior developer understand this?"

**Amendment Requirements**:
- Rationale for change
- Impact on existing code
- Updated version number

**Version**: 1.1.0 | **Ratified**: December 10, 2025 | **Last Amended**: December 10, 2025

---

## Amendment History

### Amendment 1 - Backend Development Scope Addition (v1.1.0)
**Date**: December 10, 2025  
**Status**: Approved

**Change**: Removed "FastAPI or REST API development" from Out of Scope section.

**Justification**: 
- User explicitly requested full-stack learning including "SQL, data modeling, and FastAPI"
- Educational value: Teaches backend development skills alongside ML challenges
- Complexity managed: Sequential implementation (database → API → ML) prevents overwhelm
- Scope addition: PostgreSQL database (5 normalized tables) + FastAPI REST API (12-15 endpoints)
- Aligns with plan.md Constitution Check §4 (justified violation for backend layer)

**Impact**: 
- Adds 2 weeks to timeline (10 weeks ML → 12 weeks total)
- Adds ~32 backend-related tasks to implementation (database setup, API development, CRUD operations)
- No conflict with Core Principles I-IV (learning-first approach maintained)

**Referenced Artifacts**:
- SPECIFICATION.md §10 (Database Design), §11 (API Specification)
- research.md R7 (Database Design Strategy), R8 (FastAPI Architecture Strategy)
- plan.md Phase 1 (Database + API Infrastructure)
- tasks.md T009-T024 (Foundational Backend), T095-T126 (API Integration)
