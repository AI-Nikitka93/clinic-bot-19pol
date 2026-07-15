from fastapi import FastAPI, Request, HTTPException, status, Header
from contextlib import asynccontextmanager
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from app.core.config import settings
from app.core.database import engine
from app.api.admin import (
    UserAdmin, SourceAdmin, SpecialtyAdmin, DoctorAdmin, TicketAdmin, 
    SubscriptionAdmin, HistoryLogAdmin, DashboardView
)
from app.bot.main import bot, dp, set_webhook
from aiogram.types import Update
from app.scraper.tasks import run_scraper_job
import os
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    # await set_webhook() # Disabled to prevent Telegram rate-limits on Vercel ephemeral boots
    yield

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        password = form.get("password")
        if password == settings.ADMIN_SECRET:
            request.session.update({"token": "admin_token"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False
        return True

authentication_backend = AdminAuth(secret_key=settings.ADMIN_SECRET)

app = FastAPI(title="Clinic Ticket Monitoring System", lifespan=lifespan)

admin = Admin(app, engine, templates_dir="app/templates", authentication_backend=authentication_backend)

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
    if key != settings.CRON_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron key"
        )
        
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GITHUB_TOKEN is not configured on server"
        )
        
    # Trigger workflow_dispatch in GitHub Actions
    url = "https://api.github.com/repos/AI-Nikitka93/clinic-bot-19pol/actions/workflows/scraper.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FastAPI-App"
    }
    data = {
        "ref": "master"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=data, timeout=10.0)
            if resp.status_code != 204:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"GitHub API returned {resp.status_code}: {resp.text}"
                )
            return {"status": "success", "message": "Scraper workflow triggered successfully on GitHub Actions"}
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to GitHub API: {str(e)}"
            )

@app.post("/api/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_webhook_update(bot, update)
    return {"ok": True}
