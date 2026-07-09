# Clinic Ticket Monitoring System

## Architecture Description
This project is a microservices-based monitoring system for tracking ticket availability at clinics.
It consists of:
1. **API Service** (FastAPI + SQLAdmin): Admin dashboard for monitoring users, tickets, and system health.
2. **Scraper Service**: A background worker that polls the target clinic site for tickets and calculates differences (diffs).
3. **Telegram Bot Service** (Aiogram 3.x): Handles user registration, subscriptions for specific specialties/doctors, and receives updates from the system when new tickets appear.
4. **PostgreSQL**: Primary data store for users, subscriptions, doctors, and history logs.
5. **Redis**: Cache to store old scraping states, facilitating fast diffing to find newly available tickets.

## Serverless Architecture Setup
We have migrated to a serverless architecture using Vercel, Neon DB, Upstash Redis, and GitHub Actions.

### 1. Database (Neon)
- Create a PostgreSQL database on Neon.
- Get your `DATABASE_URL` connection string.

### 2. Redis (Upstash)
- Create a Redis database on Upstash.
- Get your `REDIS_URL` connection string (make sure it starts with `redis://` or `rediss://`).

### 3. API and Bot (Vercel)
- Import your repository to Vercel.
- The project includes a `vercel.json` file for routing.
- Set the following Environment Variables in your Vercel Project Settings:
  - `DATABASE_URL`: Your Neon database URL.
  - `REDIS_URL`: Your Upstash Redis URL.
  - `BOT_TOKEN`: Your Telegram Bot token from BotFather.
- Deploy the project. The API Admin Panel will be available at `/admin` and the bot will be served via webhooks.

### 4. Scraper (GitHub Actions)
- The scraper runs as a scheduled background job using GitHub Actions.
- Go to your repository settings -> Secrets and variables -> Actions.
- Add the following Repository Secrets:
  - `DATABASE_URL`
  - `REDIS_URL`
  - `BOT_TOKEN`
- The scraper will automatically run every 5 minutes based on `.github/workflows/scraper.yml`. You can also trigger it manually from the Actions tab.

## Admin Panel
Once the application is running on Vercel, the FastAPI server exposes an Admin Panel.
- URL: `https://<your-vercel-domain>/admin`
- It provides a web interface to inspect Users, Sources, Specialties, Doctors, Tickets, Subscriptions, and History Logs.

## Telegram Bot
- Users can text the bot (`/start`) to register.
- Users can subscribe to doctors or specialties to receive immediate push notifications when new tickets become available.
