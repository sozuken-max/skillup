"""
Course Catalog Module
=====================

Handles course loading from Delta table and semantic search for course discovery.
Provides both TF-IDF baseline and placeholder for Databricks embeddings.
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import List, Optional, Dict
from .models import Course, SkillGap

# ── INTEGRATION ───────────────────────────────────────────────────────────────
from skillgap.skillgap import execute_sql_query, COURSE_TABLE

logger = logging.getLogger(__name__)

# ── ENVIRONMENT DETECTION ─────────────────────────────────────────────────────
try:
    import dbutils # type: ignore
    IN_DATABRICKS = True
except (ImportError, NameError):
    IN_DATABRICKS = False


class CourseCatalog:
    """
    Course catalog manager that loads and caches courses from Delta table.
    Handles semantic search using TF-IDF or embeddings.
    """
    
    def __init__(self, table_name: str = "workspace.default.my_skills_future_course_directory", csv_path: str = "data/skillsfuture_courses.csv"):
        """
        Initialize catalog with Delta table name or local CSV path.
        
        Args:
            table_name: Fully qualified Delta table name
            csv_path: Path to local CSV fallback
        """
        self.table_name = table_name
        self.csv_path = csv_path
        self._courses: Optional[List[Course]] = None
        self._df_local: Optional[pd.DataFrame] = None
        self._embeddings_cache: Optional[Dict[str, np.ndarray]] = None
        
    def load_all_courses(self) -> List[Course]:
        """
        Load all courses with environment-aware fallback.
        In Databricks: Loads from Delta table (optimized with limit/filtering if needed).
        Locally: Loads from CSV file.
        
        Returns:
            List of Course objects
        """
        if self._courses is not None:
            logger.debug(f"Using cached courses ({len(self._courses)} courses)")
            return self._courses

        if IN_DATABRICKS:
            try:
                query = f"SELECT * FROM {self.table_name}"
                df_pandas = execute_sql_query(query)
                self._courses = [self._load_course_from_pandas_row(row) for _, row in df_pandas.iterrows()]
                logger.info(f"Successfully loaded {len(self._courses)} courses from {self.table_name} using execute_sql_query")
                return self._courses
            except Exception as e:
                logger.warning(f"Failed to load via execute_sql_query: {e}. Falling back to CSV.")
            
            return self._load_from_csv()
        else:
            return self._load_from_csv()

    def _get_delta_df(self):
        """Get the Spark DataFrame for the Delta table."""
        try:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()
            return spark.table(self.table_name)
        except (ImportError, Exception) as e:
            logger.debug(f"Could not get Spark table {self.table_name}: {e}")
            return None

    def _load_from_delta(self) -> List[Course]:
        """Deprecated: Use load_all_courses or semantic_search instead."""
        return self.load_all_courses()

    def _load_from_csv(self) -> List[Course]:
        """Load courses from local CSV file."""
        if not os.path.exists(self.csv_path):
            logger.error(f"CSV file not found: {self.csv_path}")
            return []
            
        try:
            logger.info(f"Loading courses from local CSV: {self.csv_path}")
            df = pd.read_csv(self.csv_path)
            
            # Map CSV columns to Course object fields
            # Handle potential column name differences between Delta and CSV
            self._courses = []
            for _, row in df.iterrows():
                # Simple mapping for local dev CSV
                self._courses.append(self._load_course_from_pandas_row(row))
                
            logger.info(f"Successfully loaded {len(self._courses)} courses from {self.csv_path}")
            return self._courses
        except Exception as e:
            logger.error(f"Failed to load courses from CSV: {e}")
            return []

    def _load_course_from_pandas_row(self, row: pd.Series) -> Course:
        """Map pandas Series to Course object."""
        # Use .get() if available (for dict-like Series) or standard indexing
        row_dict = row.to_dict()
        
        return Course(
            course_id=str(row_dict.get("coursereferencenumber", row_dict.get("course_id", ""))),
            title=row_dict.get("coursetitle", row_dict.get("title", "Untitled Course")),
            provider=row_dict.get("trainingprovideralias", row_dict.get("provider", "Unknown Provider")),
            provider_uen=row_dict.get("trainingprovideruen"),
            rating=float(row_dict.get("courseratings_stars") or 0.0),
            rating_value=row_dict.get("courseratings_value"),
            rating_respondents=int(row_dict.get("courseratings_noofrespondents") or 0),
            cost=float(row_dict.get("full_course_fee", row_dict.get("cost", 0.0)) or 0.0),
            cost_after_subsidy=float(row_dict.get("course_fee_after_subsidies", row_dict.get("cost_after_subsidy", 0.0)) or 0.0),
            total_hours=float(row_dict.get("number_of_hours", row_dict.get("total_hours", 0.0)) or 0.0),
            description=row_dict.get("about_this_course", row_dict.get("description")),
            skills_covered=row_dict.get("what_you_learn", row_dict.get("skills_covered")),
            modality=self._infer_modality(row_dict),
            schedule=self._infer_schedule(row_dict),
            skillsfuture_eligible=True
        )
    
    def semantic_search(
        self,
        skill_gaps: List[SkillGap],
        top_k: int = 100,
        use_databricks_embeddings: bool = False
    ) -> List[Course]:
        """
        Find courses relevant to skill gaps using semantic similarity.
        Optimized for Databricks to avoid pulling full catalog into memory.
        """
        if not skill_gaps:
            logger.warning("No skill gaps provided for semantic search")
            return self.load_all_courses()[:top_k]

        # Create query from skill gaps
        query_parts = [gap.skill for gap in skill_gaps]
        query_text = " ".join(query_parts)
        
        if IN_DATABRICKS and not use_databricks_embeddings:
            # Optimized Spark-based filtering
            return self._semantic_search_sql(skill_gaps, top_k)

        if not IN_DATABRICKS:
            # Optimized local CSV-based filtering
            return self._semantic_search_local_csv(skill_gaps, top_k)

        all_courses = self.load_all_courses()
        
        if use_databricks_embeddings:
            try:
                return self._semantic_search_databricks(query_text, all_courses, top_k)
            except Exception as e:
                logger.warning(f"Databricks embeddings failed: {e}. Falling back to TF-IDF")
        
        return self._semantic_search_tfidf(query_text, all_courses, top_k)

    def _semantic_search_sql(self, skill_gaps: List[SkillGap], top_k: int) -> List[Course]:
        """
        Perform filtering and discovery at the database level.
        Uses keyword matching against course titles and descriptions.
        """
        # Ensure USE_SQL_CONNECTOR is defined (imported from skillgap)
        try:
            from skillgap.skillgap import USE_SQL_CONNECTOR
        except ImportError:
            USE_SQL_CONNECTOR = False

        try:
            # Build a dynamic SQL query for keywords
            conditions = []
            for gap in skill_gaps:
                skill_cleaned = gap.skill.replace("'", "''")
                # SQL-based case-insensitive match
                cond = f"(coursetitle RLIKE '(?i){skill_cleaned}' OR what_you_learn RLIKE '(?i){skill_cleaned}' OR about_this_course RLIKE '(?i){skill_cleaned}')"
                conditions.append(cond)

            where_clause = " OR ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT * 
                FROM {self.table_name} 
                WHERE {where_clause} 
                LIMIT {top_k * 2}
            """
            
            df_pandas = execute_sql_query(query)
            courses = [self._load_course_from_pandas_row(row) for _, row in df_pandas.iterrows()]
            
            logger.info(f"SQL-based filtering returned {len(courses)} candidates")
            
            if not courses:
                # If no matches, fall back to a small subset of the catalog
                logger.warning("No SQL keyword matches found, falling back to top of catalog")
                fallback_query = f"SELECT * FROM {self.table_name} LIMIT {top_k}"
                df_fallback = execute_sql_query(fallback_query)
                return [self._load_course_from_pandas_row(row) for _, row in df_fallback.iterrows()]

            # Further rank with TF-IDF for quality
            query_parts = []
            for gap in skill_gaps:
                weight = int(gap.priority * 5) + 1
                query_parts.extend([gap.skill] * weight)
            query_text = " ".join(query_parts)
            
            return self._semantic_search_tfidf(query_text, courses, top_k)

        except Exception as e:
            logger.error(f"SQL-based semantic search failed: {e}")
            return self._semantic_search_local_csv(skill_gaps, top_k)

    def _semantic_search_local_csv(self, skill_gaps: List[SkillGap], top_k: int) -> List[Course]:
        """
        Perform keyword-based filtering on local CSV using pandas before creating Course objects.
        """
        if not os.path.exists(self.csv_path):
            logger.error(f"CSV file not found: {self.csv_path}")
            return []

        try:
            if self._df_local is None:
                logger.info(f"Loading CSV for semantic search: {self.csv_path}")
                self._df_local = pd.read_csv(self.csv_path)
            
            df = self._df_local
            
            # Use same keyword columns as Spark: 'coursetitle', 'what_you_learn', 'about_this_course'
            # Note: local CSV might use fallback names (handled in _load_course_from_pandas_row)
            title_col = "coursetitle" if "coursetitle" in df.columns else "title"
            skills_col = "what_you_learn" if "what_you_learn" in df.columns else "skills_covered"
            desc_col = "about_this_course" if "about_this_course" in df.columns else "description"
            
            # Check if at least title column exists
            if title_col not in df.columns:
                logger.warning(f"Could not find title column in CSV. Available: {df.columns.tolist()}")
                return self._semantic_search_tfidf(" ".join([g.skill for g in skill_gaps]), self.load_all_courses(), top_k)

            mask = pd.Series([False] * len(df))
            for gap in skill_gaps:
                skill = gap.skill.lower()
                # Check for skill in title, skills_covered, or description
                m = (df[title_col].str.contains(skill, case=False, na=False)) | \
                    (df[skills_col].str.contains(skill, case=False, na=False)) | \
                    (df[desc_col].str.contains(skill, case=False, na=False))
                mask = mask | m
            
            df_filtered = df[mask]
            
            if df_filtered.empty:
                logger.warning("No keyword matches found in local CSV, returning top courses")
                candidate_rows = df.head(top_k)
            else:
                # Limit candidates to a reasonable number
                candidate_rows = df_filtered.head(top_k * 2)
            
            courses = [self._load_course_from_pandas_row(row) for _, row in candidate_rows.iterrows()]
            logger.info(f"Local CSV filtering returned {len(courses)} candidates")
            
            # Further rank with TF-IDF for quality
            query_parts = []
            for gap in skill_gaps:
                weight = int(gap.priority * 5) + 1
                query_parts.extend([gap.skill] * weight)
            query_text = " ".join(query_parts)
            
            return self._semantic_search_tfidf(query_text, courses, top_k)
            
        except Exception as e:
            logger.error(f"Local CSV semantic search failed: {e}")
            # Fallback to loading all (legacy behavior)
            return self._semantic_search_tfidf(" ".join([g.skill for g in skill_gaps]), self.load_all_courses(), top_k)
    
    def _semantic_search_databricks(
        self,
        query_text: str,
        courses: List[Course],
        top_k: int
    ) -> List[Course]:
        """
        Semantic search using Databricks Foundation Model API (BGE embeddings).
        
        TODO: Implement when Databricks embedding endpoint is available.
        For now, raises NotImplementedError to trigger fallback.
        """
        raise NotImplementedError("Databricks embeddings not yet implemented")
    
    def _semantic_search_tfidf(
        self,
        query_text: str,
        courses: List[Course],
        top_k: int
    ) -> List[Course]:
        """
        Semantic search using TF-IDF as fallback.
        Simple but effective baseline.
        """
        if not courses:
            return []

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            logger.error("scikit-learn not available. Cannot perform TF-IDF search.")
            return courses[:top_k]
        
        # Prepare corpus
        corpus = [course.get_searchable_text() for course in courses]
        corpus.append(query_text)  # Add query as last document
        
        # Calculate TF-IDF
        vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1
        )
        
        tfidf_matrix = vectorizer.fit_transform(corpus)
        
        # Query is last row
        query_vector = tfidf_matrix[-1]
        course_vectors = tfidf_matrix[:-1]
        
        # Calculate cosine similarity
        similarities = cosine_similarity(query_vector, course_vectors)[0]
        
        # Rank courses by similarity
        num_courses = len(courses)
        ranked_indices = np.argsort(similarities)[::-1][:min(top_k, num_courses)]
        ranked_courses = [courses[i] for i in ranked_indices]
        
        if len(ranked_indices) > 0:
            # Safely slice to avoid index errors in tests with few courses
            log_limit = min(5, len(ranked_indices))
            logger.debug(f"Top {log_limit} similarity scores: {similarities[ranked_indices[:log_limit]]}")
        
        return ranked_courses
    
    def _load_course_from_row(self, row) -> Course:
        """
        Create a Course object from a Delta table row (PySpark Row).
        
        Handles optional fields gracefully using row.asDict().get()
        """
        row_dict = row.asDict()
        
        return Course(
            course_id=row_dict.get("coursereferencenumber", ""),
            title=row_dict.get("coursetitle", "Untitled Course"),
            provider=row_dict.get("trainingprovideralias", "Unknown Provider"),
            provider_uen=row_dict.get("trainingprovideruen"),
            rating=float(row_dict.get("courseratings_stars") or 0.0),
            rating_value=row_dict.get("courseratings_value"),
            rating_respondents=int(row_dict.get("courseratings_noofrespondents") or 0),
            career_impact_stars=row_dict.get("jobcareer_impact_stars"),
            career_impact_value=row_dict.get("jobcareer_impact_value"),
            career_impact_respondents=row_dict.get("jobcareer_impact_noofrespondents"),
            enrollment_count=int(row_dict.get("attendancecount") or 0),
            cost=float(row_dict.get("full_course_fee") or 0.0),
            cost_after_subsidy=float(row_dict.get("course_fee_after_subsidies") or 0.0),
            total_hours=float(row_dict.get("number_of_hours") or 0.0),
            training_commitment=row_dict.get("training_commitment"),
            conducted_in=row_dict.get("conducted_in"),
            description=row_dict.get("about_this_course"),
            skills_covered=row_dict.get("what_you_learn"),
            prerequisites=row_dict.get("minimum_entry_requirement"),
            modality=self._infer_modality(row_dict),
            schedule=self._infer_schedule(row_dict),
            skillsfuture_eligible=True  # Assume true for courses in catalog
        )
    
    def _infer_modality(self, row_dict: dict) -> Optional[str]:
        """Infer modality from training commitment or conducted_in field"""
        commitment = (row_dict.get("training_commitment") or "").lower()
        location = (row_dict.get("conducted_in") or "").lower()
        
        if "online" in commitment or "online" in location:
            return "online"
        elif "onsite" in commitment or "onsite" in location or "classroom" in location:
            return "onsite"
        elif "blended" in commitment or "hybrid" in commitment:
            return "blended"
        else:
            return "flexible"
    
    def _infer_schedule(self, row_dict: dict) -> Optional[str]:
        """Infer schedule from training commitment field"""
        commitment = (row_dict.get("training_commitment") or "").lower()
        
        if "weekend" in commitment or "weekends" in commitment:
            return "weekend"
        elif "weekday" in commitment or "weekdays" in commitment:
            return "weekday"
        elif "evening" in commitment:
            return "evening"
        else:
            return "flexible"
