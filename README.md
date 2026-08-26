# SkillUP 🚀

> **Solving the "Discovery Crisis"** — AI-Powered Personalized Learning Path Coach for Singapore's Adult Upskilling Ecosystem

**NUS-ISS | Intelligent Reasoning Systems | AY2025/26 | AIS08 Group 3**

---

## Problem Statement

Singapore faces a critical **navigation gap** in its upskilling ecosystem:

| Metric | Value |
|--------|-------|
| Singaporeans enrolled in SSG training (2024) | **555K** |
| YoY surge in SkillsFuture Credit usage | **35%** |
| SG employers struggling to find skilled talent | **83%** |

The **MySkillsFuture** portal is a *directory*, not an *advisor*. It tells users a course exists but cannot tell them if it is the right next step. With **9,000+ courses** and no personalised guidance, learners face suboptimal course selection, wasted subsidies, and slower career transitions.

## Our Solution

SkillUP is an **AI-powered course recommendation system** that:

1. Takes a user's **CV**, **target career role**, **budget**, **time**, and **learning preferences**
2. Cross-references against **real Singapore job market demand**
3. Generates a **personalised, sequenced, explainable course pathway** using SkillsFuture-eligible programmes

### Key Capabilities

| Capability | Description |
|------------|-------------|
| 🗣️ Natural Language Interaction | Chat-based onboarding + automatic CV parsing |
| 📊 Market-Driven Gap Analysis | Map skills against real SG job demand data |
| 🛤️ Constraint-Aware Pathways | Sequenced courses respecting budget, time, modality |
| 💡 Explainable Recommendations | Users understand *why* each course is chosen |
| 🧠 Hybrid Reasoning MVP | Multi-paradigm AI advisory demonstrating feasibility |

## Architecture Overview

SkillUP employs a **Hybrid Intelligent Reasoning Architecture** with two major layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                   DATA INGESTION LAYER                          │
│  Job Descriptions (MCF) · Course Catalogue (SSG)               │
│  Peer CVs (Samples) · Course Ratings + Reviews                 │
│                                                                 │
│  NLP Parsing → Embeddings → Knowledge Graph Build               │
│         ┌──────────────┐    ┌──────────────────┐               │
│         │ Knowledge    │    │ Vector Store +    │               │
│         │ Graph (Neo4j)│    │ Ratings Data      │               │
│         └──────┬───────┘    └────────┬─────────┘               │
├────────────────┼────────────────────┼──────────────────────────┤
│                INFERENCE & RECOMMENDATION PIPELINE              │
│                                                                 │
│  Uploaded CV → Onboarding Chat → Role, Budget, Time             │
│                                                                 │
│  ┌─────────────────────────────────────────────────┐           │
│  │          RAG + LLM Orchestration Layer           │           │
│  │    LLM retrieves from each reasoning stage       │           │
│  └──────────────────┬──────────────────────────────┘           │
│                     │                                           │
│  Stage 1: User Profile Model                                    │
│    CV parsing → skill extraction → skill + constraint vectors   │
│                     ↓                                           │
│  Stage 2: Skill Gap Model                                       │
│    KG traversal + competing experts (JD demand vs peer CV)      │
│                     ↓                                           │
│  Stage 3: Course Recommendation                                 │
│    CSP filtering · Fuzzy logic · Neural ranker · CBR            │
│                     ↓                                           │
│  LLM generates grounded explanations                            │
│                     ↓                                           │
│  ✅ Personalised Learning Path + Explanations                   │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
skillup/
├── README.md                          # This file
├── docs/                              # 📖 Project documentation
│   ├── architecture.md                # System architecture deep dive
│   ├── data_pipeline.md               # Data ingestion & representation
│   ├── stage1_user_profile.md         # Stage 1: User Profile Model
│   ├── stage2_skill_gap.md            # Stage 2: Skill Gap Model
│   ├── stage3_course_recommendation.md# Stage 3: Course Recommendation
│   ├── rag_explanation_engine.md      # RAG & Explanation Generation
│   ├── evaluation.md                  # Evaluation metrics & IRS mapping
│   └── tech_stack.md                  # Technology stack & dependencies
├── app/                               # 🖥️ Streamlit frontend
│   ├── app.py                         # Main orchestrator
│   ├── config.py                      # App configuration & constants
│   ├── state.py                       # Session state management
│   ├── llm.py                         # LLM interaction & prompts
│   ├── cv_parser.py                   # CV text extraction & analysis
│   ├── ui_components.py               # Reusable UI components
│   └── styles.css                     # Custom CSS styling
├── knowledgegraph/                    # 🔗 Knowledge Graph module
│   └── knowledgegraph.py              # Neo4j graph operations
├── skillgap/                          # 🎯 Skill Gap Analysis module
│   └── skillgap.py                    # Gap detection & prioritisation
├── recommender/                       # 📋 Course Recommendation module
│   └── recommender.py                 # CSP, CBR, Fuzzy, Neural ranking
├── tests/                             # 🧪 Comprehensive test suite
│   ├── conftest.py                    # Shared test fixtures
│   ├── pytest.ini                     # Test configuration
│   ├── README.md                      # Test documentation
│   ├── unit/                          # Unit tests (76+ tests)
│   │   ├── knowledgegraph/           # Knowledge Graph tests
│   │   ├── skillgap/                 # Skill Gap tests
│   │   ├── recommender/              # Recommender tests
│   │   └── app/                      # Application tests
│   └── integration/                   # Integration tests
├── data/                             # 📊 Local data files for testing
│   ├── user_profiles.csv           # Sample user profiles
│   ├── knowledge_graph.csv         # Sample skill-role mappings
│   └── skillsfuture_courses.csv    # Sample course catalog
├── requirements.txt                   # Python dependencies
├── app.yaml                           # Deployment configuration
├── run_tests.sh                       # Test runner script (Bash)
├── run_tests.ps1                      # Test runner script (PowerShell)
└── skills-template.json               # Skill entity schema
```

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Infrastructure** | Databricks, Neo4j, OpenAI GPT-4 Mini, GitHub |
| **NLP** | spaCy, Sentence-BERT, HuggingFace Transformers |
| **Reasoning** | LangChain, Google OR-Tools, PyTorch |
| **Data** | Scrapy, BeautifulSoup, PyPDF2 |
| **Frontend** | Streamlit |
| **Testing** | pytest, pytest-cov, pytest-mock |

## Getting Started

```bash
# Clone the repository
git clone https://github.com/your-org/skillup.git
cd skillup

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (copy and edit .env.example)
cp .env.example .env
# Edit .env with your API keys and credentials

