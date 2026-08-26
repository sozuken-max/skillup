# =============================================================================
# skill_gap_model_databricks_aligned.py
# Skill Gap Identification Model — SkillsUP IRS Project AY2025
# 
# STRICTLY ALIGNED VERSION (Incorporates Tweak 1, 2, and 3)
#   - Tweak 1: Partial credit gap weights (1.0 - max_similarity)
#   - Tweak 2: Strict Arbiter Math (0.45 Demand + 0.35 Peer + 0.20 Distance)
#   - Tweak 3: Exact JSON Output Schema (COURSE FILTERING REMOVED - FIX 4)
#   - ENHANCEMENT: Multi-Role Analysis Support
#   - ENHANCEMENT: Multi-User Analysis Support (comma-separated user_id)
#   - ENHANCEMENT: Dual-mode data access (Spark SQL for notebooks, SQL Connector for apps)
#   - FIX 1: Embeddings-based role matching for fuzzy role lookup
#   - FIX 2: Consistent user-declared skills filtering at data layer
#   - FIX 2B: Persist user-declared skills to prevent state cycling
#   - FIX 3: Remove environment check from role similarity search (TEST COMPATIBILITY)
#   - FIX 4: Remove course filtering bottleneck (SEPARATION OF CONCERNS)
#   - FIX 5: Robust skill format normalization (HANDLES DICT/LIST/STRING INPUTS)
#   - FIX 6: Direct input support for Streamlit apps (BYPASS DATABASE LOADING)
#   - FIX 7: Defensive embedding function (HANDLES ANY INPUT TYPE SAFELY)
#   - FIX 8: Top 5 stability fix (EXTRACT FROM ROLE REQUIREMENTS, NOT GAPS)
#   - FIX 9: Deterministic peer data queries (ORDER BY for stable top 5)
#   - FIX 10: Stable sorting with tiebreakers (skill_name secondary sort)
#   - FIX 11: Unique ORDER BY columns (deterministic LIMIT with Name, Age, Graduation_Year)
#   - FIX 12: Role similarity tiebreaker (deterministic role selection)
#   - FIX 13: Deterministic role loading (ORDER BY in DISTINCT query)
#   - FIX 14: Arbitrate gaps tiebreaker (deterministic when scores equal)
#   - FIX 15: Sorted peer logging (deterministic debug output)
#   - FIX 16: User profile query ORDER BY (best practice)
#   - FIX 17: Proficiency-aware skill normalization (PRESERVES PROFICIENCY LEVELS)
#   - FIX 18: Graduated skill filtering (BEGINNER KEPT, ADVANCED REMOVED)
#   - INPUT: Knowledge Graph output from knowledgegraph.py
# =============================================================================


try:
    from datetime import datetime, timezone
except ImportError:
    datetime = None
    timezone = None

# ── IMPORTS ───────────────────────────────────────────────────────────────────
import os
import re
import math
import json
import time
import ast
from collections import Counter

import pandas as pd
import numpy as np

# Global spark session
try:
    spark = globals()['spark']
except KeyError:
    spark = None

# ── STEP 1: DETECT DATABRICKS ENVIRONMENT ────────────────────────────────────
IN_DATABRICKS = False
try:
    if "dbutils" in globals():
        IN_DATABRICKS = True
    else:
        import dbutils # type: ignore
        IN_DATABRICKS = True
except (NameError, ImportError):
    IN_DATABRICKS = False

# ── STEP 2: CONFIGURE WIDGETS (Only in Databricks Notebook) ──────────────────
USER_ID_INPUT = os.getenv("USER_ID", "test_user_1")
USER_IDS = [uid.strip() for uid in USER_ID_INPUT.split(',') if uid.strip()]
ENDPOINT_NAME = os.getenv("ENDPOINT_NAME", "databricks-dbrx-instruct")
CATALOG = os.getenv("CATALOG", "workspace")
JD_TABLE = os.getenv("JD_TABLE", "workspace.default.job_description")
PEER_TABLE = os.getenv("PEER_TABLE", "workspace.default.resume_dataset_1200")
COURSE_TABLE = os.getenv("COURSE_TABLE", "workspace.default.my_skills_future_course_directory")
OUTPUT_SCHEMA = os.getenv("OUTPUT_SCHEMA", "default")
KG_OUTPUT_TABLE = os.getenv("KG_OUTPUT_TABLE", "workspace.default.knowledge_graph_output")
WAREHOUSE_HTTP_PATH = os.getenv("WAREHOUSE_HTTP_PATH", "/sql/1.0/warehouses/10d7685b7261f4d2")
ROLE_SIMILARITY_THRESHOLD = float(os.getenv("ROLE_SIMILARITY_THRESHOLD", "0.70"))
USER_SKILL_FILTER_THRESHOLD = float(os.getenv("USER_SKILL_FILTER_THRESHOLD", "0.85"))

# ── STEP 3: DETERMINE EXECUTION MODE (Notebook vs Streamlit App) ─────────────
USE_SQL_CONNECTOR = False

if IN_DATABRICKS:
    # Check if we're in a notebook context (has widgets)
    try:
        dbutils.widgets.text("user_id",       "test_user_1",             "User ID (comma-separated for multiple)")
        dbutils.widgets.text("endpoint_name", "databricks-dbrx-instruct", "Model Serving endpoint")
        dbutils.widgets.text("catalog",       "workspace",     "Unity Catalog name")
        dbutils.widgets.text("jd_table",      "workspace.default.job_description", "JD Delta table")
        dbutils.widgets.text("peer_table",    "workspace.default.resume_dataset_1200", "Peer Delta table")
        dbutils.widgets.text("course_table",  "workspace.default.my_skills_future_course_directory", "Course Delta table")
        dbutils.widgets.text("output_schema", "default", "Output Delta schema")
        dbutils.widgets.text("kg_output_table", "workspace.default.knowledge_graph_output", "Knowledge Graph output table")
        dbutils.widgets.text("warehouse_http_path", "/sql/1.0/warehouses/10d7685b7261f4d2", "SQL Warehouse HTTP Path")
        dbutils.widgets.text("role_similarity_threshold", "0.70", "Minimum similarity for role matching")
        dbutils.widgets.text("user_skill_filter_threshold", "0.85", "Threshold for user-declared skill filtering")

        USER_ID_INPUT = dbutils.widgets.get("user_id").strip()
        ENDPOINT_NAME = dbutils.widgets.get("endpoint_name").strip()
        CATALOG       = dbutils.widgets.get("catalog").strip()
        JD_TABLE      = dbutils.widgets.get("jd_table").strip()
        PEER_TABLE    = dbutils.widgets.get("peer_table").strip()
        COURSE_TABLE  = dbutils.widgets.get("course_table").strip()
        OUTPUT_SCHEMA = dbutils.widgets.get("output_schema").strip()
        KG_OUTPUT_TABLE = dbutils.widgets.get("kg_output_table").strip()
        WAREHOUSE_HTTP_PATH = dbutils.widgets.get("warehouse_http_path").strip()
        ROLE_SIMILARITY_THRESHOLD = float(dbutils.widgets.get("role_similarity_threshold").strip())
        USER_SKILL_FILTER_THRESHOLD = float(dbutils.widgets.get("user_skill_filter_threshold").strip())

        if not USER_ID_INPUT:
            raise ValueError("❌ user_id widget is empty.")
        
        # Parse comma-separated user IDs
        USER_IDS = [uid.strip() for uid in USER_ID_INPUT.split(',') if uid.strip()]
    except:
        pass
else:
    print("💻 Local Environment — using fallback data sources")

try:
    import networkx as nx
except ImportError:
    nx = None

try:
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    cosine_similarity = None

try:
    import torch
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    SentenceTransformer = None
    embedder = None
    print("⚠️ sentence-transformers or torch not available. Embedding-based matching will be disabled.")
except OSError as e:
    SentenceTransformer = None
    embedder = None
    print(f"⚠️ Failed to load torch: {e}. Embedding-based matching will be disabled.")

# Check if we're in a Streamlit app context
try:
    import streamlit as st
    USE_SQL_CONNECTOR = True
    print("🔌 Databricks Streamlit App — using SQL Connector for reads")
    
    # Import SQL Connector dependencies
    from databricks import sql
    from databricks.sdk.core import Config
except ImportError:
    # We're in a notebook or local env - use Spark SQL or mock
    print("📓 Non-Streamlit environment")
    
    # Import Spark dependencies (optional)
    try:
        import mlflow
        from pyspark.sql import functions as F
        from delta.tables import DeltaTable
        from mlflow.deployments import get_deploy_client
    except ImportError:
        print("⚠️ Spark/MLflow dependencies not available")
        mlflow = None
        F = None
        DeltaTable = None
        get_deploy_client = None

