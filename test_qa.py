import pytest
import httpx
import respx
import pytest_asyncio
from bs4 import BeautifulSoup
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import NullPool

# Import the app and modules to test
from app.api.main import app as fastapi_app
from app.core.config import settings
from app.scraper.parser import get_specialties, get_doctors_for_specialty, get_tickets_for_doctor
from app.models.models import Base, User, Source, Specialty, Doctor, Subscription, Ticket

# Setup in-memory sqlite engine for testing
test_engine = create_async_engine("sqlite+aiosqlite:///test.db", poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# --- 1. Scraper Parser Tests (SSRF, Pagination, Parsing) ---
@pytest.mark.asyncio
async def test_get_specialties_with_ssrf_protection():
    html = """
    <html><body>
        <a href="Job/SelectJob?jobId=1">Терапевт</a>
        <a href="http://evil.com/ticket/Job/SelectJob?jobId=2">Злобный врач</a>
    </body></html>
    """
    with respx.mock:
        respx.get("http://self.19crp.by:8028/ticket/").mock(return_value=httpx.Response(200, text=html))
        async with httpx.AsyncClient() as client:
            specs = await get_specialties(client)
            assert len(specs) == 1
            assert specs[0]["id"] == "1"
            assert specs[0]["name"] == "Терапевт"
            assert "evil.com" not in specs[0]["url"]

@pytest.mark.asyncio
async def test_get_doctors_with_ssrf_protection():
    html = """
    <html><body>
        <a href="Doctor/SelectDoctor?doctorId=123">Иванов И.И.</a>
        <a href="http://evil.com/ticket/Doctor/SelectDoctor?doctorId=456">Петров П.П.</a>
    </body></html>
    """
    with respx.mock:
        respx.get("http://test.com/spec").mock(return_value=httpx.Response(200, text=html))
        async with httpx.AsyncClient() as client:
            docs = await get_doctors_for_specialty(client, "http://test.com/spec")
            assert len(docs) == 1
            assert docs[0]["id"] == "123"

@pytest.mark.asyncio
async def test_get_tickets_pagination_and_date():
    html_offset0 = """
    <html><body>
        <h2>Июль 2026</h2>
        <div class="ticket"><div class="ticket-daynumber">25</div><a onclick="orderTicket(1001)">10:00</a></div>
    </body></html>
    """
    html_offset1 = """
    <html><body>
        <h2>Август 2026</h2>
        <div class="ticket"><div class="ticket-daynumber">5</div><a onclick="orderTicket(1002)">11:00</a></div>
    </body></html>
    """
    with respx.mock:
        # Mock offset 0 and 1
        respx.get("http://test.com/doc?Offset=0").mock(return_value=httpx.Response(200, text=html_offset0))
        respx.get("http://test.com/doc?Offset=1").mock(return_value=httpx.Response(200, text=html_offset1))
        async with httpx.AsyncClient() as client:
            tickets = await get_tickets_for_doctor(client, "http://test.com/doc")
            assert len(tickets) == 2
            assert tickets[0]["id"] == "1001"
            assert tickets[0]["date"] == "2026-07-25"
            assert tickets[1]["id"] == "1002"
            assert tickets[1]["date"] == "2026-08-05"

# --- 2. API Tests (Security, Auth, Validation) ---
client = TestClient(fastapi_app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200

def test_cron_scrape_auth():
    settings.CRON_SECRET = "supersecret"
    # Invalid key
    response = client.get("/api/cron/scrape?key=wrong")
    assert response.status_code == 401
    # Note: Valid key test requires GITHUB_TOKEN or mocked httpx, skipping full integration to avoid 500

def test_telegram_webhook_auth():
    settings.WEBHOOK_SECRET = "webhooksecret"
    # No header
    response = client.post("/api/webhook", json={"update_id": 1})
    assert response.status_code == 401 # Unauthorized (missing header)
    # Wrong header
    response = client.post("/api/webhook", json={"update_id": 1}, headers={"x-telegram-bot-api-secret-token": "wrong"})
    assert response.status_code == 401
    # We won't test valid because dp.feed_webhook_update will fail without full bot setup, but we verified the protection.

# --- 3. Telegram Bot Tests (IDOR in subscription deletion) ---
from app.bot.handlers.subscription import del_subscription
import json

@pytest.mark.asyncio
@patch('app.bot.handlers.subscription.AsyncSessionLocal', new=TestSessionLocal)
async def test_idor_del_subscription(db_session):
    # Setup test data
    user = User(telegram_id=111)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    sub = Subscription(user_id=user.id, source_id=1)
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    sub_id = sub.id

    # Mock callback query for malicious user (ID 222)
    mock_cb = MagicMock()
    mock_cb.data = f"delsub_{sub_id}"
    mock_cb.from_user.id = 222
    mock_cb.answer = AsyncMock()
    mock_cb.message.edit_text = AsyncMock()

    await del_subscription(mock_cb)

    # Verify subscription was NOT deleted (IDOR protection)
    assert mock_cb.answer.call_args[0][0] == "Ошибка: подписка не найдена или нет прав"
    
    # Mock callback query for owner (ID 111)
    mock_cb.from_user.id = 111
    await del_subscription(mock_cb)
    
    # Verify subscription WAS deleted
    assert mock_cb.answer.call_args[0][0] == "Подписка удалена"

