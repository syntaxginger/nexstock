"""
LINE Chatbot — คำสั่งทั้งหมด:

  📋 พอร์ต                  → ดู P&L ทุกตัว
  ➕ เพิ่ม AAPL              → ดูราคา + แนะนำวิธีเพิ่ม
  ➕ เพิ่ม AAPL 10 180       → เพิ่มหุ้น (ticker จำนวน ราคาทุน)
  🗑️ ลบ AAPL                → ลบออกจากพอร์ต
  💰 ราคา AAPL              → ดูราคาปัจจุบัน
  📰 ข่าว AAPL              → ข่าว + AI สรุป
  📊 เทคนิค AAPL            → RSI แนวรับ/แนวต้าน
  🌍 ตลาด                   → ภาพรวมตลาดโลก
  ❓ ช่วย                   → แสดงคำสั่งทั้งหมด
"""

import re
from datetime import datetime, timezone

import requests
import yfinance as yf
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.portfolio import AssetType, Currency
from backend.services import news_service, technical_service
from backend.services import portfolio_service

router = APIRouter(prefix="/webhook", tags=["LINE Chatbot"])
settings = get_settings()

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"


def _headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.line_channel_access_token}",
    }


def _reply(token: str, text: str):
    requests.post(LINE_REPLY_URL, json={
        "replyToken": token,
        "messages": [{"type": "text", "text": text[:4999]}],
    }, headers=_headers(), timeout=10)


def _fetch_stock_info(ticker: str) -> dict | None:
    """ดึงชื่อ ราคา และสกุลเงินจาก yfinance"""
    try:
        t = yf.Ticker(ticker)
        fast = t.fast_info
        price = round(float(fast.last_price), 4)
        currency_raw = getattr(fast, "currency", "USD")
        currency_map = {"USD": Currency.USD, "HKD": Currency.HKD, "THB": Currency.THB}
        currency = currency_map.get(currency_raw, Currency.USD)
        sym_map = {Currency.USD: "$", Currency.HKD: "HK$", Currency.THB: "฿"}
        symbol = sym_map[currency]

        info = t.info
        name = info.get("longName") or info.get("shortName") or ticker

        if ticker.endswith(".HK"):
            asset_type = AssetType.HK_STOCK
        elif currency == Currency.THB:
            asset_type = AssetType.TH_FUND
        else:
            asset_type = AssetType.US_STOCK

        return {
            "ticker": ticker,
            "name": name,
            "price": price,
            "currency": currency,
            "symbol": symbol,
            "asset_type": asset_type,
        }
    except Exception:
        return None


