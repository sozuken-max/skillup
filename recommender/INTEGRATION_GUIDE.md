# Stage 2 → Stage 3 Integration Guide

## Overview

This guide explains how to integrate the **Stage 2 skill gap analysis** (skillgap.py) with the **Stage 3 course recommender** (recommender.py) in the SkillUp system.

## Architecture

```
┌─────────────┐     JSON      ┌──────────────┐      JSON      ┌──────────────┐
│  Stage 1    │  ────────→    │   Stage 2    │  ────────→     │   Stage 3    │
│ (Profile)   │               │ (Skill Gaps) │                │ (Recommender)│
└─────────────┘               └──────────────┘                └──────────────┘
```

* **Stage 1**: User profile collection (current skills, budget, preferences)
* **Stage 2**: Skill gap analysis (identifies gaps, prioritizes skills)
* **Stage 3**: Course recommendation (finds optimal learning path)

## Integration Functions

### 1. Parsing Stage 2 Output

```python
from recommender import parse_stage2_json

# Parse Stage 2 JSON output
target_role, skill_gaps, candidate_course_ids = parse_stage2_json(stage2_output)
```

**Input**: Stage 2 JSON dictionary (from skillgap.py)
**Output**: 
* `target_role` (str): Target job role
* `skill_gaps` (List[SkillGap]): Parsed skill gaps with priorities
* `candidate_course_ids` (List[str]): IDs of candidate courses

### 2. Loading from JSON File

```python
from recommender import load_stage2_from_json_file

# Load Stage 2 output from file
target_role, skill_gaps, candidate_course_ids = load_stage2_from_json_file(
    "stage2_output.json"
)
```

### 3. Loading from Delta Table

```python
from recommender import load_stage2_from_delta

# Load Stage 2 output from Delta table
target_role, skill_gaps, candidate_course_ids = load_stage2_from_delta(
    user_id="user_12345",
    target_role="Machine Learning Engineer",
    table_name="skillsup.gap_analysis.user_analysis_log"
)
```

### 4. End-to-End Pipeline (Recommended)

```python
from recommender import run_recommendation_pipeline

# Complete pipeline: Stage 2 → Stage 3
learning_path = run_recommendation_pipeline(
    user_profile=user_profile,              # From Stage 1
    stage2_json_path="stage2_output.json",  # From Stage 2
    course_catalog=courses,                  # Your course catalog
    output_json_path="recommendations.json"  # Optional: save output
)
```

## Stage 2 JSON Schema

Expected input format from skillgap.py:

```json
{
  "skill_gaps": {
    "target_role": "Machine Learning Engineer",
    "total_gaps": 3,
    "gaps": [
      {
        "skill": "deep learning",
        "category": "Technical",
        "gap_weight": 0.75,
        "user_skill_proficiency": 0.25,
        "demand_score": 0.85,
        "peer_score": 0.88,
        "graph_distance": 2,
        "priority": "critical",
        "rationale": "Required in 85% of postings"
      }
    ],
    "candidate_courses": [
      {
        "course_id": "SF-DL-001",
        "covers_skills": ["deep learning"],
        "pre_constraint": true
      }
    ]
  }
}
```

**Priority Values**: `"critical"`, `"high"`, `"medium"`, `"low"`, `"user-request"`

## Stage 3 JSON Output Schema

Output format from recommender.py:

```json
{
  "user_id": "user_12345",
  "generated_at": "2026-04-11T11:14:41.108362",
  "summary": {
    "total_courses": 2,
    "total_duration_weeks": 20,
    "total_cost_sgd": 4300.0,
    "total_cost_after_subsidy_sgd": 1290.0,
    "total_savings_sgd": 3010.0,
    "subsidy_rate": 0.70
  },
  "cbr_insight": "...",
  "trade_offs": [],
  "recommended_courses": [
    {
      "rank": 1,
      "sequence_position": "Month 1-3",
      "course": {
        "course_id": "SF-DL-001",
        "title": "Deep Learning Fundamentals",
        "provider": "National University of Singapore",
        "duration_weeks": 12,
        "cost_before_subsidy": 2500.0,
        "cost_after_subsidy": 750.0,
        "skills_covered": ["deep learning", "tensorflow"]
      },
      "scores": {
        "final_score": 0.742,
        "score_breakdown": {...},
        "fuzzy_logic_scores": {...}
      },
      "warnings": []
    }
  ]
}
```

## Complete Example

