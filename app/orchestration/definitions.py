from __future__ import annotations

from datetime import date

from dagster import (
    DailyPartitionsDefinition,
    Definitions,
    asset,
    build_schedule_from_partitioned_job,
    define_asset_job,
    resource,
)
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.etl.daily import run_daily_etl

settings = get_settings()


@resource
def source_db_resource(_context):
    return create_engine(settings.source_db_url, future=True)


@resource
def target_db_resource(_context):
    return create_engine(settings.target_db_url, future=True)


daily_partitions = DailyPartitionsDefinition(
    start_date="2026-01-01",
    timezone="UTC",
    end_offset=1,
)


@asset(
    partitions_def=daily_partitions,
    required_resource_keys={"source_db", "target_db"},
    group_name="etl",
)
def daily_iot_etl(context) -> int:
    process_date = date.fromisoformat(context.partition_key)

    with context.resources.source_db.connect() as source_conn:
        source_conn.execute(text("SELECT 1"))
    with context.resources.target_db.connect() as target_conn:
        target_conn.execute(text("SELECT 1"))

    loaded_rows = run_daily_etl(
        process_date=process_date,
        source_api_url=settings.source_api_url,
        target_db_url=settings.target_db_url,
    )
    context.log.info("Loaded %s rows for partition %s", loaded_rows, context.partition_key)
    return loaded_rows


daily_iot_etl_job = define_asset_job(
    name="daily_iot_etl_job",
    selection=[daily_iot_etl],
    partitions_def=daily_partitions,
)


daily_iot_etl_schedule = build_schedule_from_partitioned_job(
    daily_iot_etl_job,
    hour_of_day=1,
    minute_of_hour=5,
)


defs = Definitions(
    assets=[daily_iot_etl],
    jobs=[daily_iot_etl_job],
    schedules=[daily_iot_etl_schedule],
    resources={
        "source_db": source_db_resource,
        "target_db": target_db_resource,
    },
)
