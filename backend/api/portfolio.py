from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from backend.database import get_db
from backend.models.portfolio import AssetType, Currency
from backend.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class AddPositionRequest(BaseModel):
    ticker: str = Field(..., examples=["GOOG"])
    name: str = Field(..., examples=["Alphabet Inc."])
    asset_type: AssetType
    currency: Currency
    quantity: float = Field(..., gt=0)
    avg_cost: float = Field(..., gt=0)
    bought_at: datetime
    fee: float = Field(default=0.0, ge=0)
    note: Optional[str] = None


@router.post("/positions", summary="เพิ่มหุ้น/กองทุนในพอร์ต")
async def add_position(body: AddPositionRequest, db: AsyncSession = Depends(get_db)):
    position = await portfolio_service.add_position(
        db,
        ticker=body.ticker,
        name=body.name,
        asset_type=body.asset_type,
        currency=body.currency,
        quantity=body.quantity,
        avg_cost=body.avg_cost,
        bought_at=body.bought_at,
        fee=body.fee,
        note=body.note,
    )
    return {"message": "เพิ่มสำเร็จ", "id": position.id, "ticker": position.ticker}


@router.get("/positions", summary="ดูรายการพอร์ตทั้งหมด")
async def list_positions(db: AsyncSession = Depends(get_db)):
    positions = await portfolio_service.get_all_positions(db)
    return [
        {
            "id": p.id,
            "ticker": p.ticker,
            "name": p.name,
            "asset_type": p.asset_type,
            "currency": p.currency,
            "quantity": p.quantity,
            "avg_cost": p.avg_cost,
            "fee": p.fee,
            "bought_at": p.bought_at,
            "note": p.note,
        }
        for p in positions
    ]


@router.delete("/positions/{position_id}", summary="ลบหุ้น/กองทุนออกจากพอร์ต")
async def delete_position(position_id: int, db: AsyncSession = Depends(get_db)):
    ok = await portfolio_service.delete_position(db, position_id)
    if not ok:
        raise HTTPException(status_code=404, detail="ไม่พบ position นี้")
    return {"message": "ลบสำเร็จ"}


@router.get("/summary", summary="ภาพรวมพอร์ต + P&L แต่ละตัว")
async def portfolio_summary(db: AsyncSession = Depends(get_db)):
    return await portfolio_service.get_portfolio_summary(db)
