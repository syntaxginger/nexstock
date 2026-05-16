import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from streamlit_app.api_client import get, post

st.set_page_config(page_title="NexStock", page_icon="📈", layout="wide")

st.title("📈 NexStock Dashboard")
st.caption("Portfolio Intelligence & Stock Discovery System")

# ─── ดึงข้อมูลพอร์ต ──────────────────────────────────────────────────────────
data = get("/portfolio/summary")

if not data or not data.get("positions"):
    st.info("ยังไม่มีหุ้นในพอร์ต — ไปที่หน้า **Portfolio** เพื่อเพิ่มหุ้น")
    st.stop()

positions = data["positions"]
total_pnl = data.get("total_pnl_by_currency", {})
df = pd.DataFrame(positions)

# ─── Metric cards ─────────────────────────────────────────────────────────────
st.subheader("ภาพรวมพอร์ต")
cols = st.columns(len(total_pnl) + 1)

cols[0].metric("จำนวนหุ้น/กองทุน", f"{len(positions)} ตัว")
for i, (cur, pnl) in enumerate(total_pnl.items()):
    symbol = {"USD": "$", "HKD": "HK$", "THB": "฿"}.get(cur, "")
    cols[i + 1].metric(
        f"P&L รวม ({cur})",
        f"{symbol}{abs(pnl):,.2f}",
        delta=f"{'+' if pnl >= 0 else ''}{symbol}{pnl:,.2f}",
    )

st.divider()

# ─── ตาราง P&L ────────────────────────────────────────────────────────────────
st.subheader("รายละเอียดแต่ละตัว")

display_df = df[[
    "ticker", "name", "currency", "quantity",
    "avg_cost", "current_price", "current_value", "pnl_str", "pnl_pct_str"
]].rename(columns={
    "ticker": "Ticker",
    "name": "ชื่อ",
    "currency": "สกุลเงิน",
    "quantity": "จำนวน",
    "avg_cost": "ราคาทุน",
    "current_price": "ราคาปัจจุบัน",
    "current_value": "มูลค่ารวม",
    "pnl_str": "กำไร/ขาดทุน",
    "pnl_pct_str": "% เปลี่ยน",
})

def color_pnl(val: str):
    if val.startswith("+"):
        return "color: #22c55e; font-weight: bold"
    elif val.startswith("-"):
        return "color: #ef4444; font-weight: bold"
    return ""

styled = display_df.style.map(color_pnl, subset=["กำไร/ขาดทุน", "% เปลี่ยน"])
st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ─── Charts ───────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("สัดส่วนพอร์ต (มูลค่า)")
    fig_pie = px.pie(
        df,
        names="ticker",
        values="current_value",
        color_discrete_sequence=px.colors.qualitative.Set3,
        hole=0.4,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.subheader("กำไร/ขาดทุน รายตัว")
    df["color"] = df["pnl"].apply(lambda x: "#22c55e" if x >= 0 else "#ef4444")
    fig_bar = go.Figure(go.Bar(
        x=df["ticker"],
        y=df["pnl"],
        marker_color=df["color"],
        text=df["pnl_str"],
        textposition="outside",
    ))
    fig_bar.update_layout(
        yaxis_title="P&L",
        xaxis_title="",
        margin=dict(t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ─── Trigger alerts ───────────────────────────────────────────────────────────
st.subheader("ส่ง Alert ทันที")
cols2 = st.columns(4)

alerts = [
    ("🌅 Morning Brief", "/trigger/morning-brief"),
    ("🇭🇰 HK Pre-open", "/trigger/hk-preopen"),
    ("🇺🇸 US Pre-open", "/trigger/us-preopen"),
    ("📅 Weekly Review", "/trigger/weekly-review"),
]

for col, (label, path) in zip(cols2, alerts):
    if col.button(label, use_container_width=True):
        with st.spinner("กำลังส่ง..."):
            result = post(path, {})
        if result:
            st.success(f"ส่ง {label} แล้ว — ตรวจสอบ LINE หรือ console")
        else:
            st.error("ส่งไม่สำเร็จ — เช็คว่า server รันอยู่ไหม")
