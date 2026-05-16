import streamlit as st
from datetime import datetime, date
import yfinance as yf
from streamlit_app.api_client import get, post, delete

st.set_page_config(page_title="Portfolio — NexStock", page_icon="💼", layout="wide")
st.title("💼 จัดการพอร์ต")

# ─── ฟอร์มเพิ่มหุ้น ───────────────────────────────────────────────────────────
st.subheader("➕ เพิ่มหุ้น / กองทุน")

col_ticker, col_btn = st.columns([3, 1])
ticker_input = col_ticker.text_input(
    "พิมพ์ชื่อหุ้น หรือ Ticker",
    placeholder="เช่น AAPL, NVDA, GOOG, 2800.HK",
    help="หุ้น US ใส่ชื่อตรงๆ เช่น AAPL | หุ้น HK ใส่ตามด้วย .HK เช่น 2800.HK"
)
lookup = col_btn.button("🔍 ค้นหา", type="primary", use_container_width=True)

if lookup and ticker_input:
    ticker_clean = ticker_input.strip().upper()
    with st.spinner(f"กำลังดึงข้อมูล {ticker_clean}..."):
        try:
            info = yf.Ticker(ticker_clean).fast_info
            current_price = round(float(info.last_price), 4)
            currency_raw = getattr(info, "currency", "USD")
            currency_map = {"USD": "USD", "HKD": "HKD", "THB": "THB"}
            currency = currency_map.get(currency_raw, "USD")

            full_info = yf.Ticker(ticker_clean).info
            long_name = full_info.get("longName") or full_info.get("shortName") or ticker_clean

            st.session_state["lookup"] = {
                "ticker": ticker_clean,
                "name": long_name,
                "current_price": current_price,
                "currency": currency,
            }
        except Exception:
            st.error(f"ไม่พบข้อมูล {ticker_clean} — ลองตรวจสอบ Ticker อีกครั้ง")
            st.session_state.pop("lookup", None)

if "lookup" in st.session_state:
    d = st.session_state["lookup"]
    sym = {"USD": "$", "HKD": "HK$", "THB": "฿"}.get(d["currency"], "$")

    st.success(f"**{d['ticker']}** — {d['name']}")
    st.info(f"ราคาปัจจุบัน: **{sym}{d['current_price']:,.2f}** ({d['currency']})")

    with st.form("add_position", clear_on_submit=True):
        st.markdown("#### กรอกรายละเอียดการซื้อ")

        col1, col2 = st.columns(2)
        with col1:
            quantity = st.number_input(
                f"ซื้อกี่หุ้น / หน่วย *",
                min_value=0.0001, step=1.0, format="%.4f",
                help="จำนวนหุ้นที่ซื้อ"
            )
            avg_cost = st.number_input(
                f"ราคาที่ซื้อ ({sym}) *",
                min_value=0.0001,
                value=float(d["current_price"]),
                step=0.01, format="%.4f",
                help=f"ราคาตอนที่ซื้อ (ราคาปัจจุบัน {sym}{d['current_price']:,.2f})"
            )
        with col2:
            bought_at = st.date_input("วันที่ซื้อ *", value=date.today())
            fee = st.number_input(
                f"ค่าธรรมเนียม ({sym})",
                min_value=0.0, value=0.0, step=0.01,
                help="ค่าคอมมิชชั่น หรือค่าธรรมเนียมการซื้อ (ถ้าไม่มีใส่ 0)"
            )
            note = st.text_input(
                "โน้ตส่วนตัว (ไม่บังคับ)",
                placeholder="เช่น ซื้อเพราะ AI theme, ตั้งใจถือ 2 ปี"
            )

        asset_map = {"USD": "US_STOCK", "HKD": "HK_STOCK", "THB": "TH_FUND"}
        asset_type = asset_map.get(d["currency"], "US_STOCK")

        cost_preview = quantity * avg_cost + fee
        if quantity > 0:
            st.caption(f"💰 ต้นทุนรวม: {sym}{cost_preview:,.2f} | มูลค่าปัจจุบัน: {sym}{quantity * d['current_price']:,.2f}")

        submitted = st.form_submit_button("✅ เพิ่มในพอร์ต", use_container_width=True, type="primary")
        if submitted:
            if quantity <= 0 or avg_cost <= 0:
                st.error("กรุณากรอกจำนวนและราคาให้ถูกต้อง")
            else:
                payload = {
                    "ticker": d["ticker"],
                    "name": d["name"],
                    "asset_type": asset_type,
                    "currency": d["currency"],
                    "quantity": quantity,
                    "avg_cost": avg_cost,
                    "fee": fee,
                    "bought_at": datetime.combine(bought_at, datetime.min.time()).isoformat(),
                    "note": note or None,
                }
                result = post("/portfolio/positions", payload)
                if result:
                    st.success(f"✅ เพิ่ม {d['ticker']} สำเร็จ!")
                    del st.session_state["lookup"]
                    st.rerun()
                else:
                    st.error("เพิ่มไม่สำเร็จ — เช็คว่า FastAPI server รันอยู่ไหม (python run.py)")

st.divider()

# ─── รายการพอร์ตปัจจุบัน ──────────────────────────────────────────────────────
st.subheader("📋 รายการพอร์ตปัจจุบัน")

data = get("/portfolio/summary")
if not data or not data.get("positions"):
    st.info("ยังไม่มีหุ้นในพอร์ต — ค้นหา Ticker ด้านบนเพื่อเพิ่ม")
    st.stop()

for p in data["positions"]:
    pnl_color = "🟢" if p["pnl"] >= 0 else "🔴"
    sym = p["currency_symbol"]

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 1])
        c1.markdown(f"### {pnl_color} {p['ticker']}")
        c2.markdown(f"**{p['name']}**")
        c3.metric("ราคาปัจจุบัน", f"{sym}{p['current_price']:,.2f}",
                  delta=p["pnl_pct_str"])
        c4.metric("กำไร/ขาดทุน", p["pnl_str"])

        if c5.button("🗑️ ลบ", key=f"del_{p['ticker']}", use_container_width=True):
            positions_raw = get("/portfolio/positions")
            pos_id = next((x["id"] for x in (positions_raw or []) if x["ticker"] == p["ticker"]), None)
            if pos_id and delete(f"/portfolio/positions/{pos_id}"):
                st.success(f"ลบ {p['ticker']} แล้ว")
                st.rerun()
