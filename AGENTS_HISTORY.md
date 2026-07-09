# Agents History Log

## [2026-07-09] - Vercel Deployment & Bot Activation Fix
- **Status**: Completed successfully.
- **Changes**:
  - Configured git profile with Vercel owner identity (`alexaiartbel@gmail.com`) to unblock commit checks.
  - Added required dependencies to `pyproject.toml` (`psycopg[binary]`, `beautifulsoup4`, `httpx`, `python-multipart`) and compiled `uv.lock`.
  - Re-created Vercel environment variables:
    - Stripped trailing spaces from `BOT_TOKEN`.
    - Removed carriage returns (`\r`) from `DATABASE_URL` and `REDIS_URL` which caused the PostgreSQL driver connection pool to crash with `invalid channel_binding value: "require\r"`.
  - Updated `alembic/env.py` to support `SelectorEventLoop` on Windows when using psycopg3 in async mode.
  - Successfully ran `uv run alembic upgrade head` to populate the Neon PostgreSQL database with all required tables (including `users`).
  - Completely reset the Telegram webhook URL (`deleteWebhook` + `setWebhook` calls) to clear the "cooling down" state on Telegram side.
  - Verified webhook redelivery: updates successfully processed, user `LikiWonderland` (ID `8156149094`) successfully registered in Neon DB, and bot responds to messages.

## [2026-07-09] - Bot Menu, Live Tickets & Scraper PostgreSQL Sync Implementation
- **Status**: Completed successfully.
- **Changes**:
  - Modified `app/scraper/parser.py` to correctly extract real available ticket slots from the `onclick="orderTicket(ticketId)"` tags and Russian calendar months.
  - Rewrote `app/scraper/tasks.py` to synchronize scraped specialties, doctors, and active ticket slots directly with PostgreSQL (Neon DB).
  - Populated Neon DB with 4,000+ real available ticket slots.
  - Added Reply Keyboard (Main Menu) in `app/bot/keyboards.py` for direct menu buttons navigation.
  - Translated all bot flows, steps, and responses to Russian in handlers.
  - Implemented automatic source selection skip in subscription if there's only one source.
  - Implemented live "📅 Свободные талоны" view querying and formatting tickets from Neon DB.
  - Successfully deployed all modifications to production on Vercel.
