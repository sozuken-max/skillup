# SkillUP Evaluation Setup & Notebook Organization

**Last Updated:** 2026-04-18  
**Status:** ✅ Migrated to Volumes-based artifact storage

---

## 📁 Repository Structure

```
/Workspace/Users/yzouyang-iss@u.nus.edu/skillup/
├── notebooks/                          # All evaluation notebooks (consolidated)
│   ├── Technique_Validation.ipynb     # IRS technique validation (8 methods)
│   ├── Test_Runner.ipynb              # Comprehensive test suite
│   ├── Quick_Smoke_Tests.ipynb        # Fast health checks (<30s)
│   └── Coverage_Analysis.ipynb        # Detailed coverage reporting
├── data/                               # Version-controlled test data
│   ├── skill_mappings_gold.json
│   ├── gold_standard_cvs.json
│   ├── gold_standard_jds.json
│   └── test_profiles.json
├── tests/                              # Pytest test modules
├── knowledgegraph/                     # KG module
├── skillgap/                           # Skill Gap module
├── recommender/                        # Recommender module
├── app/                                # Application module
└── EVALUATION_SETUP.md                 # This file
```

## 🗄️ Artifact Storage (Volumes)

**All evaluation artifacts (logs, results, reports) are now stored in Databricks Volumes:**

```
/Volumes/workspace/default/iss-scratchpad/evaluation/
├── validation_YYYYMMDD.log            # Technique validation logs
├── baseline_YYYYMMDD.json             # Technique validation results
├── coverage_YYYYMMDD.json             # Coverage trends (if saved)
├── htmlcov/                            # HTML coverage reports (optional)
└── test_runs/                          # Test execution logs (optional)
```

**Why Volumes?**
- ✅ Shared across team members
- ✅ Persists beyond notebook lifecycle
- ✅ Accessible from all compute contexts
- ✅ Supports large artifacts (HTML reports, XML coverage)
- ✅ Git repo stays clean (no large binary artifacts)

---

## 📓 Notebook Details

### 1. Technique_Validation.ipynb

**Location:** `/Workspace/Users/yzouyang-iss@u.nus.edu/skillup/notebooks/Technique_Validation.ipynb`  
**Notebook ID:** 1353956204946915  
**Purpose:** Validate 8 IRS techniques against gold standard data

**Techniques Tested:**
1. Semantic Similarity (cosine similarity on embeddings)
2. Knowledge Graph Queries (Neo4j Cypher)
3. Named Entity Recognition (spaCy NER)
4. Constraint Satisfaction Programming (python-constraint)
5. Case-Based Reasoning (skill pattern matching)
6. Fuzzy Logic (fuzzy rule-based matching)
7. Competing Experts (ensemble voting)
8. Retrieval-Augmented Generation (RAG with LLM)

**Key Cells:**
- Cell 3: Configuration (updated to use `/Volumes/.../evaluation/`)
- Cell 5-21: Individual technique implementations
- Cell 23: JSON results export to Volumes

**Outputs:**
- `validation_YYYYMMDD.log` → logs to `/Volumes/workspace/default/iss-scratchpad/evaluation/`
- `baseline_YYYYMMDD.json` → saves to `/Volumes/workspace/default/iss-scratchpad/evaluation/`

**Migration Status:** ✅ Updated (Cell 3 now uses Volumes path)

---

### 2. Test_Runner.ipynb

**Location:** `/Workspace/Users/yzouyang-iss@u.nus.edu/skillup/notebooks/Test_Runner.ipynb`  
**Notebook ID:** 984473343373211  
**Purpose:** Comprehensive pytest test suite with organized sections

**Test Categories:**
- All unit tests
- Module-specific tests (KG, Skill Gap, Recommender, App)
- Smoke tests (fast validation)
- Integration tests
- Coverage report generation
- Custom test patterns

**Usage:**
```python
# Run all tests
!python -m pytest tests/ -v

# Run module-specific
!python -m pytest tests/test_knowledgegraph.py -v

# Run with coverage
!python -m pytest tests/ --cov=. --cov-report=term-missing
```

**Migration Status:** ✅ Ready (no path dependencies)

---

### 3. Quick_Smoke_Tests.ipynb

