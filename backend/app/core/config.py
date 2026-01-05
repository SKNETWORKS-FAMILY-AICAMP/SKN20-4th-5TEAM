from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os


class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str
    
    # Server Settings
    FASTAPI_HOST: str = "localhost"
    FASTAPI_PORT: int = 8001
    
    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent
    CHROMA_DB_PATH: str = "./chroma_db"
    DATA_PATH: str = "./data"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    
    # Environment
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()