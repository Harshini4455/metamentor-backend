"""Application configuration — reads from .env"""
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "MetaMentor AI Workspace"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://metamentor:metamentor@localhost:5432/metamentor"

    # Redis (for pub/sub & task queue)
    REDIS_URL: str = "redis://localhost:6379"

    # AI
    GOOGLE_API_KEY: str = ""          # Gemini 2.5
    OPENAI_API_KEY: str = ""          # fallback

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION: str = "metamentor_kb"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # JWT
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
