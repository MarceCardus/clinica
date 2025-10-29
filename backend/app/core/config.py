from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = Field(default="BetMVP")
    api_port: int = Field(default=8000)
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_minutes: int = Field(default=60 * 24)
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool = Field(default=False)
    rate_limit: str = Field(default="50/minute")
    max_daily_topup: float = Field(default=5000.0)
    max_daily_stake: float = Field(default=1000.0)
    admin_email: str = Field(default="admin@example.com")
    admin_password: str = Field(default="ChangeMe123!")
    seed_company: str = Field(default="Empresa XYZ")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