# ── DATABRICKS FOUNDATION MODEL CLIENT ────────────────────────────────────────
if IN_DATABRICKS and not USE_SQL_CONNECTOR and get_deploy_client:
    try:
        llm_client = get_deploy_client("databricks")
    except:
        llm_client = None
else:
    llm_client = None
    if not IN_DATABRICKS:
        print("⚠️ LLM client not available in local environment")


# =============================================================================
# SQL CONNECTOR HELPER FUNCTIONS
# =============================================================================

try:
    from databricks import sql
except ImportError:
    sql = None

def get_sql_connection():
    """
    Create and return a Databricks SQL connection.
    Only used when USE_SQL_CONNECTOR is True (Streamlit app context).
    """
    if not USE_SQL_CONNECTOR:
        raise RuntimeError("SQL Connector not available in this environment")
    
    cfg = Config()
    connection = sql.connect(
        server_hostname=cfg.host.replace('https://', '').replace('http://', ''),
        http_path=WAREHOUSE_HTTP_PATH,
        credentials_provider=lambda: cfg.authenticate,
        use_cloud_fetch=False
    )
    return connection

def execute_sql_query(query: str) -> pd.DataFrame:
    """
    Execute SQL query using either Spark SQL (notebook) or SQL Connector (app).
    Returns a pandas DataFrame.
    """
    if USE_SQL_CONNECTOR:
        # Use SQL Connector
        connection = get_sql_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            
            # Fetch all results
            results = cursor.fetchall()
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Convert to DataFrame
            df = pd.DataFrame(results, columns=columns)
            
            cursor.close()
            connection.close()
            
            return df
        except Exception as e:
            try:
                connection.close()
            except:
                pass
            raise e
    else:
        # Use Spark SQL
        from pyspark.sql import SparkSession
        try:
            spark = SparkSession.builder.getOrCreate()
            return spark.sql(query).toPandas()
        except Exception as e:
            # Check if this is a namespace issue in local Spark (e.g. workspace.default.table)
            # Local Spark often doesn't have catalogs/schemas configured
            if "REQUIRES_SINGLE_PART_NAMESPACE" in str(e) or "TABLE_OR_VIEW_NOT_FOUND" in str(e):
                parts = query.split("FROM")
                if len(parts) > 1:
                    table_part = parts[1].strip().split()[0]
                    if "." in table_part:
                        # Extract table name only
                        table_name = table_part.split(".")[-1]
                        # Replace in query
                        new_query = query.replace(table_part, table_name)
                        print(f"⚠️  Namespace error. Retrying with table name only: {table_name}")
                        try:
                            return spark.sql(new_query).toPandas()
                        except:
                            pass
            raise e




def get_courses_for_skill_via_embeddings(
    skill: str,
    top_k: int = 20,
    min_similarity: float = 0.30,
    checkpoint_table: str = "workspace.default.mcf_skills_course_embeddings_v1"
) -> pd.DataFrame:
    """
    Given a skill name, retrieve the top matching course IDs from the
    pre-computed embeddings checkpoint table using cosine similarity.

    Compatible with both Databricks notebook (Spark) and Streamlit 
    SQL connector environments.

    Args:
        skill:             Skill name to search for.
        top_k:             Maximum number of course IDs to return.
        min_similarity:    Minimum cosine similarity threshold. Results below
                           this threshold are included only if needed to reach top_k.
        checkpoint_table:  Fully qualified embeddings table name.

    Returns:
        DataFrame with columns: source_id, source_title, score
        sorted by score descending.
    """
    import numpy as np

    # Step 1 — Load all course embeddings from checkpoint table
    query = f"""
        SELECT source_id, source_title, embedding
        FROM {checkpoint_table}
        WHERE source_type = 'course'
        AND test_config = 'TestA3'
    """
    df = execute_sql_query(query)

    if df.empty:
        logger.warning(f"No embeddings found in {checkpoint_table}")
        return pd.DataFrame(columns=["source_id", "source_title", "score"])

    # Step 2 — Parse embeddings (stored as array/list in the table)
    # Handle both native array columns and string-serialised arrays
    try:
        emb_matrix = np.vstack(df["embedding"].values)
    except ValueError:
        import ast
        df["embedding"] = df["embedding"].apply(
            lambda x: ast.literal_eval(x) if isinstance(x, str) else x
        )
        emb_matrix = np.vstack(df["embedding"].values)

    # Step 3 — Encode query skill using the same model
    # SentenceTransformer must be available in the Streamlit environment
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_vec = model.encode([skill], normalize_embeddings=True)[0]
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        )

    # Step 4 — Compute cosine similarity (embeddings are pre-normalised)
    scores = emb_matrix @ query_vec

    # Step 5 — Rank and filter
    df["score"] = scores
    df_sorted = df.sort_values("score", ascending=False)

    # Apply similarity threshold, fall back to top_k if too few pass threshold
    df_filtered = df_sorted[df_sorted["score"] >= min_similarity].head(top_k)
    if len(df_filtered) < top_k:
        df_filtered = df_sorted.head(top_k)

    return df_filtered[["source_id", "source_title", "score"]].reset_index(drop=True)


def get_candidate_course_ids_for_skills(
    skill_gaps: list,
    top_k_per_skill: int = 10,
    min_similarity: float = 0.30,
    checkpoint_table: str = "workspace.default.mcf_skills_course_embeddings_v1"
) -> list:
    """
    Given a list of SkillGap objects, return a deduplicated list of
    candidate course IDs ranked by relevance across all skills.

    Args:
        skill_gaps:        List of SkillGap objects with .skill and .priority attributes.
        top_k_per_skill:   Courses to retrieve per skill before deduplication.
        min_similarity:    Minimum cosine similarity threshold.
        checkpoint_table:  Fully qualified embeddings table name.

    Returns:
        List of course ID strings, ordered by aggregate weighted score.
    """
    import numpy as np
    from collections import defaultdict

    # Load embeddings once and reuse across all skills
    query = f"""
        SELECT source_id, source_title, embedding
        FROM {checkpoint_table}
        WHERE source_type = 'course'
        AND test_config = 'TestA3'
    """
    df = execute_sql_query(query)

    if df.empty:
        logger.warning(f"No embeddings found in {checkpoint_table}")
        return []

    try:
        emb_matrix = np.vstack(df["embedding"].values)
    except ValueError:
        import ast
        df["embedding"] = df["embedding"].apply(
            lambda x: ast.literal_eval(x) if isinstance(x, str) else x
        )
        emb_matrix = np.vstack(df["embedding"].values)

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        )

    course_scores = defaultdict(float)

    for gap in skill_gaps:
        query_vec = model.encode([gap.skill], normalize_embeddings=True)[0]
        scores = emb_matrix @ query_vec

        df["score"] = scores
        df_sorted = df.sort_values("score", ascending=False)

        df_filtered = df_sorted[df_sorted["score"] >= min_similarity].head(top_k_per_skill)
        if len(df_filtered) < top_k_per_skill:
            df_filtered = df_sorted.head(top_k_per_skill)

        # Weight score by skill priority (0.0–1.0)
        weight = float(gap.priority) if hasattr(gap, "priority") else 1.0
        for _, row in df_filtered.iterrows():
            course_scores[row["source_id"]] += row["score"] * weight

    # Sort by aggregate weighted score
    ranked = sorted(course_scores.items(), key=lambda x: x[1], reverse=True)
    return [course_id for course_id, _ in ranked]



# =============================================================================
# SECTION 1-3: DATA LOADING FROM KNOWLEDGE GRAPH OUTPUT
# =============================================================================

_embedding_cache = {}
def get_embedding(text):
    """
    FIX 7: Defensive embedding function that handles any input type safely.
    
    Converts any input (dict, list, object) to string before generating embedding.
    This prevents "'dict' object has no attribute 'lower'" errors.
    
    Args:
        text: Any input (str, dict, list, int, etc.)
    
    Returns:
        numpy array: Embedding vector
    """
    # FIX 7: Convert any input to string
    if isinstance(text, dict):
        # If it's a dict with 'skill' key, extract that
        if 'skill' in text:
            text = text['skill']
        else:
            # Otherwise just convert to string (not ideal but safe)
            text = str(text)
            print(f"⚠️ get_embedding() received dict without 'skill' key: {text[:50]}...")
    elif not isinstance(text, str):
        # Convert any other type to string
        text = str(text)
    
    # Now text is guaranteed to be a string
    key = text.lower().strip()
    if key not in _embedding_cache:
        if embedder:
            _embedding_cache[key] = embedder.encode([key])
        else:
            # Fallback for when sentence-transformers is not available
            return np.zeros(384) # Standard MiniLM-L6-v2 size
    return _embedding_cache[key]

