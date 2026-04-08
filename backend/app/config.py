from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str

    # App
    upload_dir: str = "uploads"
    max_file_size_mb: int = 50
    session_ttl_seconds: int = 3600

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Ensure upload dir exists
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)