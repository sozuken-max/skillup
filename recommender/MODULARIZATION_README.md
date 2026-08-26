# Course Recommender - Modular Architecture

## Overview

The Course Recommender has been refactored from a single 2373-line monolithic file into a modular package with **17 focused modules** + package initialization.

## Latest Modularization (Phase 2)

The main `recommender.py` was further modularized from 640 lines to 295 lines by extracting:

* **mlflow_tracking.py** (233 lines) - MLflow experiment tracking and metrics logging
* **pipeline.py** (197 lines) - End-to-end pipeline orchestration functions  
* **output.py** (75 lines) - Console output formatting and display utilities

## Complete Module Structure

### Core Data & Configuration
* **models.py** (265 lines) - All data structures and schemas
  * Enums: `Modality`, `Schedule`
  * Dataclasses: `UserProfile`, `SkillGap`, `Course`, `FuzzyScores`, `ScoreBreakdown`, `RecommendedCourse`, `LearningPath`, `HistoricalCase`

* **config.py** (30 lines) - Configuration management
  * `RecommenderConfig` - All weights, thresholds, and settings

### Validation & Utilities
* **validation.py** (99 lines) - Input validation
  * `validate_user_profile()`, `validate_skill_gaps()`, `validate_courses()`

* **utils.py** (47 lines) - Reusable utility functions
  * Similarity: `jaccard_similarity()`, `cosine_similarity()`, `semantic_similarity()`
  * Scoring: `normalize_score()`

### Recommendation Algorithms
* **csp.py** (128 lines) - Constraint Satisfaction Problem solver
  * `ConstraintSolver` class - Budget, time, modality filtering

* **cbr.py** (118 lines) - Case-Based Reasoning system
  * `CaseLibrary` class - Historical case matching and retrieval

* **fuzzy.py** (117 lines) - Fuzzy logic scoring
  * `FuzzyScorer` class - Degree-of-satisfaction calculations

* **scoring.py** (65 lines) - Score fusion and ranking
  * `ScoreFusion` class - Multi-technique score combination

* **sequencing.py** (59 lines) - Course sequencing and timeline
  * `CourseSequencer` class - Intelligent ordering by difficulty

### Evaluation & Metrics
* **evaluation.py** (127 lines) - Evaluation metrics
  * `calculate_skill_gap_coverage()`, `calculate_weighted_skill_coverage()`
  * `calculate_recommendation_diversity()`, `calculate_cost_efficiency()`

### Integration & I/O
* **integration.py** (475 lines) - Stage 2 integration
  * JSON parsing: `parse_stage2_json()`, `parse_stage2_multi_role_json()`
  * Data loading: `load_stage2_from_json_file()`, `load_stage2_from_delta()`, etc.

* **serialization.py** (127 lines) - Output serialization
  * `serialize_learning_path_to_json()`, `save_learning_path_to_json()`, `save_learning_path_to_delta()`

* **data_loading.py** (93 lines) - Data loading utilities
  * `_load_course_from_row()` - Delta table row conversion

### Orchestration & Tracking
* **pipeline.py** (197 lines) - End-to-end pipeline orchestration
  * `run_recommendation_pipeline()` - Single-role Stage 2 → Stage 3 workflow
  * `run_multi_role_recommendation_pipeline()` - Multi-role workflow with Delta integration

* **mlflow_tracking.py** (233 lines) - MLflow experiment tracking
  * `MLflowTracker` class - Parameter, metric, and tag logging
  * Automatic failure handling and comprehensive metric collection

* **output.py** (75 lines) - Output formatting utilities
  * `print_learning_path_summary()` - Pretty-print learning paths to console

### Main Orchestrator
* **recommender.py** (295 lines) - Main recommendation engine
  * `CourseRecommender` class - Orchestrates all components
  * Core recommendation implementation (`_recommend_impl`)
  * CBR insight generation

### Package Interface
* **__init__.py** (~110 lines) - Clean package exports
  * Exposes all public APIs for easy importing

## Usage