def normalize_skill_list(skills_input):
    """
    FIX 5 + FIX 17: Robust normalization of user skills that PRESERVES proficiency levels.
    
    Handles:
    - Dictionary: {"Python": "Beginner", "SQL": "Advanced"} → returns dict as-is
    - List of dicts: [{"skill": "Python", "level": "Beginner"}, ...] → dict {skill: level}
    - List of strings: ["Python", "SQL"] → dict {skill: "Unknown"}
    - None/empty → returns {}
    
    This prevents "'dict' object has no attribute 'lower'" errors AND preserves
    proficiency information for graduated gap filtering.
    
    Args:
        skills_input: Various formats (list, dict, list of dicts, None)
    
    Returns:
        dict: {skill_name: proficiency_level} mapping
    """
    if skills_input is None:
        return {}
    
    # Dictionary format (skill -> proficiency mapping) - return as-is
    if isinstance(skills_input, dict):
        return {str(k).strip(): str(v).strip() for k, v in skills_input.items() if k}
    
    # List or tuple
    if isinstance(skills_input, (list, tuple)):
        if len(skills_input) == 0:
            return {}
        
        result = {}
        for item in skills_input:
            if isinstance(item, str):
                # Plain string - no proficiency info
                result[item.strip()] = "Unknown"
            elif isinstance(item, dict):
                # Dict with skill and proficiency
                skill = item.get('skill') or item.get('name') or item.get('skill_name')
                level = item.get('level') or item.get('proficiency') or item.get('value') or "Unknown"
                
                if skill:
                    result[str(skill).strip()] = str(level).strip() if isinstance(level, str) else "Unknown"
            else:
                # Convert other types to string
                result[str(item).strip()] = "Unknown"
        
        return result
    
    # Single string
    if isinstance(skills_input, str):
        # Parse comma and semicolon separated values
        parts = []
        for part in skills_input.split(';'):
            parts.extend(part.split(','))
        return {s.strip(): "Unknown" for s in parts if s.strip()}

    # Numpy array
    if isinstance(skills_input, np.ndarray):
        return normalize_skill_list(skills_input.tolist())
    
    # Unknown format
    print(f"⚠️ Unexpected skill input type: {type(skills_input)}, returning empty dict")
    return {}

def load_user_profile(user_id): 
    """
    Load user profile from Stage 1 output or user profile table.
    Expected schema: user_id, user_skills (array), target_roles (array), budget, weekly_hours, modality
    
    FIX 5 + FIX 17 APPLIED: Now normalizes user_skills to dict with proficiency levels.
    """
    if IN_DATABRICKS:
        try:
            # Try to load from Stage 1 output table
            query = f"""
                SELECT user_id, user_skills, target_roles, budget, weekly_hours, modality
                FROM {OUTPUT_SCHEMA}.user_profiles
                WHERE user_id = '{user_id}'
                ORDER BY user_id ASC
                LIMIT 1
            """
            profile_df = execute_sql_query(query)
            
            if len(profile_df) > 0:
                row = profile_df.iloc[0]
                
                # Helper function to convert to list safely
                def to_list(value):
                    if value is None:
                        return []
                    if isinstance(value, (list, tuple)):
                        return list(value)
                    if isinstance(value, np.ndarray):
                        return value.tolist()
                    if isinstance(value, str):
                        try:
                            return json.loads(value)
                        except:
                            return [value]
                    return []
                
                # FIX 5 + FIX 17: Normalize user_skills to dict with proficiency
                raw_user_skills = to_list(row['user_skills'])
                normalized_user_skills = normalize_skill_list(raw_user_skills)
                
                return {
                    "user_id": row['user_id'],
                    "user_skills": normalized_user_skills,  # FIX 17: Now dict {skill: proficiency}
                    "target_roles": to_list(row['target_roles']),
                    "budget": float(row['budget']) if pd.notna(row['budget']) else 2000.0,
                    "weekly_hours": float(row['weekly_hours']) if pd.notna(row['weekly_hours']) else 8.0,
                    "modality": row['modality'] if pd.notna(row['modality']) else 'hybrid'
                }
        except Exception as e:
            print(f"⚠️ Could not load user profile from table: {e}")
    
    # Local CSV fallback
    try:
        import os
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'user_profiles.csv')
        if os.path.exists(csv_path):
            profiles_df = pd.read_csv(csv_path)
            user_row = profiles_df[profiles_df['user_id'] == user_id]
            if len(user_row) > 0:
                row = user_row.iloc[0]
                
                def to_list(value):
                    if pd.isna(value):
                        return []
                    if isinstance(value, str):
                        try:
                            return ast.literal_eval(value)  # Safe eval for list strings
                        except:
                            return [value]
                    return []
                
                # FIX 5 + FIX 17: Normalize user_skills to dict
                raw_user_skills = to_list(row['user_skills'])
                normalized_user_skills = normalize_skill_list(raw_user_skills)
                
                print(f"✅ Loaded user profile from local CSV for {user_id}")
                return {
                    "user_id": row['user_id'],
                    "user_skills": normalized_user_skills,  # FIX 17: Dict with proficiency
                    "target_roles": to_list(row['target_roles']),
                    "budget": float(row['budget']) if pd.notna(row['budget']) else 2000.0,
                    "weekly_hours": float(row['weekly_hours']) if pd.notna(row['weekly_hours']) else 8.0,
                    "modality": row['modality'] if pd.notna(row['modality']) else 'hybrid'
                }
    except Exception as e2:
        print(f"⚠️ Could not load from local CSV: {e2}")
    
    # Dynamic fallback: Use input parameters or minimal structure
    print(f"⚠️ Creating minimal user profile for {user_id}")
    return {
        "user_id": user_id, 
        "user_skills": {},  # Empty dict - will be populated by user input
        "target_roles": [],
        "budget": 2000.0, 
        "weekly_hours": 8.0, 
        "modality": "hybrid"
    }

def find_similar_roles_in_kg(target_role: str, min_similarity: float = 0.70, top_k: int = 3):
    """
    FIX 1: Use embeddings to find semantically similar roles in the KG output table.
    FIX 3: Removed environment check - now tries to execute and handles failures gracefully.
    
    This solves the problem of roles not matching exactly in the database.
    For example, "Data Scientist" can match "Data Science Engineer" or "ML Engineer".
    
    Args:
        target_role: The role the user is searching for
        min_similarity: Minimum cosine similarity threshold (default 0.70)
        top_k: Number of top similar roles to return (default 3)
    
    Returns:
        list of tuples: [(matched_role, similarity_score), ...]
    """
    try:
        # Get all distinct roles from KG output table
        query = f"""
            SELECT DISTINCT role
            FROM {KG_OUTPUT_TABLE}
            WHERE role IS NOT NULL AND role != ''
            ORDER BY role ASC
        """
        roles_df = execute_sql_query(query)
        
        if len(roles_df) == 0:
            print(f"⚠️ No roles found in {KG_OUTPUT_TABLE}")
            return []
        
        available_roles = roles_df['role'].tolist()
        print(f"🔍 Searching {len(available_roles)} roles for matches to '{target_role}'...")
        
        # Compute embeddings
        target_emb = get_embedding(target_role)
        role_embeddings = [get_embedding(role) for role in available_roles]
        
        # Compute similarities
        similarities = []
        for role, role_emb in zip(available_roles, role_embeddings):
            sim = cosine_similarity(target_emb, role_emb)[0][0]
            if sim >= min_similarity:
                similarities.append((role, float(sim)))
        
        # Sort by similarity and return top k
        similarities.sort(key=lambda x: (-x[1], x[0]))  # FIX 12: DESC score, ASC role name
        top_matches = similarities[:top_k]
        
        if top_matches:
            print(f"✅ Found {len(top_matches)} similar roles:")
            for role, sim in top_matches:
                print(f"   • {role} (similarity: {sim:.2%})")
        else:
            print(f"⚠️ No roles found with similarity >= {min_similarity:.0%}")
        
        return top_matches
        
    except Exception as e:
        print(f"⚠️ Error in role similarity search: {e}")
        import traceback
        traceback.print_exc()
        return []

