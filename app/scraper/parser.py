import httpx
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, parse_qs, urlparse

logger = logging.getLogger(__name__)

BASE_URL = "http://self.19crp.by:8028/ticket/"

async def fetch_html(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.text

async def get_specialties(client: httpx.AsyncClient) -> List[Dict[str, str]]:
    html = await fetch_html(client, BASE_URL)
    soup = BeautifulSoup(html, "html.parser")
    specialties = []
    
    # We look for links pointing to /ticket/Job/SelectJob?jobId=...
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "Job/SelectJob" in href:
            qs = parse_qs(urlparse(href).query)
            job_id = qs.get("jobId", [None])[0]
            if job_id:
                specialties.append({
                    "id": job_id,
                    "name": a.get_text(strip=True),
                    "url": urljoin(BASE_URL, href)
                })
    return specialties

async def get_doctors_for_specialty(client: httpx.AsyncClient, specialty_url: str) -> List[Dict[str, str]]:
    # Example logic: we go to specialty_url and find links to doctors
    # e.g. /ticket/Doctor/SelectDoctor?doctorId=...
    html = await fetch_html(client, specialty_url)
    soup = BeautifulSoup(html, "html.parser")
    doctors = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "Doctor/SelectDoctor" in href:
            qs = parse_qs(urlparse(href).query)
            doc_id = qs.get("doctorId", [None])[0]
            if doc_id:
                doctors.append({
                    "id": doc_id,
                    "name": a.get_text(strip=True),
                    "url": urljoin(BASE_URL, href)
                })
    return doctors

async def get_tickets_for_doctor(client: httpx.AsyncClient, doctor_url: str) -> List[Dict[str, Any]]:
    # Mocking implementation as we couldn't explore further dynamically.
    # Usually it lists dates, and inside dates, it lists tickets.
    # In a real scenario, this would parse out the actual ticket slots.
    html = await fetch_html(client, doctor_url)
    soup = BeautifulSoup(html, "html.parser")
    tickets = []
    # Hypothetical ticket link /ticket/Ticket/SelectTicket?ticketId=...
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "Ticket/Select" in href or "ticketId" in href:
            qs = parse_qs(urlparse(href).query)
            ticket_id = qs.get("ticketId", [None])[0]
            if ticket_id:
                tickets.append({
                    "id": ticket_id,
                    "time": a.get_text(strip=True),
                    "url": urljoin(BASE_URL, href)
                })
    return tickets

async def scrape_all_tickets() -> Dict[str, Any]:
    state = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        specialties = await get_specialties(client)
        for spec in specialties:
            docs = await get_doctors_for_specialty(client, spec["url"])
            state[spec["name"]] = {"id": spec["id"], "doctors": {}}
            for doc in docs:
                tix = await get_tickets_for_doctor(client, doc["url"])
                state[spec["name"]]["doctors"][doc["name"]] = {
                    "id": doc["id"],
                    "tickets": {t["id"]: t["time"] for t in tix}
                }
    return state
