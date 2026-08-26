# Course Dataclass Usage Guide

## Overview

The `Course` dataclass matches the Delta table schema from `workspace.default.my_skills_future_course_directory`. This guide clarifies the correct way to create Course objects.

## ⚠️ Important: Constructor Fields vs Computed Properties

The Course dataclass has **actual fields** (constructor parameters) and **computed properties** (calculated values).

### ❌ Common Mistakes

```python
# WRONG - These are computed properties, NOT constructor parameters!
course = Course(
    course_id="TEST-001",
    title="Deep Learning",
    provider="NUS",
    duration_weeks=12,          # ❌ WRONG - This is a property!
    subsidy_rate=0.7,           # ❌ WRONG - This is a property!
    skills_covered=["skill1"],  # ❌ WRONG - Should be string, not list!
    prerequisites=[]            # ❌ WRONG - Should be string, not list!
)
```

### ✅ Correct Usage

```python
from recommender import Course

# Correct way to create a Course
course = Course(
    # Required fields
    course_id="SF-DL-001",
    title="Deep Learning Fundamentals",
    provider="National University of Singapore",
    
    # Cost fields (actual values, not rates)
    cost=2500.0,                    # ✅ Full cost before subsidy
    cost_after_subsidy=750.0,       # ✅ Cost after subsidy (NOT subsidy_rate!)
    
    # Duration (in hours, not weeks)
    total_hours=120.0,              # ✅ Total hours (duration_weeks is computed)
    
    # Skills and prerequisites (strings, not lists)
    skills_covered="Deep learning, TensorFlow, Neural networks, Keras",  # ✅ String
    prerequisites="Basic Python, Linear algebra, Statistics",            # ✅ String or None
    
    # Ratings and popularity
    rating=4.8,
    rating_respondents=150,
    enrollment_count=1250,
    
    # Optional: Modality and schedule (strings or None)
    modality="Online",
    schedule="Evening",
    training_commitment="Part-time"
)
```

## Field Reference

### Required Fields
* `course_id: str` - Primary identifier (coursereferencenumber)
* `title: str` - Course title (coursetitle)
* `provider: str` - Training provider name (trainingprovideralias)

### Cost Fields (Actual Values)
* `cost: float` - Full course fee before subsidies (full_course_fee)
* `cost_after_subsidy: float` - Course fee after subsidies (course_fee_after_subsidies)
* **NOT** `subsidy_rate` - This is a computed property!

### Duration Fields
* `total_hours: float` - Number of course hours (number_of_hours)
* `training_commitment: str | None` - "Full-time", "Part-time", etc.
* **NOT** `duration_weeks` - This is a computed property!

### Content Fields (Unstructured Text)
* `skills_covered: str | None` - Comma-separated skills description (what_you_learn)
* `prerequisites: str | None` - Prerequisites description (minimum_entry_requirement)
* `description: str | None` - Course description (about_this_course)

### Rating Fields
* `rating: float` - Course rating 0.0-5.0 (courseratings_stars)
* `rating_value: float | None` - Rating value (courseratings_value)
* `rating_respondents: int` - Number of respondents (courseratings_noofrespondents)

### Other Fields
* `enrollment_count: int` - Number of attendees (attendancecount)
* `modality: str | None` - "Online", "In-person", etc.
* `schedule: str | None` - "Evening", "Weekend", etc.
* `provider_uen: str | None` - Provider UEN (trainingprovideruen)
* `conducted_in: str | None` - Location/format (conducted_in)

## Computed Properties

These are **read-only** and calculated automatically:

```python
course = Course(
    course_id="TEST-001",
    title="Deep Learning",
    provider="NUS",
    cost=2500.0,
    cost_after_subsidy=750.0,
    total_hours=120.0,
    # ...other fields...
)

# Access computed properties (read-only)
print(course.subsidy_rate)      # Computed: (2500 - 750) / 2500 = 0.70
print(course.duration_weeks)    # Computed: ceil(120 / 10) = 12 weeks
print(course.hours_per_week)    # Estimated from training_commitment
```

### Available Computed Properties

1. **`subsidy_rate`** - Calculated as `(cost - cost_after_subsidy) / cost`
2. **`duration_weeks`** - Calculated as `ceil(total_hours / 10.0)` (assumes 10 hrs/week)
3. **`hours_per_week`** - Estimated from `training_commitment` field

## Complete Working Example

```python
from recommender import (
    Course, UserProfile, SkillGap,
    Modality, Schedule,
    CourseRecommender
)

# Create a course with correct fields
course = Course(
    # Primary identifiers
    course_id="SF-DL-101",
    title="Introduction to Deep Learning",
    provider="National University of Singapore",
    provider_uen="200604346E",
    
    # Cost information
    cost=2800.0,                      # Full fee
    cost_after_subsidy=840.0,         # After 70% subsidy
    
    # Duration and commitment
    total_hours=144.0,                # 144 hours total
    training_commitment="Part-time",   # Part-time course
    
    # Content descriptions (unstructured text)
    description="Comprehensive introduction to deep learning...",
    skills_covered="Deep learning, TensorFlow, PyTorch, CNNs, RNNs, Neural networks",
    prerequisites="Python programming, Basic linear algebra, Statistics fundamentals",
    
    # Ratings
    rating=4.7,
    rating_value=4.68,
    rating_respondents=234,
    career_impact_stars=4.5,
    
    # Popularity
    enrollment_count=1850,
    
    # Format
    modality="Online",
    schedule="Evening",
    conducted_in="Online via Zoom",
    skillsfuture_eligible=True
)

# Access computed properties
print(f"Duration: {course.duration_weeks} weeks")     # 15 weeks (ceil(144/10))
print(f"Subsidy rate: {course.subsidy_rate:.1%}")     # 70.0%
print(f"Hours/week: {course.hours_per_week}")         # Estimated from commitment

# Use in recommender
user = UserProfile(
    user_id="user_001",
    current_role="Developer",
    target_role="ML Engineer",
    current_skills=["Python"],
    budget=5000.0,
    available_hours_per_week=10.0,
    preferred_modality=Modality.ONLINE,
    preferred_schedule=Schedule.EVENING,
    skillsfuture_eligible=True
)

skill_gap = SkillGap(
    skill="deep learning",
    priority=0.9,
    current_level=0.2,
    target_level=0.8,
    gap_size=0.6
)

recommender = CourseRecommender()
learning_path = recommender.recommend(user, [skill_gap], [course])
```

## Loading from Delta Table

When loading courses from the Delta table, use `_load_course_from_row()`:

```python
from pyspark.sql import SparkSession
from recommender.data_loading import _load_course_from_row

spark = SparkSession.builder.getOrCreate()
df = spark.table("workspace.default.my_skills_future_course_directory")

# Automatically handles field mapping
courses = [_load_course_from_row(row) for row in df.collect()]
```

## Summary

✅ **DO:**
* Use `cost` and `cost_after_subsidy` (actual values)
* Use `total_hours` (duration in hours)
* Use strings for `skills_covered` and `prerequisites`
* Access `subsidy_rate` and `duration_weeks` as read-only properties

❌ **DON'T:**
* Pass `subsidy_rate` or `duration_weeks` to constructor
* Use lists for `skills_covered` or `prerequisites`
* Try to set computed properties (they're read-only)

---

For more information, see:
* [models.py](models.py) - Full Course dataclass definition
* [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Integration examples
* [data_loading.py](data_loading.py) - Delta table loading