# For local development (limited functionality):
# - Neo4j connection will use environment variables
# - Databricks-dependent features will use CSV fallbacks in data/ directory
# - Full functionality requires Databricks environment

# Run the application
streamlit run app/app.py
```

## Testing

SkillUP includes a comprehensive test suite with 75%+ coverage:

```bash
# Run all unit tests
cd skillup
uv run pytest tests/ -m unit

# Run with coverage report
uv run pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html

# Run smoke tests (quick critical checks)
uv run pytest tests/ -m smoke

# Use the test runner script
./run_tests.sh smoke      # Quick smoke tests
./run_tests.sh unit       # All unit tests
./run_tests.sh coverage   # With coverage report

# On Windows PowerShell:
# .\run_tests.ps1 smoke      # Quick smoke tests
# .\run_tests.ps1 unit       # All unit tests
# .\run_tests.ps1 coverage   # With coverage report
```

**Test Statistics:**
* 76+ comprehensive tests covering all modules
* Unit tests for: Knowledge Graph, Skill Gap, Recommender, App
* Integration tests for end-to-end pipeline
* Mock fixtures for Neo4j, Databricks, OpenAI
* CI/CD ready with coverage reporting

For detailed test documentation, see [tests/README.md](tests/README.md).

## Local Development

SkillUP is designed for deployment on **Databricks**, but supports limited local development:

### ✅ What Works Locally
- Streamlit web interface
- CV parsing and analysis
- Basic skill gap analysis (with CSV fallbacks)
- Course recommendation engine
- Unit and integration tests

### ⚠️ Limitations in Local Mode
- **No Databricks Features**: Delta tables, MLflow, PySpark operations
- **Limited Data**: Uses sample CSV files instead of full datasets
- **No Real-time Data**: Cannot access live job market or course data
- **Reduced Performance**: Local embeddings vs distributed processing

### 🔧 Local Setup Requirements
- Python 3.8+
- Neo4j database (for knowledge graph features)
- OpenAI API key
- Sample data files in `data/` directory

For full functionality, deploy to Databricks environment.

## Next Steps

1. ✅ Implement the three reasoning models
2. ✅ End-to-end pipeline integration
3. ✅ UAT with mid-career switcher profiles
4. ✅ Demo video and final report delivery

## License

This project is developed as part of the NUS-ISS Intelligent Reasoning Systems practice module (AIS08 PT).
