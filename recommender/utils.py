"""
Stage 3 Course Recommendation System - Utilities
=================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import Set, List, Dict
import math

# ---------------------------------------------------------------------------
# Skill synonym map
# Canonical skill name (lowercase) → list of equivalent terms (lowercase).
# Used by CSP and fuzzy scoring to avoid silent misses on terminology variants.
# ---------------------------------------------------------------------------
SKILL_SYNONYMS: Dict[str, List[str]] = {
    # AI / Machine Learning
    "machine learning": ["ml", "statistical learning", "predictive modelling", "predictive modeling"],
    "deep learning": ["neural networks", "deep neural networks", "dnn", "ann", "artificial neural network"],
    "natural language processing": ["nlp", "text analytics", "text mining", "text analysis", "language ai"],
    "computer vision": ["cv", "image recognition", "image processing", "image classification", "object detection"],
    "reinforcement learning": ["rl", "reward learning"],
    "generative ai": ["genai", "large language models", "llm", "llms", "foundation models"],
    "tensorflow": ["tf", "keras", "tensorflow keras"],
    "pytorch": ["torch", "libtorch"],
    # Data Engineering / Science
    "data science": ["data analytics", "data analysis", "applied statistics"],
    "data engineering": ["data pipeline", "etl", "elt", "data infrastructure"],
    "apache spark": ["spark", "pyspark", "spark streaming"],
    "hadoop": ["hdfs", "mapreduce", "hive", "big data"],
    "sql": ["structured query language", "database querying", "rdbms", "relational database"],
    "python": ["python programming", "python scripting", "python development"],
    "r programming": ["r language", "rstudio"],
    "tableau": ["data visualisation", "data visualization", "dashboarding", "bi tools"],
    "power bi": ["powerbi", "business intelligence", "microsoft bi"],
    # Cloud / DevOps / MLOps
    "cloud computing": ["aws", "azure", "gcp", "google cloud", "amazon web services", "microsoft azure", "cloud services"],
    "kubernetes": ["k8s", "container orchestration"],
    "docker": ["containerisation", "containerization", "containers"],
    "devops": ["ci/cd", "continuous integration", "continuous deployment", "devsecops"],
    "mlops": ["ml operations", "model deployment", "model serving", "model monitoring"],
    # Cybersecurity
    "cybersecurity": ["information security", "infosec", "network security", "cyber security", "it security"],
    # Business / Management
    "agile": ["scrum", "kanban", "sprint planning", "agile methodology"],
    "project management": ["pm", "pmp", "project coordination", "programme management"],
    "ux design": ["user experience", "ui/ux", "user interface design", "human-computer interaction", "hci", "ux research"],
    "digital marketing": ["seo", "sem", "social media marketing", "content marketing", "performance marketing"],
    # Finance
    "financial analysis": ["financial modelling", "financial modeling", "valuation", "corporate finance"],
    "accounting": ["bookkeeping", "financial reporting", "ifrs", "gaap"],
    "fintech": ["financial technology", "digital banking", "payments"],
}


def expand_skill_with_synonyms(skill: str) -> List[str]:
    """
    Return the given skill string plus all known synonym variants, lowercased.

    Performs both forward lookup (skill is a canonical key) and reverse lookup
    (skill appears as a value in another skill's synonym list).

    Args:
        skill: Skill name to expand (case-insensitive)

    Returns:
        Deduplicated list of the skill and all related terms
    """
    skill_lower = skill.lower().strip()
    variants = [skill_lower]

    # Forward match: skill is a canonical key
    if skill_lower in SKILL_SYNONYMS:
        variants.extend(SKILL_SYNONYMS[skill_lower])

    # Reverse match: skill appears as a synonym value
    for canonical, synonyms in SKILL_SYNONYMS.items():
        if skill_lower in synonyms:
            variants.append(canonical)
            variants.extend(synonyms)
            break  # Each synonym should only appear in one group

    # Deduplicate preserving order
    seen: Set[str] = set()
    unique: List[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)

    return unique


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Calculate Jaccard similarity between two sets"""
    if not set1 and not set2:
        return 1.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have same length")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def semantic_similarity(text1: str, text2: str) -> float:
    """
    Calculate semantic similarity between two text strings.

    TODO: Replace with actual embedding-based similarity using:
    - Databricks Foundation Model API
    - Sentence transformers
    - Or other semantic encoding method

    For MVP, using simple word overlap as placeholder.
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    return jaccard_similarity(words1, words2)


def normalize_score(value: float, min_val: float, max_val: float) -> float:
    """Normalize a value to 0-1 range"""
    if max_val == min_val:
        return 1.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