def load_kg_output_for_role(target_role): 
    """
    Load Knowledge Graph output for a specific role.
    This should contain the skills required for the role from Neo4j.
    Expected schema: role, skill_name, demand_count, category, prerequisites
    
    FIX 1 APPLIED: Now uses embeddings-based similarity matching as fallback.
    
    Tries data sources in succession:
    1. Exact match in Knowledge Graph output table
    2. SEMANTIC SIMILARITY MATCH using embeddings (NEW!)
    3. Direct extraction from JD table (crude LIKE match)
    4. Local CSV file
    5. Returns empty DataFrame if all fail
    """
    # Try primary KG output table - exact match
    try:
        query = f"""
            SELECT skill_name, demand_count, category, prerequisites
            FROM {KG_OUTPUT_TABLE}
            WHERE role = '{target_role}'
            ORDER BY demand_count DESC, skill_name ASC
        """
        kg_df = execute_sql_query(query)
        
        if len(kg_df) > 0:
            print(f"✅ Loaded {len(kg_df)} skills from Knowledge Graph for {target_role} (exact match)")
            return kg_df
    except Exception as e:
        print(f"⚠️ Could not load KG output: {e}")
    
    # NEW: Try semantic similarity match using embeddings
    print(f"⚠️ No exact match for '{target_role}', trying semantic similarity...")
    similar_roles = find_similar_roles_in_kg(target_role, min_similarity=ROLE_SIMILARITY_THRESHOLD, top_k=1)
    
    if similar_roles:
        best_match_role, similarity = similar_roles[0]
        print(f"🎯 Using similar role: '{best_match_role}' (similarity: {similarity:.1%})")
        
        try:
            query = f"""
                SELECT skill_name, demand_count, category, prerequisites
                FROM {KG_OUTPUT_TABLE}
                WHERE role = '{best_match_role}'
                ORDER BY demand_count DESC, skill_name ASC
            """
            kg_df = execute_sql_query(query)
            
            if len(kg_df) > 0:
                print(f"✅ Loaded {len(kg_df)} skills from similar role '{best_match_role}'")
                return kg_df
        except Exception as e:
            print(f"⚠️ Could not load data for similar role: {e}")
    
    # Try alternative: Extract directly from JD table
    try:
        print(f"⚠️ Attempting to extract skills directly from JD table for {target_role}")
        query = f"""
            SELECT DISTINCT skill_name, COUNT(*) as demand_count
            FROM {JD_TABLE}
            WHERE LOWER(job_title) LIKE LOWER('%{target_role}%')
               OR LOWER(role) LIKE LOWER('%{target_role}%')
            GROUP BY skill_name
            ORDER BY demand_count DESC, skill_name ASC
            LIMIT 20
        """
        jd_df = execute_sql_query(query)
        
        if len(jd_df) > 0:
            print(f"✅ Extracted {len(jd_df)} skills from JD table for {target_role}")
            # Add missing columns with defaults
            jd_df['category'] = 'Technical'
            jd_df['prerequisites'] = [[] for _ in range(len(jd_df))]
            return jd_df
    except Exception as e2:
        print(f"⚠️ Could not extract from JD table: {e2}")
    
    # Try local CSV file
    try:
        import os
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_graph.csv')
        if os.path.exists(csv_path):
            kg_df = pd.read_csv(csv_path)
            # Filter by role if column exists
            if 'role' in kg_df.columns:
                kg_df = kg_df[kg_df['role'].str.lower() == target_role.lower()]
            if len(kg_df) > 0:
                print(f"✅ Loaded {len(kg_df)} skills from local CSV for {target_role}")
                return kg_df
    except Exception as e3:
        print(f"⚠️ Could not load from local CSV: {e3}")
    
    # Final fallback: Return empty DataFrame with correct schema
    print(f"⚠️ No data available for {target_role}, returning empty skill set")
    return pd.DataFrame(columns=['skill_name', 'demand_count', 'category', 'prerequisites'])

def load_jd_demand_scores(target_role, kg_df):
    """
    Convert Knowledge Graph output to demand scores.
    Normalize demand_count to 0-1 scale.
    """
    if len(kg_df) == 0:
        return [], {}
    
    skills = kg_df['skill_name'].tolist()
    max_demand = kg_df['demand_count'].max()
    
    demand_db = {}
    for _, row in kg_df.iterrows():
        demand_db[row['skill_name']] = row['demand_count'] / 100.0  # Normalize to 0-1
    
    return skills, demand_db

def load_peer_data(target_role): 
    """
    Load peer CV data from resume dataset.
    Schema: Name, Age, Gender, Education_Level, Field_of_Study, Degrees, 
            Institute_Name, Graduation_Year, Experience_Years, Current_Job_Title,
            Previous_Job_Titles, Skills (comma-separated), Certifications, Target_Job_Description
    
    Returns:
        tuple: (peer_db_dict, None) where peer_db_dict = {'primary_db': {skill: normalized_frequency}}
    """
    if not IN_DATABRICKS:
        print(f"⚠️ No peer data available outside Databricks")
        return {'primary_db': {}}, None
    
    try:
        # Strategy 1: Exact role match in Current_Job_Title
        print(f"🔍 Loading peer data for role: {target_role}")
        query = f"""
            SELECT Skills, Current_Job_Title
            FROM {PEER_TABLE}
            WHERE Current_Job_Title = '{target_role}'
            ORDER BY Current_Job_Title, Skills, Name, Age, Graduation_Year
        """
        resumes_df = execute_sql_query(query)
        
        # Strategy 2: If no exact match, try partial match
        if len(resumes_df) == 0:
            print(f"   No exact matches, trying partial match...")
            query = f"""
                SELECT Skills, Current_Job_Title
                FROM {PEER_TABLE}
                WHERE LOWER(Current_Job_Title) LIKE LOWER('%{target_role}%')
                   OR LOWER(Target_Job_Description) LIKE LOWER('%{target_role}%')
                ORDER BY Current_Job_Title, Skills, Name, Age, Graduation_Year
            """
            resumes_df = execute_sql_query(query)
        
        # Strategy 3: If still no match, get general data
        if len(resumes_df) == 0:
            print(f"   No partial matches, using general peer data (top 100 resumes)...")
            query = f"""
                SELECT Skills, Current_Job_Title
                FROM {PEER_TABLE}
                ORDER BY Current_Job_Title, Skills, Name, Age, Graduation_Year
                LIMIT 100
            """
            resumes_df = execute_sql_query(query)
        
        if len(resumes_df) == 0:
            print(f"⚠️ No peer data available in {PEER_TABLE}")
            return {'primary_db': {}}, None
        
        print(f"✅ Found {len(resumes_df)} peer resumes")
        
        # Parse skills from comma-separated strings
        all_skills = []
        for _, row in resumes_df.iterrows():
            skills_str = row['Skills']
            if pd.notna(skills_str) and skills_str:
                # Split by comma and clean up
                skills = [s.strip() for s in str(skills_str).split(',')]
                all_skills.extend(skills)
        
        if not all_skills:
            print(f"⚠️ No skills found in peer data")
            return {'primary_db': {}}, None
        
        # Count skill frequencies
        skill_counts = Counter(all_skills)
        
        # Normalize frequencies
        max_count = max(skill_counts.values())
        peer_db = {skill: count / max_count for skill, count in skill_counts.items()}
        
        print(f"✅ Loaded peer data for {len(peer_db)} unique skills (from {len(resumes_df)} resumes)")
        print(f"   Top 5 peer skills: {', '.join(sorted(list(peer_db.keys()))[:5])}")  # FIX 15: Sorted
        
        return {'primary_db': peer_db}, None
        
    except Exception as e:
        print(f"⚠️ Could not load peer data: {e}")
        return {'primary_db': {}}, None

def load_course_skills_map(role_required_skills): 
    """
    DEPRECATED (FIX 4): This function is no longer used in the processing pipeline.
    Course discovery and matching is now handled by the Recommender module.
    
    This function previously loaded course-to-skill mappings from the course directory,
    but was creating a bottleneck by:
    - Only loading 10-100 courses (LIMIT clause)
    - Using crude substring matching
    - Pre-filtering courses before Recommender could apply semantic search
    
    Kept for backward compatibility only.
    
    Expected schema: coursereferencenumber, skills_covered (array) or what_you_learn (text)
    Note: Current table schema uses 'coursereferencenumber' not 'course_id'
    """
    print(f"⚠️ load_course_skills_map() is deprecated - course discovery now handled by Recommender")
    return {}

