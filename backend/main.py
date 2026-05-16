from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.database import init_db
from backend.config import get_settings
from backend.api import portfolio, analysis, line_webhook
from backend.scheduler.alerts import (
    run_morning_brief,
    run_hk_preopen,
    run_hk_midsession,
    run_hk_close,
    run_us_preopen,
    run_price_alert_check,
    run_weekly_review,
)

settings = get_settings()


def _build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Bangkok")

    # 08:00 — Morning Brief (ทุกวัน จ-ศ)
    scheduler.add_job(run_morning_brief, CronTrigger(day_of_week="mon-fri", hour=8, minute=0), id="morning_brief")

    # 09:00 — HK Pre-open
    scheduler.add_job(run_hk_preopen, CronTrigger(day_of_week="mon-fri", hour=9, minute=0), id="hk_preopen")

    # 12:30 — HK Mid-session
    scheduler.add_job(run_hk_midsession, CronTrigger(day_of_week="mon-fri", hour=12, minute=30), id="hk_mid")

    # 15:15 — HK Close
    scheduler.add_job(run_hk_close, CronTrigger(day_of_week="mon-fri", hour=15, minute=15), id="hk_close")

    # 21:00 — US Pre-open
    scheduler.add_job(run_us_preopen, CronTrigger(day_of_week="mon-fri", hour=21, minute=0), id="us_preopen")

    # ทุก 10 นาที — Price Alert (ช่วงตลาดเปิดเท่านั้น ฟังก์ชันตรวจเองภายใน)
    scheduler.add_job(run_price_alert_check, CronTrigger(day_of_week="mon-fri", minute="*/10"), id="price_alert")

    # จันทร์ 08:30 — Weekly Review
    scheduler.add_job(run_weekly_review, CronTrigger(day_of_week="mon", hour=8, minute=30), id="weekly_review")

    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = _build_scheduler()
    scheduler.start()
    print("[Scheduler] Jobs ที่ลงทะเบียน:")
    for job in scheduler.get_jobs():
        print(f"  • {job.id} — {job.trigger}")
    yield
    scheduler.shutdown()


app = FastAPI(
    title="NexStock API",
    description="Portfolio Intelligence & Stock Discovery System — Phase 1",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(analysis.router)
app.include_router(line_webhook.router)


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "app": "NexStock Phase 1"}


@app.get("/scheduler/jobs", tags=["scheduler"], summary="ดู jobs ที่ตั้งเวลาไว้ทั้งหมด")
async def list_jobs():
    from backend.main import app as current_app
    return {"jobs": ["morning_brief 08:00", "hk_preopen 09:00", "hk_mid 12:30",
                     "hk_close 15:15", "us_preopen 21:00", "price_alert */10min", "weekly_review จันทร์ 08:30"]}


# ─── Manual trigger endpoints สำหรับทดสอบ ───────────────────────────────────

@app.post("/trigger/morning-brief", tags=["trigger"], summary="ทดสอบ Morning Brief")
async def trigger_morning(): await run_morning_brief(); return {"ok": True}

@app.post("/trigger/hk-preopen", tags=["trigger"], summary="ทดสอบ HK Pre-open")
async def trigger_hk_pre(): await run_hk_preopen(); return {"ok": True}

@app.post("/trigger/hk-midsession", tags=["trigger"], summary="ทดสอบ HK Mid-session")
async def trigger_hk_mid(): await run_hk_midsession(); return {"ok": True}

@app.post("/trigger/hk-close", tags=["trigger"], summary="ทดสอบ HK Close")
async def trigger_hk_close(): await run_hk_close(); return {"ok": True}

@app.post("/trigger/us-preopen", tags=["trigger"], summary="ทดสอบ US Pre-open")
async def trigger_us_pre(): await run_us_preopen(); return {"ok": True}

@app.post("/trigger/price-alert", tags=["trigger"], summary="ทดสอบ Price Alert check")
async def trigger_price(): await run_price_alert_check(); return {"ok": True}

@app.post("/trigger/weekly-review", tags=["trigger"], summary="ทดสอบ Weekly Review")
async def trigger_weekly(): await run_weekly_review(); return {"ok": True}