```python
from recommender import (
    UserProfile, Course, Modality, Schedule,
    CourseRecommender, parse_stage2_json
)

# 1. Load Stage 2 output
stage2_output = {
    "skill_gaps": {
        "target_role": "ML Engineer",
        "gaps": [
            {
                "skill": "deep learning",
                "gap_weight": 0.75,
                "user_skill_proficiency": 0.25,
                "priority": "critical"
            }
        ],
        "candidate_courses": [
            {"course_id": "SF-DL-001", "covers_skills": ["deep learning"]}
        ]
    }
}

# 2. Parse Stage 2
target_role, skill_gaps, _ = parse_stage2_json(stage2_output)

# 3. Create user profile (from Stage 1)
user = UserProfile(
    user_id="user_001",
    current_role="Developer",
    target_role=target_role,
    current_skills=["Python"],
    budget=5000.0,
    available_hours_per_week=10.0,
    preferred_modality=Modality.ONLINE,
    preferred_schedule=Schedule.EVENING,
    skillsfuture_eligible=True
)

# 4. Define course catalog
courses = [
    Course(
        course_id="SF-DL-001",
        title="Deep Learning",
        provider="NUS",
        duration_weeks=12,
        cost=2500.0,
        subsidy_rate=0.7,
        modality=Modality.ONLINE,
        schedule=Schedule.EVENING,
        skills_covered=["deep learning"],
        prerequisites=[],
        rating=4.8,
        enrollment_count=1250
    )
]

# 5. Generate recommendations
recommender = CourseRecommender()
learning_path = recommender.recommend(user, skill_gaps, courses)

# 6. Display results
print(f"Recommended {learning_path.total_courses} courses")
print(f"Total cost: ${learning_path.total_cost_after_subsidy:.2f}")
for rec in learning_path.courses:
    print(f"  {rec.rank}. {rec.course.title} (score: {rec.final_score:.3f})")
```

## Modular Architecture

The recommender has been fully modularized into focused components:

### Core Components
* **recommender.py** (295 lines) - Main orchestrator
* **models.py** (265 lines) - Data structures
* **config.py** (30 lines) - Configuration

### Recommendation Algorithms
* **csp.py** (128 lines) - Constraint solver
* **cbr.py** (118 lines) - Case-based reasoning
* **fuzzy.py** (117 lines) - Fuzzy logic
* **scoring.py** (65 lines) - Score fusion
* **sequencing.py** (59 lines) - Course sequencing

### Integration & I/O
* **integration.py** (475 lines) - Stage 2 integration
* **pipeline.py** (197 lines) - End-to-end orchestration
* **serialization.py** (127 lines) - Output serialization
* **output.py** (75 lines) - Console display

### MLflow & Tracking
* **mlflow_tracking.py** (233 lines) - Experiment tracking

### Utilities
* **validation.py** (99 lines) - Input validation
* **evaluation.py** (127 lines) - Metrics
* **data_loading.py** (93 lines) - Data loading
* **utils.py** (47 lines) - Helper functions

See [MODULARIZATION_README.md](MODULARIZATION_README.md) for detailed architecture documentation.

## File Locations

* **Recommender**: `skillup/recommender/recommender.py` (295 lines, streamlined)
* **Pipeline Orchestration**: `skillup/recommender/pipeline.py` (197 lines)
* **Integration Demo**: `skillup/recommender/demo_integration.py`
* **Tests**: `skillup/tests/unit/recommender/test_recommender.py` (35 tests, all passing)
* **Stage 2**: `skillup/skillgap/skillgap.py`

## Testing

Run the integration tests:

```bash
cd skillup
python -m pytest tests/unit/recommender/test_recommender.py -v
```

Run the integration demo:

```bash
cd skillup/recommender
python demo_integration.py
```

## Key Features

* ✅ **Automatic Priority Mapping**: Converts text priorities ("critical", "high", etc.) to numeric values
* ✅ **Flexible Input**: Supports JSON files, Delta tables, or direct dictionaries
* ✅ **Structured Output**: Generates standardized JSON for downstream systems
* ✅ **Cost Optimization**: Applies SkillsFuture subsidies and optimizes budget allocation
* ✅ **Timeline Generation**: Creates sequenced learning paths with realistic timelines
* ✅ **Constraint Satisfaction**: Ensures recommendations respect budget, time, and modality constraints
* ✅ **Modular Architecture**: 17 focused modules for maintainability and testability
* ✅ **MLflow Integration**: Optional experiment tracking and metrics logging

## Next Steps

1. **Production Deployment**: Connect to actual Stage 2 Delta tables
2. **Delta Lake Integration**: Use `save_learning_path_to_delta()` to persist recommendations
3. **Real-time Updates**: Set up streaming pipelines for continuous recommendations
4. **A/B Testing**: Compare recommendation strategies using historical case data

---

For questions or issues, refer to:
* Stage 3 Architecture: `docs/stage3_course_recommendation.md`
* Modularization Details: `MODULARIZATION_README.md`
* Test Documentation: `../tests/README.md`
* Demo Script: `demo_integration.py`
