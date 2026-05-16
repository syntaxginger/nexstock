import streamlit as st
from streamlit_app.api_client import get

st.set_page_config(page_title="News — NexStock", page_icon="📰", layout="wide")
st.title("📰 ข่าวและ AI สรุป")

# ─── เลือก mode ───────────────────────────────────────────────────────────────
mode = st.radio("ดูข่าว", ["ทุกตัวในพอร์ต", "ค้นหา Ticker เอง"], horizontal=True)

if mode == "ทุกตัวในพอร์ต":
    if st.button("🔄 ดึงข่าวทุกตัว", type="primary"):
        with st.spinner("Gemini กำลังสรุปข่าว..."):
            results = get("/analysis/news/portfolio/all")

        if not results:
            st.warning("ไม่มีหุ้นในพอร์ต หรือไม่พบข่าว")
            st.stop()

        for item in results:
            sentiment = item.get("sentiment", "เป็นกลาง")
            emoji = {"บวก": "🟢", "ลบ": "🔴", "เป็นกลาง": "⚪"}.get(sentiment, "⚪")
            with st.expander(f"{emoji} {item['ticker']} — ผลกระทบ: {sentiment}", expanded=True):
                st.markdown(item.get("summary", "ไม่มีข้อมูล"))
                articles = item.get("articles", [])
                if articles:
                    st.divider()
                    st.caption("📎 บทความต้นฉบับ")
                    for a in articles:
                        st.markdown(f"- [{a['title']}]({a['link']}) — *{a['source']}*")
else:
    col1, col2 = st.columns([3, 1])
    ticker = col1.text_input("ใส่ Ticker", placeholder="เช่น AAPL, NVDA, 2800.HK").upper()
    if col2.button("🔍 ค้นหา", type="primary") and ticker:
        with st.spinner(f"Gemini กำลังสรุปข่าว {ticker}..."):
            result = get(f"/analysis/news/{ticker}")

        if not result:
            st.error("ไม่พบข้อมูล")
            st.stop()

        ai = result.get("ai_summary") or {}
        sentiment = ai.get("sentiment", "เป็นกลาง") if ai else "เป็นกลาง"
        emoji = {"บวก": "🟢", "ลบ": "🔴", "เป็นกลาง": "⚪"}.get(sentiment, "⚪")

        st.subheader(f"{emoji} {ticker} — ผลกระทบ: {sentiment}")
        st.markdown(ai.get("summary", "ไม่มีข้อมูล") if ai else "ไม่พบข่าว")

        articles = result.get("articles", [])
        if articles:
            st.divider()
            st.caption("📎 บทความต้นฉบับ")
            for a in articles:
                st.markdown(f"- [{a['title']}]({a['link']}) — *{a['source']}*")

st.divider()

# ─── ภาพรวมตลาด ───────────────────────────────────────────────────────────────
st.subheader("🌍 ภาพรวมตลาดโลกวันนี้")
if st.button("ดึงภาพรวมตลาด"):
    with st.spinner("Gemini กำลังวิเคราะห์..."):
        result = get("/analysis/market-overview")
    if result and result.get("overview"):
        st.info(result["overview"])
    else:
        st.warning("ไม่พบข้อมูล")