### Before (Monolithic)
```python
from recommender import (
    CourseRecommender,
    UserProfile,
    parse_stage2_json,
    # ... everything in one file
)
```

### After (Modular)
```python
# Same clean interface
from recommender import (
    CourseRecommender,
    UserProfile,
    parse_stage2_json,
    run_recommendation_pipeline,
    print_learning_path_summary,
    # ... but now organized into focused modules
)

# Or import specific modules
from recommender.models import UserProfile, Course
from recommender.csp import ConstraintSolver
from recommender.cbr import CaseLibrary
from recommender.mlflow_tracking import MLflowTracker
from recommender.pipeline import run_recommendation_pipeline
from recommender.output import print_learning_path_summary
```

## Benefits

1. **Maintainability**: Each module has a single, clear responsibility
2. **Testability**: Modules can be tested in isolation
3. **Readability**: ~30-500 lines per file vs. 2373 lines monolith
4. **Reusability**: Components can be imported and used independently
5. **Collaboration**: Multiple developers can work on different modules
6. **Documentation**: Easier to document and understand each component
7. **Separation of Concerns**: MLflow tracking, pipeline orchestration, and output formatting are cleanly separated

## File Sizes (Updated)

| Module | Lines | Purpose |
|--------|-------|---------|
| models.py | 265 | Data structures |
| config.py | 30 | Configuration |
| validation.py | 99 | Input validation |
| utils.py | 47 | Utilities |
| csp.py | 128 | Constraint solver |
| cbr.py | 118 | Case-based reasoning |
| fuzzy.py | 117 | Fuzzy logic |
| scoring.py | 65 | Score fusion |
| sequencing.py | 59 | Course sequencing |
| evaluation.py | 127 | Metrics |
| integration.py | 475 | Stage 2 integration |
| serialization.py | 127 | Output serialization |
| data_loading.py | 93 | Data loading |
| **mlflow_tracking.py** | **233** | **MLflow tracking** |
| **pipeline.py** | **197** | **Pipeline orchestration** |
| **output.py** | **75** | **Output formatting** |
| **recommender.py** | **295** | **Main orchestrator** |
| __init__.py | ~110 | Package exports |
| **Total** | **~2660** | **(organized)** |

## Architecture Diagram

```
recommender/
├── __init__.py                # Package interface
├── models.py                  # Core data structures
├── config.py                  # Configuration
│
├── validation.py              # Input validation
├── utils.py                   # Utilities
│
├── csp.py                     # Constraint solver
├── cbr.py                     # Case-based reasoning
├── fuzzy.py                   # Fuzzy logic
├── scoring.py                 # Score fusion
├── sequencing.py              # Course sequencing
│
├── evaluation.py              # Metrics
├── integration.py             # Stage 2 integration
├── serialization.py           # Output serialization
├── data_loading.py            # Data loading
│
├── mlflow_tracking.py         # MLflow experiment tracking ✨ NEW
├── pipeline.py                # End-to-end orchestration ✨ NEW
├── output.py                  # Display utilities ✨ NEW
│
└── recommender.py             # Main orchestrator (streamlined)
```

## Migration Guide

All existing code using `recommender.py` will continue to work unchanged because:
* The package `__init__.py` exports all public APIs
* Import paths remain the same
* Function signatures are unchanged
* Original file preserved as `recommender_original.py` for reference

## Testing

Run the test suite to verify modularization:

```bash
cd skillup
python -m pytest tests/unit/recommender/test_recommender.py -v
```

Run the integration demo:

```bash
cd skillup/recommender
python demo_integration.py
```

## Modularization History

* **Phase 1** (Initial): 2373-line monolith → 14 modules (recommender.py: 640 lines)
* **Phase 2** (Latest): Further split → 17 modules (recommender.py: 295 lines)
  * Extracted MLflow tracking → `mlflow_tracking.py`
  * Extracted pipeline orchestration → `pipeline.py`
  * Extracted output utilities → `output.py`

Total reduction: **2373 lines → 295 lines** in main orchestrator (87.5% reduction)
