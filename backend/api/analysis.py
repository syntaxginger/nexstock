from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database import get_db
from backend.services import news_service, technical_service
from backend.models.portfolio import Currency
from backend.services.portfolio_service import get_all_positions

router = APIRouter(prefix="/analysis", tags=["analysis"])

CURRENCY_SYMBOL_MAP = {
    Currency.USD: "$",
    Currency.HKD: "HK$",
    Currency.THB: "฿",
}


@router.get("/news/{ticker}", summary="ดึงข่าวและสรุป AI สำหรับหุ้นตัวนั้น")
async def ticker_news(ticker: str):
    articles = news_service.fetch_ticker_news(ticker.upper())
    summary = news_service.summarize_news_for_ticker(ticker.upper(), articles)
    return {
        "ticker": ticker.upper(),
        "articles": articles,
        "ai_summary": summary,
    }


@router.get("/news/portfolio/all", summary="สรุปข่าวทุกตัวในพอร์ต")
async def portfolio_news(db: AsyncSession = Depends(get_db)):
    positions = await get_all_positions(db)
    tickers = list({p.ticker for p in positions})
    return news_service.analyze_portfolio_news(tickers)


@router.get("/market-overview", summary="ภาพรวมตลาดโลกวันนี้")
async def market_overview():
    overview = news_service.get_market_overview()
    return {"overview": overview}


@router.get("/technical/{ticker}", summary="Technical Analysis สำหรับหุ้นตัวนั้น")
async def technical_analysis(
    ticker: str,
    currency_symbol: str = Query(default="$", description="สัญลักษณ์เงิน เช่น $, HK$, ฿"),
):
    result = technical_service.analyze_ticker(ticker.upper(), currency_symbol=currency_symbol)
    if not result:
        return {"error": f"ไม่สามารถดึงข้อมูล {ticker} ได้"}
    return result


@router.get("/technical/portfolio/all", summary="Technical Analysis ทุกตัวในพอร์ต")
async def portfolio_technical(db: AsyncSession = Depends(get_db)):
    positions = await get_all_positions(db)
    results = []
    for pos in positions:
        symbol = CURRENCY_SYMBOL_MAP.get(pos.currency, "$")
        result = technical_service.analyze_ticker(pos.ticker, currency_symbol=symbol)
        if result:
            results.append(result)
    return results
