from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timezone
from typing import Optional
import yfinance as yf

from backend.models.portfolio import Position, DailySnapshot, AssetType, Currency


CURRENCY_SYMBOL = {
    Currency.USD: "$",
    Currency.HKD: "HK$",
    Currency.THB: "฿",
}


async def add_position(
    db: AsyncSession,
    ticker: str,
    name: str,
    asset_type: AssetType,
    currency: Currency,
    quantity: float,
    avg_cost: float,
    bought_at: datetime,
    fee: float = 0.0,
    note: Optional[str] = None,
) -> Position:
    position = Position(
        ticker=ticker.upper(),
        name=name,
        asset_type=asset_type,
        currency=currency,
        quantity=quantity,
        avg_cost=avg_cost,
        fee=fee,
        bought_at=bought_at,
        note=note,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position


async def get_all_positions(db: AsyncSession) -> list[Position]:
    result = await db.execute(select(Position).order_by(Position.ticker))
    return list(result.scalars().all())


async def get_position(db: AsyncSession, position_id: int) -> Optional[Position]:
    result = await db.execute(select(Position).where(Position.id == position_id))
    return result.scalar_one_or_none()


async def delete_position(db: AsyncSession, position_id: int) -> bool:
    result = await db.execute(delete(Position).where(Position.id == position_id))
    await db.commit()
    return result.rowcount > 0


def fetch_current_price(ticker: str) -> Optional[float]:
    try:
        data = yf.Ticker(ticker)
        info = data.fast_info
        return float(info.last_price)
    except Exception:
        return None


def calculate_pnl(position: Position, current_price: float) -> dict:
    cost_basis = position.quantity * position.avg_cost + position.fee
    current_value = position.quantity * current_price
    pnl = current_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
    symbol = CURRENCY_SYMBOL.get(position.currency, "")
    return {
        "ticker": position.ticker,
        "name": position.name,
        "asset_type": position.asset_type,
        "currency": position.currency,
        "quantity": position.quantity,
        "avg_cost": position.avg_cost,
        "current_price": current_price,
        "cost_basis": round(cost_basis, 2),
        "current_value": round(current_value, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "currency_symbol": symbol,
        "pnl_str": f"{'+' if pnl >= 0 else ''}{symbol}{pnl:,.2f}",
        "pnl_pct_str": f"{'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%",
    }


async def get_portfolio_summary(db: AsyncSession) -> dict:
    positions = await get_all_positions(db)
    if not positions:
        return {"positions": [], "total_by_currency": {}, "total_positions": 0}

    enriched = []
    totals: dict[str, float] = {}

    for pos in positions:
        price = fetch_current_price(pos.ticker)
        if price is None:
            continue
        pnl_data = calculate_pnl(pos, price)
        enriched.append(pnl_data)
        cur = pos.currency.value
        totals[cur] = totals.get(cur, 0) + pnl_data["pnl"]

    return {
        "positions": enriched,
        "total_pnl_by_currency": {k: round(v, 2) for k, v in totals.items()},
        "total_positions": len(enriched),
    }


async def save_daily_snapshot(db: AsyncSession, ticker: str, price: float):
    snapshot = DailySnapshot(
        ticker=ticker.upper(),
        price=price,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    await db.commit()
