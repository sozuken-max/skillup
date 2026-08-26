"""
config.py — Centralized configuration management for SkillUP.
"""

import os
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class AppConfig:
    """Application-wide configuration."""
    # LLM Configuration
    llm_model: str = "gpt-3.5-turbo"
    max_history_turns: int = 16
    openai_api_key: Optional[str] = None

    # Neo4j Configuration
    neo4j_url: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None
    neo4j_database: str = "neo4j"

    # Databricks Configuration
    databricks_host: Optional[str] = None
    databricks_client_id: Optional[str] = None
    databricks_client_secret: Optional[str] = None

    # Data paths
    data_dir: str = "data"
    user_profiles_csv: str = "data/user_profiles.csv"
    knowledge_graph_csv: str = "data/knowledge_graph.csv"
    courses_csv: str = "data/skillsfuture_courses.csv"

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Load configuration from environment variables."""
        return cls(
            llm_model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            max_history_turns=int(os.getenv("MAX_HISTORY_TURNS", "16")),
            openai_api_key=os.getenv("OPENAI_API_KEY"),

            neo4j_url=os.getenv("NEO4J_URL"),
            neo4j_user=os.getenv("NEO4J_USER"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),

            databricks_host=os.getenv("DATABRICKS_HOST"),
            databricks_client_id=os.getenv("DATABRICKS_CLIENT_ID"),
            databricks_client_secret=os.getenv("DATABRICKS_CLIENT_SECRET"),
        )

# Global config instance
config = AppConfig.from_env()