def build_knowledge_graph(role, kg_df): 
    """
    Build NetworkX graph from Knowledge Graph output.
    Uses the prerequisites field from KG output to create edges.
    """
    g = nx.DiGraph()
    g.add_node(role, type='Role')
    
    for _, row in kg_df.iterrows():
        skill = row['skill_name']
        g.add_node(skill, type='Skill', category=row.get('category', 'Technical'))
        g.add_edge(role, skill, relation='role-requires-skill')
        
        # Add prerequisite edges if available
        prereqs = row.get('prerequisites', [])
        if isinstance(prereqs, str):
            prereqs = json.loads(prereqs) if prereqs else []
        
        for prereq in prereqs:
            if prereq and prereq != skill:
                g.add_node(prereq, type='Skill')
                g.add_edge(prereq, skill, relation='skill-prerequisite-skill')
    
    return g

# =============================================================================
# SECTION 9 — GAP IDENTIFICATION + SCORING (MODIFIED FOR TWEAK 1 & 2)
# =============================================================================

# --- TEST COMPATIBILITY WRAPPERS ---
def get_mock_kg_data():
    """Returns a minimal mock Knowledge Graph DataFrame for testing."""
    return pd.DataFrame({
        'role': ['Data Scientist', 'Data Scientist', 'Software Engineer'],
        'skill': ['Python', 'Machine Learning', 'Java'],
        'skill_cluster': ['Programming', 'AI', 'Programming']
    })

def find_skill_gaps(user_skills, target_role, graph, full_match_threshold=0.80):
    """
    TWEAK 1: Embedding-Based Similarity with Partial Credit.
    Returns a dictionary of missing skills with (gap_weight, user_proficiency) tuples.
    - gap_weight: 1.0 - max_similarity (how much is missing)
    - user_proficiency: max_similarity (how good the user currently is)
    
    FIX 17: Now accepts dict {skill: proficiency} as user_skills (iterates over keys).
    """
    print(f"\nTraversing KG from '{target_role}'...")
    required = [n for n in graph.neighbors(target_role)
                if graph.edges[target_role, n].get('relation') == 'role-requires-skill']
    
    gaps_dict = {}
    for req in required:
        req_emb = get_embedding(req)
        
        if user_skills:
            # FIX 17: user_skills is now dict - iterate over keys (skill names)
            sims = [cosine_similarity(get_embedding(u), req_emb)[0][0] for u in user_skills]
            max_sim = max(sims)
        else:
            max_sim = 0.0

        # If similarity is less than full match threshold, it's a gap
        if max_sim < full_match_threshold:
            # gap_weight calculation: 1.0 = full gap, lower means partial match
            gap_weight = round(max(0.0, 1.0 - max_sim), 3)
            user_proficiency = round(max_sim, 3)  # Current skill level
            gaps_dict[req] = (gap_weight, user_proficiency)
            
    return gaps_dict

def compute_career_distance(user_skills, missing_skill, graph):
    """
    FIX 17: Now accepts dict {skill: proficiency} as user_skills (checks keys with 'in').
    """
    prereqs = [n for n in graph.predecessors(missing_skill)
               if graph.edges[n, missing_skill].get('relation') == 'skill-prerequisite-skill']
    if not prereqs: return 1
    unmet = [p for p in prereqs if p not in user_skills]  # Works with dict (checks keys)
    if not unmet: return 1
    return 1 + max(compute_career_distance(user_skills, p, graph) for p in unmet)

def jd_demand_expert(skill, jd_demand_db, role_required_skills):
    max_d = jd_demand_db.get(role_required_skills[0], 1.0) if role_required_skills else 1.0
    return min(1.0, jd_demand_db.get(skill, 0.0) / max_d) if max_d > 0 else 0.5

def peer_cv_expert(skill, peer_data):
    if not peer_data or not peer_data.get('primary_db'): return 0.5
    db = peer_data['primary_db']
    raw = db.get(skill, 0.0)
    max_r = max(db.values()) if db.values() else 1.0
    return min(1.0, raw / max_r) if max_r > 0 else 0.5

def arbitrate_skill_gaps(missing_skills_dict, user_skills, graph, jd_demand_db, role_required_skills, peer_data):
    """
    TWEAK 2: Competing Experts Framework with Strict Meta-Arbiter Formula.
    Formula: α(0.45) * demand_score + β(0.35) * peer_score + γ(0.20) * graph_distance_score
    
    Priority Levels:
    - "critical": unified_score >= 0.75
    - "high": unified_score >= 0.50
    - "medium": unified_score >= 0.30
    - "low": unified_score < 0.30
    - "user-request": Special override category (set externally, not by algorithm)
    
    FIX 17: Now accepts dict {skill: proficiency} as user_skills.
    """
    print("\nRunning Competing Experts Arbitator...")
    prioritised_gaps = []
    
    for skill, (gap_weight, user_proficiency) in missing_skills_dict.items():
        # 1. Expert Scores
        demand_score = jd_demand_expert(skill, jd_demand_db, role_required_skills)
        peer_score   = peer_cv_expert(skill, peer_data)
        
        # 2. Graph Distance Score (Inverted: closer = easier = higher priority score)
        raw_dist = compute_career_distance(user_skills, skill, graph)
        # Distance mapping: 1 -> 1.0, 2 -> 0.8, 3 -> 0.6, etc.
        dist_score = max(0.0, 1.0 - ((raw_dist - 1) * 0.2)) 
        
        # 3. Meta-Arbiter Fusion
        unified_score = (0.45 * demand_score) + (0.35 * peer_score) + (0.20 * dist_score)
        
        # Determine Priority Category
        if unified_score >= 0.75: 
            priority = "critical"
        elif unified_score >= 0.50: 
            priority = "high"
        elif unified_score >= 0.30:
            priority = "medium"
        else:
            priority = "low"
        
        # Generate rationale with normalized relative scores (not absolute percentages)
        rationale = f"Demand: {demand_score:.0%} (relative to top skill); Peer prevalence: {peer_score:.0%} (relative to most common)"
        
        prioritised_gaps.append({
            "skill": skill,
            "category": "Technical", # Default mapping
            "gap_weight": float(gap_weight),
            "user_skill_proficiency": float(user_proficiency),
            "demand_score": round(float(demand_score), 3),
            "peer_score": round(float(peer_score), 3),
            "graph_distance": int(raw_dist),
            "priority": priority,
            "rationale": rationale,
            "unified_score": round(float(unified_score), 4) # Retained for sorting
        })
        
    return sorted(prioritised_gaps, key=lambda x: (-x['unified_score'], x['skill']))  # FIX 14: Tiebreaker


# =============================================================================
# FIX 8: STABLE TOP 5 COMPUTATION (USER-INDEPENDENT)
# =============================================================================

def compute_stable_top5(role_required_skills, jd_demand_db, peer_data):
    """
    FIX 8: Compute stable top 5 skills based ONLY on role requirements.
    
    This function scores ALL role-required skills by demand + peer prevalence,
    WITHOUT considering user proficiency. This ensures the top 5 remains constant
    regardless of what skills the user declares they already know.
    
    Formula: 0.45 * demand + 0.35 * peer (ignoring distance since we don't filter by user)
    
    Args:
        role_required_skills: List of all skills required for the target role
        jd_demand_db: Dictionary of skill -> demand score
        peer_data: Dictionary with 'primary_db' containing skill -> prevalence scores
    
    Returns:
        list: Top 5 skill names, sorted by combined demand + peer score
    """
    if not role_required_skills:
        print("⚠️ No role-required skills provided for stable top5 computation")
        return []
    
    print(f"\n🎯 Computing stable top 5 from {len(role_required_skills)} role-required skills...")
    
    skill_scores = []
    for skill in role_required_skills:
        demand_score = jd_demand_expert(skill, jd_demand_db, role_required_skills)
        peer_score = peer_cv_expert(skill, peer_data)
        
        # Simplified scoring: 0.45 demand + 0.35 peer (no distance component)
        combined_score = (0.45 * demand_score) + (0.35 * peer_score)
        
        skill_scores.append({
            'skill': skill,
            'score': combined_score,
            'demand': demand_score,
            'peer': peer_score
        })
    
    # Sort by combined score (DESC), then skill name (ASC) for deterministic tiebreaking
    skill_scores.sort(key=lambda x: (-x['score'], x['skill']))
    
    # Extract top 5
    top_5 = [s['skill'] for s in skill_scores[:5]]
    
    print(f"✅ Stable top 5 skills (user-independent):")
    for i, s in enumerate(skill_scores[:5], 1):
        print(f"   {i}. {s['skill']} (score: {s['score']:.3f}, demand: {s['demand']:.3f}, peer: {s['peer']:.3f})")
    
    return top_5


