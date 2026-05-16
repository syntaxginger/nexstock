"""
Alert schedule (เวลาไทย UTC+7):
  08:00  Morning Brief       — US ปิดเมื่อคืน + ข่าว + แนะนำหุ้น
  09:00  HK Pre-open         — Futures + sentiment ก่อน HK เปิด
  12:30  HK Mid-session      — สรุปครึ่งเช้า HK
  15:15  HK Close            — สรุป HK + เตรียม US คืนนี้
  21:00  US Pre-open         — Futures + ข่าวล่าสุด ก่อน US เปิด
  */10   Price alert check   — ตรวจราคาทะลุแนวรับ/แนวต้านทุก 10 นาที
  จันทร์ 08:30  Weekly review
"""

import asyncio
from datetime import datetime, timezone, timedelta

from backend.database import AsyncSessionLocal
from backend.services import portfolio_service, news_service, technical_service, line_service
from backend.services.gemini_client import generate
from backend.models.portfolio import Currency

CURRENCY_SYMBOL_MAP = {
    Currency.USD: "$",
    Currency.HKD: "HK$",
    Currency.THB: "฿",
}

# เก็บราคาล่าสุดที่เช็คไว้ เพื่อ detect การทะลุ
_last_prices: dict[str, float] = {}


# ─── helpers ────────────────────────────────────────────────────────────────

async def _get_positions():
    async with AsyncSessionLocal() as db:
        return await portfolio_service.get_all_positions(db)


def _ticker_map(positions) -> dict[str, str]:
    return {p.ticker: CURRENCY_SYMBOL_MAP.get(p.currency, "$") for p in positions}


def _send(text: str):
    line_service.send_line_message(text)
    print(text)


# ─── Morning Brief (08:00) ──────────────────────────────────────────────────

async def run_morning_brief():
    print("[08:00] Morning Brief เริ่ม...")
    positions = await _get_positions()
    if not positions:
        return

    tickers = list({p.ticker for p in positions})
    sym = _ticker_map(positions)

    market_overview = news_service.get_market_overview() or "ไม่มีข้อมูลภาพรวมตลาด"
    portfolio_news = news_service.analyze_portfolio_news(tickers)
    technical = [technical_service.analyze_ticker(t, sym.get(t, "$")) for t in tickers]
    technical = [r for r in technical if r]

    msg = line_service.format_morning_brief(market_overview, portfolio_news, technical)
    _send(msg)


# ─── HK Pre-open (09:00) ────────────────────────────────────────────────────

async def run_hk_preopen():
    print("[09:00] HK Pre-open Alert เริ่ม...")
    positions = await _get_positions()
    hk_positions = [p for p in positions if p.currency == Currency.HKD]
    if not hk_positions:
        return

    tickers = [p.ticker for p in hk_positions]
    news_items = news_service.analyze_portfolio_news(tickers)

    prompt = f"""ตลาดหุ้นฮ่องกง (HKEX) กำลังจะเปิดในอีก 30 นาที
หุ้น HK ในพอร์ต: {', '.join(tickers)}

ข้อมูลข่าวล่าสุด:
{chr(10).join(f"- {n['ticker']}: {n.get('sentiment','')}" for n in news_items)}

สรุป 2-3 ประโยค ว่าวันนี้ตลาด HK น่าจะเปิดยังไง และมีหุ้นตัวไหนในพอร์ตที่ต้องระวังเป็นพิเศษ"""

    summary = generate(prompt, max_tokens=250) or "ไม่สามารถสรุปได้"

    lines = [
        "🇭🇰 HK Pre-open Alert",
        f"⏰ {datetime.now().strftime('%H:%M น.')} — ตลาด HK เปิดใน 30 นาที",
        "",
        summary,
        "",
        "─────────────────",
        "NexStock AI",
    ]
    _send("\n".join(lines))


# ─── HK Mid-session (12:30) ─────────────────────────────────────────────────

async def run_hk_midsession():
    print("[12:30] HK Mid-session Alert เริ่ม...")
    positions = await _get_positions()
    hk_positions = [p for p in positions if p.currency == Currency.HKD]
    if not hk_positions:
        return

    sym = _ticker_map(positions)
    results = []
    for p in hk_positions:
        r = technical_service.analyze_ticker(p.ticker, sym.get(p.ticker, "HK$"))
        if r:
            ind = r["indicators"]
            results.append(
                f"• {p.ticker}: HK${ind['current_price']:,.2f} | RSI {ind['rsi']} | "
                f"แนวรับ HK${ind['support_20d']:,.2f} แนวต้าน HK${ind['resistance_20d']:,.2f}"
            )

    lines = [
        "📊 HK Mid-session Report",
        f"⏰ {datetime.now().strftime('%H:%M น.')} — สรุปครึ่งเช้า",
        "",
        *results,
        "",
        "─────────────────",
        "NexStock AI",
    ]
    _send("\n".join(lines))


# ─── HK Close (15:15) ───────────────────────────────────────────────────────

