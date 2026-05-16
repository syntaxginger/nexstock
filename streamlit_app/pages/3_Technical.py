import streamlit as st
import plotly.graph_objects as go
from streamlit_app.api_client import get

st.set_page_config(page_title="Technical — NexStock", page_icon="📊", layout="wide")
st.title("📊 Technical Analysis")


def _render_ticker(item: dict):
    ticker = item["ticker"]
    ind = item["indicators"]
    interp = item.get("interpretation", "")

    with st.expander(f"📈 {ticker} — ราคา {ind['current_price']:,.4f}", expanded=True):
        col1, col2, col3 = st.columns([1, 2, 2])

        rsi = ind["rsi"]
        rsi_color = "#ef4444" if rsi > 70 else "#22c55e" if rsi < 30 else "#f59e0b"
        rsi_label = "Overbought ⚠️" if rsi > 70 else "Oversold 🟢" if rsi < 30 else "ปกติ"

        with col1:
            st.metric("RSI (14)", f"{rsi}", delta=rsi_label)
            st.metric("ATR", f"{ind['atr']:,.4f}")

        with col2:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=rsi,
                title={"text": "RSI Gauge"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": rsi_color},
                    "steps": [
                        {"range": [0, 30], "color": "#dcfce7"},
                        {"range": [30, 70], "color": "#fef9c3"},
                        {"range": [70, 100], "color": "#fee2e2"},
                    ],
                },
            ))
            fig.update_layout(height=200, margin=dict(t=30, b=0, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            macd_color = "normal" if ind["macd_histogram"] >= 0 else "inverse"
            st.markdown("**MACD**")
            st.metric("MACD Line", f"{ind['macd']:,.4f}",
                      delta=f"Histogram {ind['macd_histogram']:+.4f}", delta_color=macd_color)
            st.metric("Signal Line", f"{ind['macd_signal']:,.4f}")

        st.divider()

        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 แนวรับ (20 วัน)", f"{ind['support_20d']:,.4f}")
        c2.metric("⚪ ราคาปัจจุบัน", f"{ind['current_price']:,.4f}")
        c3.metric("🔴 แนวต้าน (20 วัน)", f"{ind['resistance_20d']:,.4f}")

        st.caption(
            f"Bollinger Bands — Upper: {ind['bb_upper']:,.4f} | "
            f"Mid: {ind['bb_mid']:,.4f} | Lower: {ind['bb_lower']:,.4f}"
        )

        st.divider()
        st.markdown("**🤖 Gemini วิเคราะห์:**")
        st.info(interp)


# ─── เลือก mode ───────────────────────────────────────────────────────────────
mode = st.radio("วิเคราะห์", ["ทุกตัวในพอร์ต", "ค้นหา Ticker เอง"], horizontal=True)

if mode == "ทุกตัวในพอร์ต":
    if st.button("🔄 วิเคราะห์ทุกตัว", type="primary"):
        with st.spinner("กำลังคำนวณ + Gemini แปลสัญญาณ..."):
            results = get("/analysis/technical/portfolio/all")

        if not results:
            st.warning("ไม่มีหุ้นในพอร์ต หรือดึงข้อมูลไม่ได้")
            st.stop()

        for item in results:
            _render_ticker(item)
else:
    c1, c2, c3 = st.columns([3, 1, 1])
    ticker = c1.text_input("ใส่ Ticker", placeholder="เช่น AAPL, NVDA, 2800.HK").upper()
    symbol = c2.selectbox("สกุลเงิน", ["$", "HK$", "฿"])
    if c3.button("🔍 วิเคราะห์", type="primary") and ticker:
        with st.spinner(f"กำลังวิเคราะห์ {ticker}..."):
            result = get(f"/analysis/technical/{ticker}?currency_symbol={symbol}")
        if result and "indicators" in result:
            _render_ticker(result)
        else:
            st.error(f"ไม่พบข้อมูล {ticker}")
