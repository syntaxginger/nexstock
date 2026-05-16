import feedparser
from datetime import datetime, timezone, timedelta
from typing import Optional

from backend.services.gemini_client import generate

RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
]

MARKET_NEWS_FEEDS = [
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
]

HOURS_LOOKBACK = 24


def _is_recent(entry) -> bool:
    try:
        pub = entry.get("published_parsed") or entry.get("updated_parsed")
        if not pub:
            return True
        pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - pub_dt < timedelta(hours=HOURS_LOOKBACK)
    except Exception:
        return True


def fetch_ticker_news(ticker: str, max_items: int = 5) -> list[dict]:
    articles = []
    url = RSS_FEEDS[0].format(ticker=ticker)
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            if not _is_recent(entry):
                continue
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", "")[:300],
                "link": entry.get("link", ""),
                "source": "Yahoo Finance",
            })
    except Exception:
        pass
    return articles


def fetch_market_news(max_items: int = 6) -> list[dict]:
    articles = []
    for feed_url in MARKET_NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:2]:
                if not _is_recent(entry):
                    continue
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "source": feed.feed.get("title", ""),
                })
                if len(articles) >= max_items:
                    return articles
        except Exception:
            continue
    return articles


def summarize_news_for_ticker(ticker: str, articles: list[dict]) -> Optional[dict]:
    if not articles:
        return None

    news_text = "\n".join(f"- {a['title']}: {a['summary']}" for a in articles)

    prompt = f"""คุณเป็นผู้ช่วยวิเคราะห์การลงทุน สรุปข่าวต่อไปนี้เกี่ยวกับหุ้น {ticker} เป็นภาษาไทย

ข่าว:
{news_text}

ตอบในรูปแบบนี้:
สรุป: [สรุปข่าว 2-3 ประโยค]
ผลกระทบ: [บวก/ลบ/เป็นกลาง]
ระดับ: [สูง/ปานกลาง/ต่ำ]
เหตุผล: [อธิบายสั้นๆ ว่ากระทบยังไง]"""

    response = generate(prompt, max_tokens=400)

    if not response:
        return {"ticker": ticker, "summary": "ไม่มี API key — ใส่ GEMINI_API_KEY ใน .env", "sentiment": "เป็นกลาง", "article_count": len(articles)}

    sentiment = "เป็นกลาง"
    if "บวก" in response:
        sentiment = "บวก"
    elif "ลบ" in response:
        sentiment = "ลบ"

    return {
        "ticker": ticker,
        "summary": response,
        "sentiment": sentiment,
        "article_count": len(articles),
    }


def analyze_portfolio_news(tickers: list[str]) -> list[dict]:
    results = []
    for ticker in tickers:
        articles = fetch_ticker_news(ticker)
        if not articles:
            continue
        summary = summarize_news_for_ticker(ticker, articles)
        if summary:
            summary["articles"] = articles
            results.append(summary)
    return results


def get_market_overview() -> Optional[str]:
    articles = fetch_market_news(max_items=6)
    if not articles:
        return None

    news_text = "\n".join(f"- {a['title']}" for a in articles)
    prompt = f"""สรุปภาพรวมตลาดการเงินโลกในวันนี้เป็นภาษาไทย 3-4 ประโยค โดยอิงจากหัวข้อข่าวเหล่านี้:

{news_text}

สรุปให้กระชับ เน้นประเด็นที่กระทบนักลงทุนหุ้น US/HK"""

    return generate(prompt, max_tokens=300)