async def _handle_message(text: str) -> str:
    text = text.strip()
    lower = text.lower()

    # ─── พอร์ต ────────────────────────────────────────────────────────────────
    if lower in ["พอร์ต", "portfolio", "port"]:
        async with AsyncSessionLocal() as db:
            summary = await portfolio_service.get_portfolio_summary(db)

        if not summary["positions"]:
            return "💼 พอร์ตว่างอยู่ครับ\nพิมพ์ 'เพิ่ม AAPL' เพื่อเพิ่มหุ้น"

        lines = ["💼 สรุปพอร์ต\n"]
        for p in summary["positions"]:
            emoji = "🟢" if p["pnl"] >= 0 else "🔴"
            sym = p["currency_symbol"]
            lines.append(
                f"{emoji} {p['ticker']}\n"
                f"   ราคา {sym}{p['current_price']:,.2f} | {p['pnl_str']} ({p['pnl_pct_str']})"
            )

        pnl = summary.get("total_pnl_by_currency", {})
        if pnl:
            lines.append("\n── รวม ──")
            for cur, val in pnl.items():
                sym = {"USD": "$", "HKD": "HK$", "THB": "฿"}.get(cur, "")
                lines.append(f"{cur}: {'+' if val >= 0 else ''}{sym}{val:,.2f}")

        return "\n".join(lines)

    # ─── ราคา TICKER ──────────────────────────────────────────────────────────
    m = re.match(r"^ราคา\s+(\S+)$", text, re.IGNORECASE)
    if m:
        ticker = m.group(1).upper()
        info = _fetch_stock_info(ticker)
        if not info:
            return f"❌ ไม่พบข้อมูล {ticker}\nลองตรวจสอบ Ticker อีกครั้ง"
        return (
            f"💰 {ticker}\n"
            f"{info['name']}\n\n"
            f"ราคาปัจจุบัน: {info['symbol']}{info['price']:,.2f} ({info['currency'].value})\n\n"
            f"ถ้าอยากเพิ่มในพอร์ต พิมพ์:\n"
            f"เพิ่ม {ticker} [จำนวน] [ราคาที่ซื้อ]\n"
            f"เช่น: เพิ่ม {ticker} 10 {info['price']:,.0f}"
        )

    # ─── เพิ่ม TICKER (ดูราคาก่อน) ───────────────────────────────────────────
    m = re.match(r"^เพิ่ม\s+(\S+)$", text)
    if m:
        ticker = m.group(1).upper()
        info = _fetch_stock_info(ticker)
        if not info:
            return f"❌ ไม่พบข้อมูล {ticker}\nลองตรวจสอบ Ticker อีกครั้ง"
        return (
            f"📋 {ticker} — {info['name']}\n"
            f"ราคาปัจจุบัน: {info['symbol']}{info['price']:,.2f}\n\n"
            f"กรอกคำสั่งนี้เพื่อเพิ่ม:\n"
            f"เพิ่ม {ticker} [จำนวนหุ้น] [ราคาที่ซื้อ]\n\n"
            f"ตัวอย่าง:\n"
            f"เพิ่ม {ticker} 10 {info['price']:,.0f}"
        )

    # ─── เพิ่ม TICKER จำนวน ราคา ─────────────────────────────────────────────
    m = re.match(r"^เพิ่ม\s+(\S+)\s+([\d.]+)\s+([\d.]+)$", text)
    if m:
        ticker = m.group(1).upper()
        quantity = float(m.group(2))
        avg_cost = float(m.group(3))

        info = _fetch_stock_info(ticker)
        if not info:
            return f"❌ ไม่พบข้อมูล {ticker} ครับ"

        sym = info["symbol"]
        cost_total = quantity * avg_cost
        current_value = quantity * info["price"]
        pnl = current_value - cost_total
        pnl_pct = (pnl / cost_total * 100) if cost_total > 0 else 0

        async with AsyncSessionLocal() as db:
            await portfolio_service.add_position(
                db,
                ticker=ticker,
                name=info["name"],
                asset_type=info["asset_type"],
                currency=info["currency"],
                quantity=quantity,
                avg_cost=avg_cost,
                bought_at=datetime.now(timezone.utc),
            )

        return (
            f"✅ เพิ่ม {ticker} แล้ว!\n\n"
            f"📋 {info['name']}\n"
            f"จำนวน: {quantity:,.2f} หุ้น\n"
            f"ราคาทุน: {sym}{avg_cost:,.2f}\n"
            f"ต้นทุนรวม: {sym}{cost_total:,.2f}\n\n"
            f"ราคาตอนนี้: {sym}{info['price']:,.2f}\n"
            f"P&L: {'+' if pnl >= 0 else ''}{sym}{pnl:,.2f} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)"
        )

    # ─── ลบ TICKER ────────────────────────────────────────────────────────────
    m = re.match(r"^ลบ\s+(\S+)$", text)
    if m:
        ticker = m.group(1).upper()
        async with AsyncSessionLocal() as db:
            positions = await portfolio_service.get_all_positions(db)
            target = next((p for p in positions if p.ticker == ticker), None)
            if not target:
                return f"❌ ไม่พบ {ticker} ในพอร์ต\nพิมพ์ 'พอร์ต' เพื่อดูรายการ"
            await portfolio_service.delete_position(db, target.id)

        return f"🗑️ ลบ {ticker} ออกจากพอร์ตแล้วครับ"

    # ─── ข่าว TICKER ──────────────────────────────────────────────────────────
    m = re.match(r"^ข่าว\s+(\S+)$", text, re.IGNORECASE)
    if m:
        ticker = m.group(1).upper()
        articles = news_service.fetch_ticker_news(ticker)
        summary = news_service.summarize_news_for_ticker(ticker, articles)
        if not summary:
            return f"ไม่พบข่าวของ {ticker} ครับ"
        emoji = {"บวก": "🟢", "ลบ": "🔴", "เป็นกลาง": "⚪"}.get(summary["sentiment"], "⚪")
        return f"{emoji} ข่าว {ticker}\n\n{summary['summary']}"

    # ─── เทคนิค TICKER ────────────────────────────────────────────────────────
    m = re.match(r"^เทคนิค\s+(\S+)(?:\s+(\S+))?$", text, re.IGNORECASE)
    if m:
        ticker = m.group(1).upper()
        symbol = m.group(2) or "$"
        result = technical_service.analyze_ticker(ticker, currency_symbol=symbol)
        if not result:
            return f"❌ ไม่พบข้อมูล {ticker} ครับ"
        ind = result["indicators"]
        rsi_note = "⚠️ Overbought" if ind["rsi"] > 70 else "🟢 Oversold" if ind["rsi"] < 30 else "ปกติ"
        return (
            f"📊 {ticker}\n"
            f"ราคา: {symbol}{ind['current_price']:,.2f}\n"
            f"RSI: {ind['rsi']} ({rsi_note})\n"
            f"MACD: {ind['macd']:,.4f}\n"
            f"แนวรับ: {symbol}{ind['support_20d']:,.2f}\n"
            f"แนวต้าน: {symbol}{ind['resistance_20d']:,.2f}\n\n"
            f"🤖 {result['interpretation']}"
        )

    # ─── ตลาด ─────────────────────────────────────────────────────────────────
    if lower in ["ตลาด", "market", "ภาพรวม"]:
        overview = news_service.get_market_overview()
        return f"🌍 ภาพรวมตลาดวันนี้\n\n{overview}" if overview else "ดึงข้อมูลไม่ได้ครับ"

    # ─── ช่วย ─────────────────────────────────────────────────────────────────
    if lower in ["ช่วย", "help", "คำสั่ง", "?"]:
        return (
            "📋 NexStock — คำสั่งทั้งหมด\n\n"
            "💼 จัดการพอร์ต\n"
            "พอร์ต — ดู P&L ทุกตัว\n"
            "ราคา AAPL — ดูราคาก่อนเพิ่ม\n"
            "เพิ่ม AAPL — ดูราคา + วิธีเพิ่ม\n"
            "เพิ่ม AAPL 10 180 — เพิ่มเลย\n"
            "ลบ AAPL — ลบออกจากพอร์ต\n\n"
            "📰 วิเคราะห์\n"
            "ข่าว AAPL — สรุปข่าว AI\n"
            "เทคนิค AAPL — RSI แนวรับ/แนวต้าน\n"
            "ตลาด — ภาพรวมตลาดโลก\n\n"
            "💡 ตัวอย่าง\n"
            "เพิ่ม NVDA 5 850\n"
            "เพิ่ม 2800.HK 500 18\n"
            "ลบ AAPL"
        )

    return "ไม่เข้าใจคำสั่งครับ 😅\nพิมพ์ 'ช่วย' เพื่อดูคำสั่งทั้งหมด"


@router.post("/line", summary="LINE Chatbot Webhook")
async def line_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "ok"})

    for event in payload.get("events", []):
        if event.get("type") != "message":
            continue
        if event["message"].get("type") != "text":
            continue

        reply_token = event["replyToken"]
        text = event["message"]["text"]

        try:
            response_text = await _handle_message(text)
        except Exception as e:
            response_text = f"เกิดข้อผิดพลาด: {e}"

        _reply(reply_token, response_text)

    return JSONResponse({"status": "ok"})
