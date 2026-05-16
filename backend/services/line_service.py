import requests
from datetime import datetime, timezone

from backend.config import get_settings

settings = get_settings()

LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.line_channel_access_token}",
    }


def send_line_message(text: str) -> bool:
    if not settings.line_channel_access_token or not settings.line_user_id:
        print("[LINE] ยังไม่ได้ตั้งค่า LINE_CHANNEL_ACCESS_TOKEN หรือ LINE_USER_ID")
        return False

    payload = {
        "to": settings.line_user_id,
        "messages": [{"type": "text", "text": text}],
    }
    try:
        resp = requests.post(LINE_API_URL, json=payload, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[LINE] ส่งข้อความไม่สำเร็จ: {e}")
        return False


def format_morning_brief(
    market_overview: str,
    portfolio_news: list[dict],
    technical_highlights: list[dict],
) -> str:
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    lines = [f"🌅 NexStock Morning Brief — {now}\n"]

    lines.append("📊 ภาพรวมตลาด")
    lines.append(market_overview or "ไม่มีข้อมูลภาพรวมตลาด")
    lines.append("")

    if portfolio_news:
        lines.append("📰 ข่าวกระทบพอร์ต")
        for item in portfolio_news[:5]:
            sentiment_emoji = {"บวก": "🟢", "ลบ": "🔴", "เป็นกลาง": "⚪"}.get(
                item.get("sentiment", "เป็นกลาง"), "⚪"
            )
            lines.append(f"{sentiment_emoji} {item['ticker']}: {item.get('sentiment','')}")
            summary_lines = item.get("summary", "").split("\n")
            for line in summary_lines[:2]:
                if line.strip():
                    lines.append(f"   {line.strip()}")
        lines.append("")

    if technical_highlights:
        lines.append("📈 สัญญาณ Technical")
        for item in technical_highlights[:5]:
            ticker = item.get("ticker", "")
            interp = item.get("interpretation", "")
            first_line = interp.split("\n")[0] if interp else ""
            lines.append(f"• {ticker}: {first_line}")
        lines.append("")

    lines.append("─────────────────")
    lines.append("NexStock AI • ข้อมูลอ้างอิงเท่านั้น ไม่ใช่คำแนะนำทางการเงิน")

    return "\n".join(lines)


def format_price_alert(ticker: str, alert_type: str, price: float, currency_symbol: str = "$") -> str:
    emoji = "⚠️" if alert_type == "support" else "🚨"
    level = "แนวรับ" if alert_type == "support" else "แนวต้าน"
    return (
        f"{emoji} แจ้งเตือน {ticker}\n"
        f"ราคาทะลุ{level}: {currency_symbol}{price:,.2f}\n"
        f"เวลา: {datetime.now().strftime('%H:%M น.')}"
    )