async def run_hk_close():
    print("[15:15] HK Close Alert เริ่ม...")
    positions = await _get_positions()
    hk_positions = [p for p in positions if p.currency == Currency.HKD]
    if not hk_positions:
        return

    sym = _ticker_map(positions)
    pnl_lines = []
    async with AsyncSessionLocal() as db:
        summary = await portfolio_service.get_portfolio_summary(db)

    hk_data = [p for p in summary["positions"] if p["currency"] == Currency.HKD]
    for item in hk_data:
        emoji = "🟢" if item["pnl"] >= 0 else "🔴"
        pnl_lines.append(f"{emoji} {item['ticker']}: {item['pnl_str']} ({item['pnl_pct_str']})")

    us_tickers = [p.ticker for p in positions if p.currency == Currency.USD]
    us_news = news_service.analyze_portfolio_news(us_tickers[:3]) if us_tickers else []
    us_preview = "\n".join(
        f"• {n['ticker']}: {n.get('sentiment','เป็นกลาง')}" for n in us_news
    ) or "ไม่มีข้อมูล"

    lines = [
        "🇭🇰 HK Close Summary",
        f"⏰ {datetime.now().strftime('%H:%M น.')} — ตลาด HK ปิดแล้ว",
        "",
        "📈 P&L วันนี้:",
        *pnl_lines,
        "",
        "🌙 ข่าว US คืนนี้:",
        us_preview,
        "",
        "─────────────────",
        "NexStock AI",
    ]
    _send("\n".join(lines))


# ─── US Pre-open (21:00) ────────────────────────────────────────────────────

async def run_us_preopen():
    print("[21:00] US Pre-open Alert เริ่ม...")
    positions = await _get_positions()
    us_positions = [p for p in positions if p.currency == Currency.USD]
    if not us_positions:
        return

    tickers = [p.ticker for p in us_positions]
    news_items = news_service.analyze_portfolio_news(tickers)
    market_overview = news_service.get_market_overview() or ""

    prompt = f"""ตลาดหุ้น US (NYSE/NASDAQ) กำลังจะเปิดในอีกประมาณ 30 นาที
หุ้น US ในพอร์ต: {', '.join(tickers)}

ภาพรวมล่าสุด: {market_overview[:200]}

ข่าวรายตัว:
{chr(10).join(f"- {n['ticker']}: {n.get('sentiment','')}" for n in news_items)}

สรุป 2-3 ประโยค ควรระวังอะไรคืนนี้ มีตัวไหนน่าสนใจเป็นพิเศษ"""

    summary = generate(prompt, max_tokens=250) or "ไม่สามารถสรุปได้"

    lines = [
        "🇺🇸 US Pre-open Alert",
        f"⏰ {datetime.now().strftime('%H:%M น.')} — ตลาด US เปิดใน ~30 นาที",
        "",
        summary,
        "",
        "─────────────────",
        "NexStock AI",
    ]
    _send("\n".join(lines))


# ─── Price Alert checker (ทุก 10 นาที ช่วงตลาดเปิด) ────────────────────────

def _market_is_open() -> bool:
    """ตรวจว่าตอนนี้ตลาด HK หรือ US เปิดอยู่ไหม (เวลาไทย)"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()  # 0=จันทร์ ... 4=ศุกร์

    if weekday >= 5:
        return False

    total_min = hour * 60 + minute
    hk_open = 8 * 60 + 30    # 08:30
    hk_close = 15 * 60        # 15:00
    us_open = 21 * 60 + 30   # 21:30 (EDT)
    us_close_next = 4 * 60    # 04:00 วันถัดไป

    in_hk = hk_open <= total_min <= hk_close
    in_us = total_min >= us_open or total_min <= us_close_next
    return in_hk or in_us


async def run_price_alert_check():
    if not _market_is_open():
        return

    positions = await _get_positions()
    if not positions:
        return

    sym = _ticker_map(positions)
    alerts = []

    for pos in positions:
        ticker = pos.ticker
        result = technical_service.analyze_ticker(ticker, sym.get(ticker, "$"))
        if not result:
            continue

        ind = result["indicators"]
        price = ind["current_price"]
        support = ind["support_20d"]
        resistance = ind["resistance_20d"]
        prev = _last_prices.get(ticker)
        _last_prices[ticker] = price

        if prev is None:
            continue

        s = sym.get(ticker, "$")
        if prev > support and price <= support:
            alerts.append(line_service.format_price_alert(ticker, "support", price, s))
        elif prev < resistance and price >= resistance:
            alerts.append(line_service.format_price_alert(ticker, "resistance", price, s))

    for alert in alerts:
        _send(alert)


# ─── Weekly Review (จันทร์ 08:30) ───────────────────────────────────────────

async def run_weekly_review():
    print("[จันทร์ 08:30] Weekly Review เริ่ม...")
    positions = await _get_positions()
    if not positions:
        return

    async with AsyncSessionLocal() as db:
        summary = await portfolio_service.get_portfolio_summary(db)

    total_pnl = summary.get("total_pnl_by_currency", {})
    pnl_lines = [f"  {cur}: {'+' if v >= 0 else ''}{v:,.2f}" for cur, v in total_pnl.items()]

    top = sorted(summary["positions"], key=lambda x: x["pnl_pct"], reverse=True)
    best = top[:2] if top else []
    worst = top[-2:] if len(top) >= 2 else []

    best_lines = [f"🟢 {p['ticker']}: {p['pnl_pct_str']}" for p in best]
    worst_lines = [f"🔴 {p['ticker']}: {p['pnl_pct_str']}" for p in worst]

    lines = [
        "📅 NexStock Weekly Review",
        f"สัปดาห์ที่แล้ว — {datetime.now().strftime('%d/%m/%Y')}",
        "",
        "💰 P&L รวม:",
        *pnl_lines,
        "",
        f"🏆 ดีสุด: {', '.join(best_lines) or '-'}",
        f"⚠️ แย่สุด: {', '.join(worst_lines) or '-'}",
        "",
        "─────────────────",
        "NexStock AI",
    ]
    _send("\n".join(lines))
