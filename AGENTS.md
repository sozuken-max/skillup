# SkillUP AI Agent Guide

## Architecture Overview

SkillUP implements a **Hybrid Intelligent Reasoning Architecture** with two layers:

1. **Data Ingestion Layer**: Offline processing of job descriptions, course catalogs, and CVs into Neo4j knowledge graph and vector stores
2. **Inference Pipeline**: Real-time 3-stage reasoning (User Profile → Skill Gap → Course Recommendation) with RAG + LLM orchestration

**Key Components**:
- `app/app.py` - Streamlit orchestrator with embedded business logic
- `knowledgegraph/` - Neo4j operations
- `skillgap/` - Gap analysis against job market demand
- `recommender/` - CSP filtering, fuzzy logic, neural ranking, CBR

## Critical Workflows

### Testing
```bash
# Quick smoke tests (critical checks only)
uv run pytest tests/ -m smoke -v

# All unit tests with coverage
uv run pytest tests/ --cov=. --cov-report=html

# Via script (smoke/unit/coverage/all/quick)
./run_tests.sh smoke
# Or on Windows PowerShell:
# .\run_tests.ps1 smoke
```

### Development Setup
```bash
# Environment detection pattern
try:
    dbutils  # noqa
    IN_DATABRICKS = True
    # Use Delta tables
except NameError:
    IN_DATABRICKS = False
    # Use CSV fallbacks from data/
```

### Data Access Patterns
- **Source data**: `data/` directory (version controlled gold standards, test fixtures)
- **Artifacts**: `/Volumes/workspace/default/iss-scratchpad/data/` (generated/processed data, NOT in git)
- **Production**: Databricks Unity Catalog tables (`workspace.default.my_skills_future_course_directory`)

## Project Conventions

### Environment Variables
```python
# Required for full functionality
OPENAI_API_KEY=sk-...
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# Databricks (auto-detected)
DATABRICKS_HOST=...
DATABRICKS_CLIENT_ID=...
DATABRICKS_CLIENT_SECRET=...
```

### Service Integration
```python
# LLM calls with Databricks fallback
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        w = WorkspaceClient(...)
        api_key = w.secrets.get_secret("my-secrets", "openai-api-key01").value
    return OpenAI(api_key=api_key)
```

### Error Handling
```python
# Basic error handling pattern
try:
    # operation
except Exception as e:
    st.warning(f"⚠️ Operation failed: {e}")
```

### Data Flow
- **Local dev**: CSV files in `data/` → pandas DataFrames
- **Databricks**: Delta tables → Spark DataFrames → pandas conversion
- **Fallback logic**: Always check `IN_DATABRICKS` flag

## Integration Points

### External Dependencies
- **Databricks**: Delta tables, MLflow tracking, PySpark operations
- **Neo4j**: Knowledge graph queries, Cypher operations
- **OpenAI**: GPT-4-mini for chat, embeddings, RAG explanations
- **APIs**: MCF job portal scraping, SkillsFuture course catalog

### Cross-Component Communication
- **Session state**: Streamlit's `st.session_state` for user context
- **Module imports**: Relative imports from parent directory (`sys.path.insert(0, '..')`)
- **Configuration**: Scattered constants in app.py (refactoring planned)

## Key Files & Patterns

### Entry Points
- `app/app.py` - Main Streamlit application (monolithic)

### Configuration
- `app/config.py` - Centralized AppConfig with env var loading

### Business Logic
- `knowledgegraph/knowledgegraph.py` - Neo4j graph operations
- `skillgap/skillgap.py` - Market demand analysis
- `recommender/recommender.py` - Course ranking pipeline

### Data Management
- `data/gold_standard_*.json` - Validated training data
- `data/*.csv` - Local development fallbacks
- `/Volumes/.../data/` - Generated artifacts (not in git)

### Testing
- `tests/conftest.py` - Shared fixtures (mock Neo4j, OpenAI clients)
- `tests/pytest.ini` - Test configuration and markers
- `run_tests.sh` - Test runner script (Bash/Linux/macOS)
- `run_tests.ps1` - Test runner script (Windows PowerShell)
