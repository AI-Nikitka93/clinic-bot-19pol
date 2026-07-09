from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/clinic_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    BOT_TOKEN: str = "test_token"
    WEBHOOK_URL: str = ""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v):
        if v and isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    class Config:
        env_file = ".env"

settings = Settings()
