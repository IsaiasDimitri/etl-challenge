from __future__ import annotations

from datetime import datetime, timezone
import argparse

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.db import source_engine
from app.models.source import SourceBase


def build_dataset(days: int, seed: int) -> pd.DataFrame:
    periods = days * 24 * 60
    end_dt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    timestamps = pd.date_range(end=end_dt, periods=periods, freq="min", tz="UTC")

    rng = np.random.default_rng(seed)
    wind_speed = np.clip(rng.normal(loc=8.0, scale=2.5, size=periods), 0.0, None)
    power = np.clip(wind_speed * 12 + rng.normal(loc=0.0, scale=6.0, size=periods), 0.0, None)
    ambient_temprature = rng.normal(loc=24.0, scale=4.0, size=periods)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "wind_speed": wind_speed,
            "power": power,
            "ambient_temprature": ambient_temprature,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap source data with 10 days of 1-minute samples")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    SourceBase.metadata.create_all(bind=source_engine)
    dataset = build_dataset(days=args.days, seed=args.seed)

    with source_engine.begin() as connection:
        connection.execute(text('TRUNCATE TABLE "data"'))

    dataset.to_sql(
        "data",
        con=source_engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=2000,
    )

    print(f"Inserted {len(dataset)} rows into source.data")


if __name__ == "__main__":
    main()
