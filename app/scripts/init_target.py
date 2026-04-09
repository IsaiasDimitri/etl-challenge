from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import target_engine
from app.models.target import Signal, TargetBase

DEFAULT_SIGNALS = [
    "wind_speed_mean",
    "wind_speed_min",
    "wind_speed_max",
    "wind_speed_std",
    "power_mean",
    "power_min",
    "power_max",
    "power_std",
]


def main() -> None:
    TargetBase.metadata.create_all(bind=target_engine)

    with Session(target_engine) as session:
        existing = session.execute(select(Signal.name)).scalars().all()
        existing_set = set(existing)
        missing = [name for name in DEFAULT_SIGNALS if name not in existing_set]
        if missing:
            session.add_all([Signal(name=name) for name in missing])
            session.commit()


if __name__ == "__main__":
    main()