**Location:** `/Workspace/Users/yzouyang-iss@u.nus.edu/skillup/notebooks/Quick_Smoke_Tests.ipynb`  
**Notebook ID:** 984473343373212  
**Purpose:** Fast (<30s) system health validation

**Tests:**
- Module imports
- Neo4j connectivity (mocked if unavailable)
- Skill Gap Analyzer instantiation
- Recommender instantiation
- Data file accessibility
- Databricks table availability

**When to Use:**
- Before committing changes
- After environment setup
- Daily development workflow
- Pre-flight check before full test suite

**Migration Status:** ✅ Ready (no artifact storage)

---

### 4. Coverage_Analysis.ipynb

**Location:** `/Workspace/Users/yzouyang-iss@u.nus.edu/skillup/notebooks/Coverage_Analysis.ipynb`  
**Notebook ID:** 984473343373213  
**Purpose:** Detailed code coverage analysis with trends

**Coverage Targets:**
| Module | Target | Priority |
|--------|--------|---------|
| Knowledge Graph | 80%+ | High |
| Skill Gap | 75%+ | High |
| Recommender | 85%+ | Critical |
| App | 70%+ | Medium |
| **Overall** | **≥80%** | **Required** |

**Outputs:**
- Terminal report (with missing line numbers)
- HTML report (`htmlcov/index.html` in repo)
- XML report (`coverage.xml` in repo)
- Trends tracking (looks in `/Volumes/.../evaluation/` for historical data)

**Migration Status:** ⚠️ Needs update (Cell 17 references old path)

---

## 🔐 Databricks Secrets Configuration

**App-level environment variables are available as Databricks secrets for notebooks.**

### Setup Databricks Secrets

1. **Create Secret Scope** (if not exists):
   ```bash
   databricks secrets create-scope skillup
   ```

2. **Add Secrets** (example for Neo4j):
   ```bash
   databricks secrets put-secret skillup neo4j_uri
   databricks secrets put-secret skillup neo4j_username
   databricks secrets put-secret skillup neo4j_password
   ```

3. **Access in Notebooks**:
   ```python
   # Example: Neo4j credentials
   neo4j_uri = dbutils.secrets.get(scope="skillup", key="neo4j_uri")
   neo4j_user = dbutils.secrets.get(scope="skillup", key="neo4j_username")
   neo4j_pass = dbutils.secrets.get(scope="skillup", key="neo4j_password")
   ```

### Common Secrets Needed

| Secret Key | Purpose | Used By |
|-----------|---------|----------|
| `neo4j_uri` | Neo4j connection URI | KnowledgeGraph |
| `neo4j_username` | Neo4j username | KnowledgeGraph |
| `neo4j_password` | Neo4j password | KnowledgeGraph |
| `openai_api_key` | OpenAI API key (for RAG) | Technique_Validation |
| `databricks_token` | Databricks API token | Integration tests |

### Best Practices

✅ **DO:**
- Use secrets for all credentials
- Document which secrets each notebook needs
- Test with mocked credentials if secrets unavailable
- Use try/except blocks when accessing secrets

❌ **DON'T:**
- Hardcode credentials in notebooks
- Print secret values in output cells
- Commit secrets to git
- Share secret scope names in public docs

---

## 🚀 Migration Checklist

### Phase 1: Path Updates ✅

- [x] Update `Technique_Validation.ipynb` Cell 3 to use `/Volumes/workspace/default/iss-scratchpad/evaluation/`
- [ ] Update `Coverage_Analysis.ipynb` Cell 17 to use Volumes path for trends
- [x] Create this documentation file (`EVALUATION_SETUP.md`)

### Phase 2: Notebook Relocation (Manual)

- [ ] Move `Technique_Validation.ipynb` from `/Users/yzouyang-iss@u.nus.edu/` to `/Users/yzouyang-iss@u.nus.edu/skillup/notebooks/`
- [ ] Verify Test_Runner.ipynb is in correct location
- [ ] Verify Quick_Smoke_Tests.ipynb is in correct location
- [ ] Verify Coverage_Analysis.ipynb is in correct location

