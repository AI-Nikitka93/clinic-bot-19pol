from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from sqladmin import Admin
from app.core.database import engine
from app.api.admin import (
    UserAdmin, SourceAdmin, SpecialtyAdmin, DoctorAdmin, TicketAdmin, 
    SubscriptionAdmin, HistoryLogAdmin, DashboardView
)
from app.bot.main import bot, dp, set_webhook
from aiogram.types import Update

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

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_webhook_update(bot, update)
    return {"ok": True}