# =============================================================================
# FIX 2 + FIX 18: USER-DECLARED SKILLS FILTERING (PROFICIENCY-AWARE)
# =============================================================================

def filter_user_declared_skills(gaps_list: list, user_declared_skills: dict, 
                                  similarity_threshold: float = 0.85) -> dict:
    """
    FIX 2 + FIX 18: Proficiency-aware skill gap filtering with graduated approach.
    
    This solves the state swapping issue AND respects proficiency levels:
    1. Filtering at the DATA LAYER (not UI layer)
    2. Using embeddings for fuzzy matching (handles variations like "Python" vs "Python Programming")
    3. GRADUATED filtering based on proficiency:
       - Beginner/Novice/Unknown → KEEP gap (user needs to learn)
       - Intermediate → KEEP gap with adjustment tag (partial knowledge)
       - Advanced/Expert → REMOVE gap (user is proficient)
    4. Adding metadata to track what was filtered and why
    5. Ensuring deterministic, consistent filtering across refreshes
    
    Args:
        gaps_list: List of gap dictionaries from arbitrate_skill_gaps()
        user_declared_skills: Dict {skill: proficiency_level} the user explicitly declares
        similarity_threshold: Minimum similarity to consider a skill match (default 0.85)
    
    Returns:
        dict with keys:
            - 'filtered_gaps': List of gaps after proficiency-aware filtering
            - 'removed_gaps': List of gaps that were filtered out (Advanced/Expert only)
            - 'filter_metadata': Info about what was filtered
    """
    if not user_declared_skills or not isinstance(user_declared_skills, dict):
        print(f"ℹ️ No user-declared skills to filter or not dict")
        return {
            'filtered_gaps': gaps_list,
            'removed_gaps': [],
            'filter_metadata': {
                'total_input_gaps': len(gaps_list),
                'user_declared_count': 0,
                'removed_count': 0,
                'remaining_count': len(gaps_list)
            }
        }
    
    print(f"\n🔍 Filtering gaps against {len(user_declared_skills)} user-declared skills (with proficiency)...")
    print(f"   User declared: {', '.join([f'{s} ({p})' for s, p in user_declared_skills.items()])}")
    
    # Compute embeddings for user-declared skills
    user_skill_embeddings = {skill: get_embedding(skill) for skill in user_declared_skills.keys()}
    
    filtered_gaps = []
    removed_gaps = []
    
    for gap in gaps_list:
        gap_skill = gap['skill']
        gap_emb = get_embedding(gap_skill)
        
        # Check similarity against all user-declared skills
        max_similarity = 0.0
        best_match_skill = None
        
        for user_skill, user_emb in user_skill_embeddings.items():
            sim = cosine_similarity(gap_emb, user_emb)[0][0]
            if sim > max_similarity:
                max_similarity = sim
                best_match_skill = user_skill
        
        # If similarity is high enough, check proficiency level
        if best_match_skill and max_similarity >= similarity_threshold:
            proficiency = user_declared_skills[best_match_skill].lower()
            
            # FIX 18: Graduated filtering based on proficiency
            if proficiency in ['advanced', 'expert']:
                # REMOVE gap - user is proficient enough
                gap_copy = gap.copy()
                gap_copy['filter_reason'] = f"User declared '{best_match_skill}' with proficiency '{proficiency}' (similarity: {max_similarity:.1%})"
                gap_copy['filter_match_similarity'] = round(float(max_similarity), 3)
                removed_gaps.append(gap_copy)
                print(f"   ✂️ Filtered: {gap_skill} (matches user's '{best_match_skill}' at '{proficiency}' level, {max_similarity:.1%})")
            
            elif proficiency in ['intermediate']:
                # KEEP gap with adjustment - user has partial knowledge
                gap_copy = gap.copy()
                gap_copy['proficiency_adjustment'] = f"Intermediate - partial gap"
                gap_copy['matched_user_skill'] = best_match_skill
                gap_copy['user_proficiency'] = proficiency
                filtered_gaps.append(gap_copy)
                print(f"   ⚠️ Kept (Intermediate): {gap_skill} (partial gap - user has intermediate '{best_match_skill}', {max_similarity:.1%})")
            
            else:  # beginner, novice, unknown
                # KEEP gap - user needs to learn this
                gap_copy = gap.copy()
                gap_copy['matched_user_skill'] = best_match_skill
                gap_copy['user_proficiency'] = proficiency
                filtered_gaps.append(gap_copy)
                print(f"   🟢 Kept (Beginner/Unknown): {gap_skill} (user declared '{best_match_skill}' at '{proficiency}' level, {max_similarity:.1%})")
        else:
            # No match or low similarity - keep gap
            filtered_gaps.append(gap)
    
    filter_metadata = {
        'total_input_gaps': len(gaps_list),
        'user_declared_count': len(user_declared_skills),
        'removed_count': len(removed_gaps),
        'remaining_count': len(filtered_gaps),
        'similarity_threshold': similarity_threshold
    }
    
    print(f"✅ Filtering complete: {len(removed_gaps)} gaps removed (Advanced/Expert), {len(filtered_gaps)} remaining")
    
    return {
        'filtered_gaps': filtered_gaps,
        'removed_gaps': removed_gaps,
        'filter_metadata': filter_metadata
    }


# =============================================================================
# FIX 2B: USER PROFILE PERSISTENCE (PREVENT STATE CYCLING)
# =============================================================================

