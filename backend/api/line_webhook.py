"""
LINE Chatbot — Flex Message + Quick Reply buttons
ไม่ต้องพิมพ์คำสั่ง กดปุ่มได้เลย

Flow เพิ่มหุ้น (step-by-step):
  กด "เพิ่มหุ้น" → พิมพ์ ticker → ยืนยันราคา → พิมพ์จำนวน → พิมพ์ราคาทุน → เสร็จ
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
from backend.services import news_service, technical_service, portfolio_service

router = APIRouter(prefix="/webhook", tags=["LINE Chatbot"])
settings = get_settings()

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# conversation state สำหรับ flow เพิ่มหุ้น
_state: dict[str, dict] = {}


def _headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.line_channel_access_token}",
    }


def _reply(token: str, messages: list[dict]):
    requests.post(LINE_REPLY_URL, json={
        "replyToken": token,
        "messages": messages[:5],
    }, headers=_headers(), timeout=10)


def _quick_reply_menu():
    """ปุ่มเมนูหลัก"""
    return {
        "items": [
            {"type": "action", "action": {"type": "message", "label": "💼 พอร์ต", "text": "ดูพอร์ต"}},
            {"type": "action", "action": {"type": "message", "label": "📰 ข่าว", "text": "ดูข่าว"}},
            {"type": "action", "action": {"type": "message", "label": "📊 เทคนิค", "text": "ดูเทคนิค"}},
            {"type": "action", "action": {"type": "message", "label": "➕ เพิ่มหุ้น", "text": "เพิ่มหุ้น"}},
            {"type": "action", "action": {"type": "message", "label": "🗑️ ลบหุ้น", "text": "ลบหุ้น"}},
        ]
    }


def _text_msg(text: str, with_menu: bool = True) -> dict:
    msg = {"type": "text", "text": text[:4999]}
    if with_menu:
        msg["quickReply"] = _quick_reply_menu()
    return msg


def _portfolio_flex(positions: list[dict]) -> dict:
    """การ์ดพอร์ตสวยๆ"""
    rows = []
    for p in positions:
        color = "#22c55e" if p["pnl"] >= 0 else "#ef4444"
        emoji = "▲" if p["pnl"] >= 0 else "▼"
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "margin": "sm",
            "contents": [
                {"type": "text", "text": p["ticker"], "weight": "bold", "size": "md", "flex": 2},
                {"type": "text", "text": f"{p['currency_symbol']}{p['current_price']:,.2f}",
                 "size": "sm", "color": "#555555", "flex": 2, "align": "center"},
                {"type": "text",
                 "text": f"{emoji} {p['pnl_pct_str']}",
                 "size": "sm", "color": color, "flex": 2, "align": "end", "weight": "bold"},
            ]
        })

    total_lines = []
    for cur, val in (positions[0].get("_totals") or {}).items() if positions else []:
        pass

    return {
        "type": "flex",
        "altText": "สรุปพอร์ต",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1a1a2e",
                "contents": [{
                    "type": "text",
                    "text": "💼 พอร์ตของคุณ",
                    "color": "#ffffff",
                    "weight": "bold",
                    "size": "lg",
                }]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": rows or [{"type": "text", "text": "ยังไม่มีหุ้นในพอร์ต", "color": "#888888"}],
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#1a1a2e",
                     "action": {"type": "message", "label": "📰 ดูข่าว", "text": "ดูข่าว"},
                     "height": "sm"},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "➕ เพิ่มหุ้น", "text": "เพิ่มหุ้น"},
                     "height": "sm"},
                ]
            }
        }
    }


def _stock_confirm_flex(info: dict) -> dict:
    """การ์ดยืนยันหุ้นก่อนเพิ่ม"""
    sym = info["symbol"]
    return {
        "type": "flex",
        "altText": f"ยืนยัน {info['ticker']}",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": info["ticker"], "weight": "bold", "size": "xxl"},
                    {"type": "text", "text": info["name"], "color": "#888888", "size": "sm", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                        {"type": "text", "text": "ราคาปัจจุบัน", "color": "#555555", "flex": 2},
                        {"type": "text", "text": f"{sym}{info['price']:,.2f}",
                         "weight": "bold", "flex": 2, "align": "end"},
                    ]},
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "สกุลเงิน", "color": "#555555", "flex": 2},
                        {"type": "text", "text": info["currency"].value, "flex": 2, "align": "end"},
                    ]},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "พิมพ์จำนวนหุ้นที่ซื้อ เช่น 10",
                     "color": "#888888", "size": "sm", "margin": "md"},
                ]
            }
        }
    }


def _fetch_stock_info(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        fast = t.fast_info
        price = round(float(fast.last_price), 4)
        currency_raw = getattr(fast, "currency", "USD")
        currency_map = {"USD": Currency.USD, "HKD": Currency.HKD, "THB": Currency.THB}
        currency = currency_map.get(currency_raw, Currency.USD)
        sym_map = {Currency.USD: "$", Currency.HKD: "HK$", Currency.THB: "฿"}
        info = t.info
        name = info.get("longName") or info.get("shortName") or ticker
        asset_type = (AssetType.HK_STOCK if ticker.endswith(".HK")
                      else AssetType.TH_FUND if currency == Currency.THB
                      else AssetType.US_STOCK)
        return {"ticker": ticker, "name": name, "price": price,
                "currency": currency, "symbol": sym_map[currency], "asset_type": asset_type}
    except Exception:
        return None


async def _handle_message(user_id: str, text: str) -> list[dict]:
    text = text.strip()
    lower = text.lower()
    state = _state.get(user_id, {})

    # ─── flow เพิ่มหุ้น step-by-step ──────────────────────────────────────────
    if state.get("step") == "wait_ticker":
        ticker = text.upper()
        info = _fetch_stock_info(ticker)
        if not info:
            return [_text_msg(f"❌ ไม่พบหุ้น '{ticker}'\nลองใหม่ หรือกด ยกเลิก", with_menu=False)]
        _state[user_id] = {"step": "wait_quantity", "info": info}
        return [_stock_confirm_flex(info)]

    if state.get("step") == "wait_quantity":
        try:
            qty = float(text.replace(",", ""))
            _state[user_id] = {**state, "step": "wait_price", "quantity": qty}
            info = state["info"]
            return [_text_msg(
                f"ซื้อ {info['ticker']} {qty:,.0f} หุ้น\n\n"
                f"ราคาที่ซื้อเท่าไหร่ {info['symbol']}?\n"
                f"(ราคาตอนนี้ {info['symbol']}{info['price']:,.2f})",
                with_menu=False
            )]
        except ValueError:
            return [_text_msg("กรุณาพิมพ์ตัวเลขจำนวนหุ้น เช่น 10", with_menu=False)]

    if state.get("step") == "wait_price":
        try:
            price_bought = float(text.replace(",", ""))
            info = state["info"]
            qty = state["quantity"]
            sym = info["symbol"]

            async with AsyncSessionLocal() as db:
                await portfolio_service.add_position(
                    db, ticker=info["ticker"], name=info["name"],
                    asset_type=info["asset_type"], currency=info["currency"],
                    quantity=qty, avg_cost=price_bought,
                    bought_at=datetime.now(timezone.utc),
                )
            _state.pop(user_id, None)

            cost = qty * price_bought
            current_val = qty * info["price"]
            pnl = current_val - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"

            return [_text_msg(
                f"✅ เพิ่ม {info['ticker']} แล้ว!\n\n"
                f"จำนวน: {qty:,.0f} หุ้น\n"
                f"ราคาทุน: {sym}{price_bought:,.2f}\n"
                f"ต้นทุน: {sym}{cost:,.2f}\n\n"
                f"{pnl_emoji} P&L ตอนนี้: {'+' if pnl >= 0 else ''}{sym}{pnl:,.2f} "
                f"({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)"
            )]
        except ValueError:
            return [_text_msg("กรุณาพิมพ์ราคา เช่น 180.50", with_menu=False)]

    if state.get("step") == "wait_delete":
        ticker = text.upper()
        async with AsyncSessionLocal() as db:
            positions = await portfolio_service.get_all_positions(db)
            target = next((p for p in positions if p.ticker == ticker), None)
            if not target:
                _state.pop(user_id, None)
                return [_text_msg(f"❌ ไม่พบ {ticker} ในพอร์ต")]
            await portfolio_service.delete_position(db, target.id)
        _state.pop(user_id, None)
        return [_text_msg(f"🗑️ ลบ {ticker} ออกจากพอร์ตแล้วครับ")]

    # ─── ยกเลิก ───────────────────────────────────────────────────────────────
    if lower in ["ยกเลิก", "cancel", "หยุด"]:
        _state.pop(user_id, None)
        return [_text_msg("ยกเลิกแล้วครับ")]

    # ─── ดูพอร์ต ──────────────────────────────────────────────────────────────
    if lower in ["ดูพอร์ต", "พอร์ต", "portfolio"]:
        async with AsyncSessionLocal() as db:
            summary = await portfolio_service.get_portfolio_summary(db)

        if not summary["positions"]:
            return [_text_msg("💼 ยังไม่มีหุ้นในพอร์ต\nกด ➕ เพิ่มหุ้น เพื่อเริ่มต้น")]

        flex = _portfolio_flex(summary["positions"])
        total = summary.get("total_pnl_by_currency", {})
        total_lines = [f"{'🟢' if v >= 0 else '🔴'} {cur}: {'+' if v >= 0 else ''}{v:,.2f}"
                       for cur, v in total.items()]
        total_msg = _text_msg("💰 P&L รวม\n" + "\n".join(total_lines)) if total_lines else None

        return [flex] + ([total_msg] if total_msg else [])

    # ─── เพิ่มหุ้น ─────────────────────────────────────────────────────────────
    if lower in ["เพิ่มหุ้น", "เพิ่ม"]:
        _state[user_id] = {"step": "wait_ticker"}
        return [_text_msg(
            "➕ เพิ่มหุ้น\n\nพิมพ์ชื่อหุ้นหรือ Ticker:\n"
            "เช่น AAPL, NVDA, GOOG\nหุ้น HK: 2800.HK\n\n(พิมพ์ ยกเลิก เพื่อหยุด)",
            with_menu=False
        )]

    # ─── ลบหุ้น ───────────────────────────────────────────────────────────────
    if lower in ["ลบหุ้น", "ลบ"]:
        async with AsyncSessionLocal() as db:
            positions = await portfolio_service.get_all_positions(db)

        if not positions:
            return [_text_msg("ไม่มีหุ้นในพอร์ตครับ")]

        tickers = [p.ticker for p in positions]
        _state[user_id] = {"step": "wait_delete"}

        qr_items = [{"type": "action", "action": {"type": "message", "label": t, "text": t}}
                    for t in tickers[:13]]
        return [{
            "type": "text",
            "text": f"🗑️ เลือกหุ้นที่อยากลบ:\n" + ", ".join(tickers),
            "quickReply": {"items": qr_items}
        }]

    # ─── ดูข่าว ───────────────────────────────────────────────────────────────
    if lower in ["ดูข่าว", "ข่าว"]:
        async with AsyncSessionLocal() as db:
            positions = await portfolio_service.get_all_positions(db)

        if not positions:
            return [_text_msg("ไม่มีหุ้นในพอร์ต")]

        tickers = list({p.ticker for p in positions})
        qr_items = [{"type": "action", "action": {"type": "message", "label": t, "text": f"ข่าว {t}"}}
                    for t in tickers[:13]]
        return [{
            "type": "text",
            "text": "📰 เลือกหุ้นที่อยากดูข่าว:",
            "quickReply": {"items": qr_items}
        }]

    m = re.match(r"^ข่าว\s+(\S+)$", text, re.IGNORECASE)
    if m:
        ticker = m.group(1).upper()
        articles = news_service.fetch_ticker_news(ticker)
        summary = news_service.summarize_news_for_ticker(ticker, articles)
        if not summary:
            return [_text_msg(f"ไม่พบข่าวของ {ticker}")]
        emoji = {"บวก": "🟢", "ลบ": "🔴", "เป็นกลาง": "⚪"}.get(summary["sentiment"], "⚪")
        return [_text_msg(f"{emoji} ข่าว {ticker}\n\n{summary['summary']}")]

    # ─── ดูเทคนิค ─────────────────────────────────────────────────────────────
    if lower in ["ดูเทคนิค", "เทคนิค"]:
        async with AsyncSessionLocal() as db:
            positions = await portfolio_service.get_all_positions(db)

        if not positions:
            return [_text_msg("ไม่มีหุ้นในพอร์ต")]

        tickers = list({p.ticker for p in positions})
        qr_items = [{"type": "action", "action": {"type": "message", "label": t, "text": f"เทคนิค {t}"}}
                    for t in tickers[:13]]
        return [{"type": "text", "text": "📊 เลือกหุ้นที่อยากดู Technical:", "quickReply": {"items": qr_items}}]

    m = re.match(r"^เทคนิค\s+(\S+)$", text, re.IGNORECASE)
    if m:
        ticker = m.group(1).upper()
        sym_map = {"HKD": "HK$", "THB": "฿"}
        async with AsyncSessionLocal() as db:
            positions = await portfolio_service.get_all_positions(db)
        pos = next((p for p in positions if p.ticker == ticker), None)
        sym = sym_map.get(pos.currency.value, "$") if pos else "$"
        result = technical_service.analyze_ticker(ticker, sym)
        if not result:
            return [_text_msg(f"ไม่พบข้อมูล {ticker}")]
        ind = result["indicators"]
        rsi_note = "⚠️ Overbought" if ind["rsi"] > 70 else "🟢 Oversold" if ind["rsi"] < 30 else "ปกติ"
        return [_text_msg(
            f"📊 {ticker}\n"
            f"ราคา: {sym}{ind['current_price']:,.2f}\n"
            f"RSI: {ind['rsi']} ({rsi_note})\n"
            f"แนวรับ: {sym}{ind['support_20d']:,.2f}\n"
            f"แนวต้าน: {sym}{ind['resistance_20d']:,.2f}\n\n"
            f"🤖 {result['interpretation']}"
        )]

    # ─── เมนูหลัก (default) ───────────────────────────────────────────────────
    return [_text_msg("👋 สวัสดีครับ! กดปุ่มด้านล่างได้เลย")]


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
        user_id = event["source"].get("userId", "default")
        text = event["message"]["text"]

        try:
            messages = await _handle_message(user_id, text)
        except Exception as e:
            messages = [_text_msg(f"เกิดข้อผิดพลาด: {e}")]

        _reply(reply_token, messages)

    return JSONResponse({"status": "ok"})
