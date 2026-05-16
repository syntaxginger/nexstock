from sqlalchemy import String, Float, Integer, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
import enum

from backend.database import Base


class AssetType(str, enum.Enum):
    US_STOCK = "US_STOCK"
    HK_STOCK = "HK_STOCK"
    TH_FUND = "TH_FUND"


class Currency(str, enum.Enum):
    USD = "USD"
    HKD = "HKD"
    THB = "THB"


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(SAEnum(AssetType), nullable=False)
    currency: Mapped[Currency] = mapped_column(SAEnum(Currency), nullable=False)

    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.0)

    bought_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
