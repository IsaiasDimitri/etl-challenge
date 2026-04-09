from datetime import datetime

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SourceBase(DeclarativeBase):
    pass


class SourceData(SourceBase):
    __tablename__ = "data"

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    power: Mapped[float] = mapped_column(Float, nullable=False)
    ambient_temprature: Mapped[float] = mapped_column(Float, nullable=False)