def update_user_profile_skills(user_id: str, updated_skills: dict) -> bool:
    """
    FIX 2B + FIX 17: Persist updated user skills to the database to prevent state cycling.
    
    This solves the cycling problem where:
    - User declares skill → filtered → not returned
    - Next call: skill declaration lost from DB → returned again → cycle repeats
    
    This function MERGES new skills with existing ones (no duplicates) and updates the DB.
    
    Args:
        user_id: The user whose profile to update
        updated_skills: Current dict of user skills {skill: proficiency} (including newly declared ones)
    
    Returns:
        bool: True if update succeeded, False otherwise
    """
    if not updated_skills:
        print(f"ℹ️ No skills to update for user {user_id}")
        return True
    
    if not IN_DATABRICKS or USE_SQL_CONNECTOR:
        print(f"⚠️ User profile update only available in Databricks notebook environment")
        return False
    
    try:
        profile_table = f"{OUTPUT_SCHEMA}.user_profiles"
        now = datetime.now(timezone.utc)
        
        # Load existing profile to get other fields
        existing_profile = load_user_profile(user_id)
        
        # Merge skills: combine existing + new, preserve proficiency from latest
        combined_skills = {**existing_profile['user_skills'], **updated_skills}
        
        print(f"\n💾 Updating user profile for {user_id}...")
        print(f"   Previous skills: {len(existing_profile['user_skills'])}")
        print(f"   New skills: {len(updated_skills)}")
        print(f"   Combined skills: {len(combined_skills)}")
        
        # Prepare row for update - convert dict to list for storage
        # Store as list of dicts: [{"skill": "Python", "level": "Beginner"}, ...]
        skills_list = [{"skill": k, "level": v} for k, v in combined_skills.items()]
        
        row = {
            "user_id": user_id,
            "user_skills": skills_list,
            "target_roles": existing_profile['target_roles'],
            "budget": existing_profile['budget'],
            "weekly_hours": existing_profile['weekly_hours'],
            "modality": existing_profile['modality'],
            "updated_at": now
        }
        
        # Create DataFrame
        df = spark.createDataFrame([row])
        
        # Try to create schema if it doesn't exist
        try:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OUTPUT_SCHEMA}")
        except:
            pass
        
        # Merge update: if user exists, update; otherwise insert
        try:
            DeltaTable.forName(spark, profile_table).alias("t").merge(
                df.alias("s"), "t.user_id = s.user_id"
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
            print(f"   ✅ User profile updated in {profile_table}")
            return True
        except Exception as merge_error:
            # Table might not exist - try to create it
            try:
                df.write.format("delta").mode("append").saveAsTable(profile_table)
                print(f"   ✅ Created {profile_table} and saved user profile")
                return True
            except Exception as create_error:
                print(f"   ❌ Failed to update user profile: {create_error}")
                return False
                
    except Exception as e:
        print(f"❌ Error updating user profile: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# SECTION 10 — OUTPUT (MODIFIED FOR FIX 4: SEPARATION OF CONCERNS)
# =============================================================================

def build_json_output(target_role, prioritised_gaps, filter_metadata=None, removed_gaps=None, top_5_skills=None):
    """
    FIX 4: Clean Separation of Concerns - Course discovery removed.
    FIX 8: Top 5 stability fix - Accept pre-computed top5 to prevent state cycling.
    
    Generates skill gap analysis output WITHOUT course pre-filtering.
    Course discovery and matching is now handled entirely by the Recommender module,
    which has access to:
    - Full course catalog (no LIMIT bottleneck)
    - Semantic search with embeddings
    - Fuzzy matching for synonyms
    - Neural ranking algorithms
    - CSP constraint satisfaction
    
    Output Schema:
    - target_role: Role being analyzed
    - total_gaps: Number of skill gaps identified
    - gaps: Prioritized list of gap objects
    - top_5_skills: List of top 5 skill names (STABLE - extracted from role requirements)
    - filter_metadata: User-declared skills filtering stats (FIX 2)
    - removed_gaps: Skills that were filtered out (FIX 2B)
    
    Args:
        target_role: The job role being analyzed
        prioritised_gaps: List of gap dictionaries (AFTER filtering user-declared skills)
        filter_metadata: Optional metadata about user-declared skills filtering
        removed_gaps: Optional list of gaps that were filtered out
        top_5_skills: Optional pre-computed top 5 skills (FIX 8 - from role requirements, user-independent)
    
    Returns:
        dict: JSON output with skill gaps (NO candidate_courses)
    """
    # Clean up internal sorting keys before output
    gaps_out = []
    for g in prioritised_gaps:
        clean_g = g.copy()
        #clean_g.pop("unified_score", None). #Chad: Added back, needed for final sorting and display of gap %
        gaps_out.append(clean_g)
    
    # FIX 8: Use pre-computed top5 if provided, otherwise extract from current gaps
    if top_5_skills is None:
        # Fallback: extract from current gaps (backward compatibility)
        top_5_skills = [gap['skill'] for gap in gaps_out[:5]]

    output_doc = {
        "skill_gaps": {
            "target_role": target_role,
            "total_gaps": len(gaps_out),
            "gaps": gaps_out,
            "top_5_skills": top_5_skills  # FIX 8: Stable across user skill changes
            # NOTE: candidate_courses REMOVED (FIX 4)
            # Recommender will handle ALL course discovery using:
            # - Semantic search over full catalog
            # - Embedding-based similarity matching
            # - Neural ranking and CSP filtering
        }
    }
    
    # Add filter metadata if available
    if filter_metadata:
        output_doc['skill_gaps']['filter_metadata'] = filter_metadata
    
    # Add removed gaps for UI visibility (FIX 2B)
    if removed_gaps:
        output_doc['skill_gaps']['removed_gaps'] = removed_gaps
    
    return output_doc

def write_single_role_to_delta(user_id: str, role_result: dict):
    """
    Writes a single role's gap analysis result to Delta table immediately after processing.
    This provides incremental, consistent logging throughout execution.
    Schema: user_id (STRING), target_role (STRING), gap_analysis_json (STRING), computed_at (TIMESTAMP)
    
    NOTE: Delta writes ALWAYS use Spark (even in Streamlit), as SQL Connector doesn't support writes.
    """
    output_table = f"{OUTPUT_SCHEMA}.user_analysis_log"
    now = datetime.now(timezone.utc)
    
    json_payload = json.dumps(role_result, indent=2)
    row = {
        "user_id": user_id,
        "target_role": role_result["skill_gaps"]["target_role"],
        "gap_analysis_json": json_payload,
        "computed_at": now
    }
    
    if IN_DATABRICKS and not USE_SQL_CONNECTOR:
        # Only write to Delta if we have Spark available (notebook environment)
        # Try to create schema if it doesn't exist
        try:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OUTPUT_SCHEMA}")
        except Exception as e:
            pass  # Schema may already exist
        
        df = spark.createDataFrame([row])
        
        # Using merge to update if exists, insert if new
        try:
            DeltaTable.forName(spark, output_table).alias("t").merge(
                df.alias("s"), "t.user_id = s.user_id AND t.target_role = s.target_role"
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
            print(f"   💾 Logged to Delta: {output_table}")
        except Exception:
            # Fallback if table doesn't exist - create it
            df.write.format("delta").mode("append").saveAsTable(output_table)
            print(f"   💾 Initialized Delta table and logged: {output_table}")
    else:
        print(f"   ⚠️ Delta write skipped (SQL Connector mode or not in Databricks)")
        print(f"   Result preview: {role_result['skill_gaps']['target_role']} - {role_result['skill_gaps']['total_gaps']} gaps")

def write_gap_list_to_delta(user_id: str, all_role_results: list):
    """
    DEPRECATED: Use write_single_role_to_delta() for incremental logging.
    This batch function is kept for backward compatibility.
    
    NOTE: Delta writes ALWAYS use Spark (even in Streamlit), as SQL Connector doesn't support writes.
    """
    output_table = f"{OUTPUT_SCHEMA}.user_analysis_log"
    now = datetime.now(timezone.utc)
    
    rows = []
    for role_result in all_role_results:
        json_payload = json.dumps(role_result, indent=2)
        rows.append({
            "user_id": user_id,
            "target_role": role_result["skill_gaps"]["target_role"],
            "gap_analysis_json": json_payload,
            "computed_at": now
        })

    if IN_DATABRICKS and not USE_SQL_CONNECTOR:
        # Only write to Delta if we have Spark available (notebook environment)
        # Try to create schema if it doesn't exist (may fail due to permissions)
        try:
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {OUTPUT_SCHEMA}")
        except Exception as e:
            print(f"⚠️  Could not create schema (may already exist or lack permissions): {e}")
        
        df = spark.createDataFrame(rows)
        # Using merge/overwrite by user_id + target_role to keep one active record per user per role
        try:
            DeltaTable.forName(spark, output_table).alias("t").merge(
                df.alias("s"), "t.user_id = s.user_id AND t.target_role = s.target_role"
            ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
            print(f"\n✅ JSON Payload written to Delta: {output_table} ({len(rows)} roles)")
        except Exception:
            # Fallback if table doesn't exist
            df.write.format("delta").mode("append").saveAsTable(output_table)
            print(f"\n✅ Initialized and wrote JSON Payload to Delta: {output_table} ({len(rows)} roles)")
    else:
        print(f"\n⚠️ Delta write skipped (SQL Connector mode or not in Databricks)")
        print("\n=== FINAL JSON OUTPUT ARTIFACTS ===")
        for i, role_result in enumerate(all_role_results, 1):
            print(f"\n--- Role {i}: {role_result['skill_gaps']['target_role']} ---")
            print(json.dumps(role_result, indent=2))


# =============================================================================
# MAIN PIPELINE (ALL FIXES APPLIED + FIX 8: TOP 5 STABILITY + FIX 17 & 18)
# =============================================================================

def process_single_user(
    user_id: str, 
    user_skills=None, 
    target_roles=None,
    budget: float = 2000.0,
    weekly_hours: float = 8.0,
    modality: str = "hybrid"
) -> dict:
    """
    Process skill gap analysis for a single user.
    
    FIX 2 APPLIED: Filters user-declared skills consistently at data layer.
    FIX 2B APPLIED: Persists user-declared skills to prevent cycling.
    FIX 4 APPLIED: Removed course pre-filtering bottleneck.
    FIX 5 APPLIED: Robust skill format normalization.
    FIX 6 APPLIED: Direct input support for Streamlit apps (bypass database loading).
    FIX 7 APPLIED: Defensive embedding function (handles any input type safely).
    FIX 8 APPLIED: Top 5 stability fix (extract from role requirements, user-independent).
    FIX 17 APPLIED: Proficiency-aware normalization (returns dict {skill: proficiency}).
    FIX 18 APPLIED: Graduated skill filtering (Beginner kept, Advanced removed).
    
    Args:
        user_id: User identifier
        user_skills: Optional. Direct input of user skills (bypasses database load).
                     Accepts: dict {skill: proficiency}, list of strings, list of dicts, or any format.
        target_roles: Optional. Direct input of target roles (bypasses database load).
                      Accepts: list of strings or single string.
        budget: Optional. User budget (default: 2000.0)
        weekly_hours: Optional. Weekly study hours (default: 8.0)
        modality: Optional. Learning modality (default: "hybrid")
    
    Returns: 
        dict with processing stats (success, total_roles, total_gaps, duration, all_role_results)
    """
    user_start = time.time()
    
    try:
        # FIX 6 + FIX 17: Support direct input (Streamlit app mode) OR database loading (notebook mode)
        if user_skills is not None and target_roles is not None:
            # Direct input mode - normalize skills to dict {skill: proficiency}
            print(f"🎯 Processing user {user_id} with direct input (Streamlit mode)")
            normalized_user_skills = normalize_skill_list(user_skills)  # FIX 5 + FIX 6 + FIX 17
            
            # Normalize target_roles to list
            if isinstance(target_roles, str):
                normalized_target_roles = [target_roles]
            elif isinstance(target_roles, (list, tuple)):
                normalized_target_roles = list(target_roles)
            else:
                normalized_target_roles = [str(target_roles)]
            
            profile = {
                "user_id": user_id,
                "user_skills": normalized_user_skills,  # FIX 17: Now dict {skill: proficiency}
                "target_roles": normalized_target_roles,
                "budget": budget,
                "weekly_hours": weekly_hours,
                "modality": modality
            }
        else:
            # Database loading mode (original behavior)
            print(f"🎯 Processing user {user_id} via database profile")
            profile = load_user_profile(user_id)
            normalized_user_skills = profile["user_skills"]  # FIX 17: Already dict from load_user_profile
            normalized_target_roles = profile["target_roles"]
        
        # Validate that we have data to work with
        if not normalized_target_roles:
            print(f"⚠️ No target roles specified for {user_id}, skipping...")
            return {
                "user_id": user_id,
                "success": False,
                "error": "No target roles specified",
                "duration": time.time() - user_start
            }
        
        print(f"\n{'='*70}")
        print(f"🎯 User: {user_id}")
        print(f"   Analyzing {len(normalized_target_roles)} target roles: {', '.join(normalized_target_roles)}")
        
        # FIX 17: Handle dict format for printing
        if isinstance(normalized_user_skills, dict):
            skills_display = ', '.join([f"{s} ({p})" for s, p in normalized_user_skills.items()]) if normalized_user_skills else '(none specified)'
        else:
            # Fallback for backward compatibility
            skills_display = ', '.join(normalized_user_skills) if normalized_user_skills else '(none specified)'
        print(f"   User Skills: {skills_display}")
        print(f"{'='*70}")

        all_role_results = []
        all_removed_gaps = []  # Track all skills that were filtered across all roles
        
        # Process each target role
        for role_idx, target_role in enumerate(normalized_target_roles, 1):
            print(f"\n{'─'*70}")
            print(f"📊 ROLE {role_idx}/{len(normalized_target_roles)}: {target_role}")
            print(f"{'─'*70}")
            
            # Step 1: Load Knowledge Graph output for this role (with semantic matching)
            kg_df = load_kg_output_for_role(target_role)
            
            if len(kg_df) == 0:
                print(f"⚠️ No skills found for {target_role}, skipping...")
                continue
            
            # Step 2: Convert KG output to demand scores
            role_required_skills, jd_demand_db = load_jd_demand_scores(target_role, kg_df)
            
            # Step 3: Load peer data (FIX 4: Course loading REMOVED)
            peer_data, peer_counts = load_peer_data(target_role)
            # NOTE: load_course_skills_map() call REMOVED - Recommender handles this
            
            # Step 4: Build knowledge graph structure
            kg = build_knowledge_graph(target_role, kg_df)

            # FIX 8: Compute stable top 5 FIRST (user-independent, based on role requirements only)
            top_5_skills = compute_stable_top5(role_required_skills, jd_demand_db, peer_data)

            # Step 5: Identify gaps with partial credit (Tweak 1) - FIX 17: accepts dict
            gaps_dict = find_skill_gaps(normalized_user_skills, target_role, kg, full_match_threshold=0.80)

            # Step 6: Arbitrate (Tweak 2) - FIX 17: accepts dict
            prioritised = arbitrate_skill_gaps(gaps_dict, normalized_user_skills, kg, jd_demand_db, role_required_skills, peer_data)

            # Step 7: FIX 2 + FIX 18 - Filter user-declared skills with proficiency awareness
            filter_result = filter_user_declared_skills(
                prioritised, 
                normalized_user_skills,  # FIX 17: Now dict {skill: proficiency}
                similarity_threshold=USER_SKILL_FILTER_THRESHOLD
            )
            
            filtered_gaps = filter_result['filtered_gaps']
            removed_gaps = filter_result['removed_gaps']
            filter_metadata = filter_result['filter_metadata']
            
            # Collect removed gaps for persistence tracking
            all_removed_gaps.extend([g['skill'] for g in removed_gaps])
            
            # Step 8: Generate JSON Object (pass stable top5)
            final_json = build_json_output(
                target_role, 
                filtered_gaps, 
                filter_metadata,
                removed_gaps,
                top_5_skills  # FIX 8: Stable top5 (user-independent)
            )
            all_role_results.append(final_json)
            
            # Print top 5 skills for this role
            print(f"✅ Found {len(filtered_gaps)} skill gaps for {target_role} (after proficiency-aware filtering)")
            print(f"   🎯 Top 5 skills for {target_role}: {', '.join(top_5_skills)}")
            if removed_gaps:
                print(f"   🔒 Filtered {len(removed_gaps)} Advanced/Expert skills: {', '.join([g['skill'] for g in removed_gaps])}")
            
            # Step 9: Write to Delta immediately (incremental logging)
            write_single_role_to_delta(user_id, final_json)

        # FIX 2B: Persist user skills to prevent cycling (only in database mode)
        if normalized_user_skills and user_skills is None:
            # Only persist if we loaded from database (not direct input)
            update_success = update_user_profile_skills(user_id, normalized_user_skills)
            if update_success:
                print(f"\n✅ User skills persisted to database (prevents cycling)")
            else:
                print(f"\n⚠️ Could not persist user skills - cycling may occur on next call")

        # Calculate summary stats
        total_gaps = sum(len(r['skill_gaps']['gaps']) for r in all_role_results)
        duration = time.time() - user_start
        
        print(f"\n{'='*70}")
        print(f"✅ User {user_id} complete in {duration:.1f}s")
        print(f"   Roles analyzed: {len(all_role_results)}")
        print(f"   Total skill gaps: {total_gaps}")
        print(f"   Total filtered skills: {len(set(all_removed_gaps))}")
        print(f"   ℹ️  Course recommendations will be handled by Recommender module")
        print(f"{'='*70}")
        
        return {
            "user_id": user_id,
            "success": True,
            "total_roles": len(all_role_results),
            "total_gaps": total_gaps,
            "duration": duration,
            "all_role_results": all_role_results  # FIX 6: Return full results for Streamlit app
        }
        
    except Exception as e:
        print(f"\n❌ Error processing user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "user_id": user_id,
            "success": False,
            "error": str(e),
            "duration": time.time() - user_start
        }


if __name__ == "__main__":
    pipeline_start = time.time()
    
    print(f"\n{'#'*70}")
    print(f"# MULTI-USER SKILL GAP ANALYSIS")
    print(f"# Processing {len(USER_IDS)} users: {', '.join(USER_IDS)}")
    print(f"# FIX 4: Course discovery delegated to Recommender module")
    print(f"# FIX 5: Robust skill format normalization applied")
    print(f"# FIX 6: Direct input support for Streamlit apps")
    print(f"# FIX 7: Defensive embedding function (any input type)")
    print(f"# FIX 8: Top 5 stability fix (user-independent scoring)")
    print(f"# FIX 17: Proficiency-aware skill normalization")
    print(f"# FIX 18: Graduated skill filtering (Beginner kept, Advanced removed)")
    print(f"{'#'*70}\n")
    
    # Process each user
    results = []
    for user_idx, user_id in enumerate(USER_IDS, 1):
        print(f"\n\n{'█'*70}")
        print(f"█ USER {user_idx}/{len(USER_IDS)}: {user_id}")
        print(f"{'█'*70}")
        
        result = process_single_user(user_id)
        results.append(result)
    
    # Final summary across all users
    pipeline_duration = time.time() - pipeline_start
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\n\n{'#'*70}")
    print(f"# PIPELINE COMPLETE")
    print(f"{'#'*70}")
    print(f"⏱️  Total Duration: {pipeline_duration:.1f}s")
    print(f"✅ Successful: {len(successful)}/{len(USER_IDS)} users")
    
    if successful:
        total_roles = sum(r['total_roles'] for r in successful)
        total_gaps = sum(r['total_gaps'] for r in successful)
        print(f"📊 Total Roles Analyzed: {total_roles}")
        print(f"📊 Total Skill Gaps Found: {total_gaps}")
        print(f"💾 Results saved to: {OUTPUT_SCHEMA}.user_analysis_log")
        print(f"ℹ️  Course recommendations: Pass gaps to Recommender module")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)} users")
        for f in failed:
            print(f"   • {f['user_id']}: {f.get('error', 'Unknown error')}")
    
    print(f"{'#'*70}\n")