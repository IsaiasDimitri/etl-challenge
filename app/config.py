from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    source_db_url: str
    target_db_url: str
    source_api_url: str
    dagster_home: str


def get_settings() -> Settings:
    return Settings(
        source_db_url=os.getenv(
            "SOURCE_DB_URL",
            "postgresql+psycopg2://iot:iot@db_source:5432/source_db",
        ),
        target_db_url=os.getenv(
            "TARGET_DB_URL",
            "postgresql+psycopg2://etl:etl@db_target:5432/target_db",
        ),
        source_api_url=os.getenv("SOURCE_API_URL", "http://api:8000"),
        dagster_home=os.getenv("DAGSTER_HOME", "/opt/dagster/dagster_home"),
    )
