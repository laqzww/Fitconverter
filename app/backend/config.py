from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_db: str = "gis"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    redis_url: str = "redis://localhost:6379/0"
    api_port: int = 8000
    frontend_port: int = 5173
    tileserver_port: int = 7800
    gpx_output_dir: str = "out"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
