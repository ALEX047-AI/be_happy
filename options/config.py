from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    API_KEY: str
    BASE_URL: str


    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra fields


settings = Settings()