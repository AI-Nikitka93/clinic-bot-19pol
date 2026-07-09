from fastapi import FastAPI, Request, HTTPException, status
from contextlib import asynccontextmanager
from sqladmin import Admin
from app.core.database import engine
from app.api.admin import (
    UserAdmin, SourceAdmin, SpecialtyAdmin, DoctorAdmin, TicketAdmin, 
    SubscriptionAdmin, HistoryLogAdmin, DashboardView
)
from app.bot.main import bot, dp, set_webhook
from aiogram.types import Update
from app.scraper.tasks import run_scraper_job

@asynccontextmanager
async def lifespan(app: FastAPI):
    await set_webhook()
    yield

app = FastAPI(title="Clinic Ticket Monitoring System", lifespan=lifespan)

admin = Admin(app, engine, templates_dir="app/templates")

admin.add_view(DashboardView)
admin.add_view(UserAdmin)
admin.add_view(SourceAdmin)
admin.add_view(SpecialtyAdmin)
admin.add_view(DoctorAdmin)
admin.add_view(TicketAdmin)
admin.add_view(SubscriptionAdmin)
admin.add_view(HistoryLogAdmin)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/cron/scrape")
async def trigger_scrape(key: str):
    if key != "5YkVoxpU9cGjlUiEOcT98uDghR38i4EQ3RjWFtdFv+k=":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron key"
        )
    try:
        await run_scraper_job()
        return {"status": "success", "message": "Scraper job completed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_webhook_update(bot, update)
    return {"ok": True}
