import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "asda")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./pipeline_state.db")
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "6000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "500"))


settings = Settings()
