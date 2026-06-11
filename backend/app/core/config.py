from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://archaeologai:archaeologai_secret@localhost:5432/archaeologai"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_secret"
    github_token: str = "your_github_token_here"
    gemini_api_key: str = "your_gemini_key_here"
    openai_api_key: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    llm_provider: str = "gemini"
    qdrant_collection_name: str = "artifacts"
    vector_dim: int = 384
    retrieval_top_k: int = 10
    graph_expansion_depth: int = 2
    final_top_k: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
