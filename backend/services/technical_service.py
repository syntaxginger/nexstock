import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional

from backend.services.gemini_client import generate


def fetch_ohlcv(ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return None
        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
        return df
    except Exception:
        return None


def _rsi(close: pd.Series, length: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()
    rs = gain / loss.replace(0, np.nan)
    return float((100 - (100 / (1 + rs))).iloc[-1])


def _macd(close: pd.Series, fast=12, slow=26, signal=9) -> tuple[float, float, float]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float((macd_line - signal_line).iloc[-1])


def _bollinger_bands(close: pd.Series, length=20, std=2) -> tuple[float, float, float]:
    mid = close.rolling(length).mean()
    std_dev = close.rolling(length).std()
    return float((mid + std * std_dev).iloc[-1]), float(mid.iloc[-1]), float((mid - std * std_dev).iloc[-1])


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length=14) -> float:
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return float(tr.rolling(length).mean().iloc[-1])


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["close"].squeeze()
    high = df["high"].squeeze()
    low = df["low"].squeeze()

    return {
        "current_price": round(float(close.iloc[-1]), 4),
        "rsi": round(_rsi(close), 2),
        "macd": round(_macd(close)[0], 4),
        "macd_signal": round(_macd(close)[1], 4),
        "macd_histogram": round(_macd(close)[2], 4),
        "bb_upper": round(_bollinger_bands(close)[0], 4),
        "bb_mid": round(_bollinger_bands(close)[1], 4),
        "bb_lower": round(_bollinger_bands(close)[2], 4),
        "atr": round(_atr(high, low, close), 4),
        "support_20d": round(float(close.rolling(20).min().iloc[-1]), 4),
        "resistance_20d": round(float(close.rolling(20).max().iloc[-1]), 4),
    }


def interpret_indicators(ticker: str, indicators: dict, currency_symbol: str = "$") -> str:
    p = indicators
    prompt = f"""คุณเป็นผู้เชี่ยวชาญ Technical Analysis อธิบายสัญญาณต่อไปนี้ของหุ้น {ticker} เป็นภาษาไทยให้เข้าใจง่าย

ข้อมูล:
- ราคาปัจจุบัน: {currency_symbol}{p['current_price']}
- RSI (14): {p['rsi']} (>70=overbought, <30=oversold)
- MACD: {p['macd']}, Signal: {p['macd_signal']}, Histogram: {p['macd_histogram']}
- Bollinger Bands: Upper {currency_symbol}{p['bb_upper']}, Mid {currency_symbol}{p['bb_mid']}, Lower {currency_symbol}{p['bb_lower']}
- ATR (14): {p['atr']}
- แนวรับ 20 วัน: {currency_symbol}{p['support_20d']}
- แนวต้าน 20 วัน: {currency_symbol}{p['resistance_20d']}

อธิบายใน 3-4 ประโยค บอกสัญญาณสำคัญ แนวรับ/แนวต้าน และคำแนะนำสั้นๆ ว่าควรระวังอะไร"""

    response = generate(prompt, max_tokens=350)
    return response if response else _fallback_interpretation(ticker, indicators, currency_symbol)


def _fallback_interpretation(ticker: str, indicators: dict, currency_symbol: str) -> str:
    rsi = indicators.get("rsi", 50)
    price = indicators.get("current_price", 0)
    support = indicators.get("support_20d", 0)
    resistance = indicators.get("resistance_20d", 0)

    if rsi > 70:
        rsi_note = f"RSI {rsi:.0f} — overbought ระวังแรงขาย"
    elif rsi < 30:
        rsi_note = f"RSI {rsi:.0f} — oversold อาจมีแรงซื้อ"
    else:
        rsi_note = f"RSI {rsi:.0f} — อยู่ในโซนปกติ"

    return (
        f"{ticker} ราคา {currency_symbol}{price:,.2f} | "
        f"แนวรับ {currency_symbol}{support:,.2f} แนวต้าน {currency_symbol}{resistance:,.2f} | {rsi_note}"
    )


def analyze_ticker(ticker: str, currency_symbol: str = "$") -> Optional[dict]:
    df = fetch_ohlcv(ticker)
    if df is None:
        return None
    indicators = compute_indicators(df)
    return {
        "ticker": ticker,
        "indicators": indicators,
        "interpretation": interpret_indicators(ticker, indicators, currency_symbol),
    }