**How to Move Notebooks:**
```bash
# Option 1: Using Databricks CLI
databricks workspace mv \
  /Users/yzouyang-iss@u.nus.edu/Technique_Validation \
  /Users/yzouyang-iss@u.nus.edu/skillup/notebooks/Technique_Validation

# Option 2: Using Databricks UI
# 1. Right-click notebook → Export → Download as .ipynb
# 2. Go to skillup/notebooks/ folder
# 3. Import the downloaded .ipynb file
# 4. Delete old notebook after verifying
```

### Phase 3: Databricks Secrets Setup

- [ ] Create `skillup` secret scope
- [ ] Add Neo4j credentials (uri, username, password)
- [ ] Add OpenAI API key (if using RAG validation)
- [ ] Test secret access in Quick_Smoke_Tests notebook
- [ ] Document additional secrets in this file

### Phase 4: Validation

- [ ] Run Quick_Smoke_Tests.ipynb (should complete <30s)
- [ ] Run Test_Runner.ipynb (full test suite)
- [ ] Run Coverage_Analysis.ipynb (verify Volumes path works)
- [ ] Run Technique_Validation.ipynb (verify artifacts save to Volumes)
- [ ] Check `/Volumes/workspace/default/iss-scratchpad/evaluation/` for outputs

### Phase 5: Cross-Reference Updates

- [ ] Update weekly plan references to new notebook locations
- [ ] Update README.md (if exists) with new structure
- [ ] Update CI/CD pipelines to use new paths
- [ ] Update team documentation

---

## 🔄 Weekly Workflow

### Monday Morning Health Check
1. Run Quick_Smoke_Tests (<30s)
2. If pass → proceed with development
3. If fail → fix issues before starting work

### Before Committing Code
1. Run Test_Runner (module-specific tests)
2. Verify no regressions
3. Commit code

### Friday End-of-Week Validation
1. Run Coverage_Analysis (full coverage report)
2. Run Technique_Validation (IRS baseline)
3. Save results to `/Volumes/.../evaluation/baseline_YYYYMMDD.json`
4. Track coverage trends week-over-week

---

## 📊 Accessing Results

### View Evaluation Artifacts

```python
from pathlib import Path
import json

# List all evaluation results
eval_dir = Path("/Volumes/workspace/default/iss-scratchpad/evaluation")
for file in sorted(eval_dir.glob("*.json")):
    print(f"📄 {file.name} ({file.stat().st_size / 1024:.1f} KB)")

# Load latest baseline
latest_baseline = sorted(eval_dir.glob("baseline_*.json"))[-1]
with open(latest_baseline) as f:
    data = json.load(f)
    print(f"\n📊 Latest Baseline: {data['snapshot_date']}")
    print(f"   Techniques Tested: {len(data['techniques'])}")
```

### Compare Baselines Over Time

```python
import pandas as pd

# Load all baselines
baselines = []
for file in sorted(eval_dir.glob("baseline_*.json")):
    with open(file) as f:
        data = json.load(f)
        baselines.append({
            'date': data['snapshot_date'],
            'file': file.name,
            'techniques': len(data['techniques'])
        })

df = pd.DataFrame(baselines)
print(df)
```

---

## 🆘 Troubleshooting

### Issue: "FileNotFoundError: /Volumes/workspace/default/iss-scratchpad/evaluation"

**Solution:**
```python
from pathlib import Path
eval_dir = Path("/Volumes/workspace/default/iss-scratchpad/evaluation")
eval_dir.mkdir(parents=True, exist_ok=True)
print(f"✅ Created {eval_dir}")
```

### Issue: "Secret scope 'skillup' does not exist"

**Solution:**
```bash
databricks secrets create-scope skillup
```

### Issue: "Module 'knowledgegraph' not found"

**Solution:**
```python
import sys
from pathlib import Path
REPO_ROOT = Path("/Workspace/Users/yzouyang-iss@u.nus.edu/skillup")
sys.path.insert(0, str(REPO_ROOT))
print(f"✅ Added {REPO_ROOT} to sys.path")
```

### Issue: "Neo4j connection failed"

**Solution:**
- Check if secrets are configured correctly
- Test with mocked Neo4j (see Quick_Smoke_Tests for example)
- Verify Neo4j instance is running

---

**Questions?** Contact the SkillUP team or check the skillup Git repository for latest updates.