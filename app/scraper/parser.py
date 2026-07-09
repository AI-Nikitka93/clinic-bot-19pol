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

import re

async def get_doctors_for_specialty(client: httpx.AsyncClient, specialty_url: str) -> List[Dict[str, str]]:
    html = await fetch_html(client, specialty_url)
    soup = BeautifulSoup(html, "html.parser")
    doctors = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "Doctor/SelectDoctor" in href:
            qs = parse_qs(urlparse(href).query)
            doc_id = None
            for k, v in qs.items():
                if k.lower() == "doctorid":
                    doc_id = v[0]
                    break
            if doc_id:
                doctors.append({
                    "id": doc_id,
                    "name": a.get_text(strip=True),
                    "url": urljoin(BASE_URL, href)
                })
    return doctors

async def get_tickets_for_doctor(client: httpx.AsyncClient, doctor_url: str) -> List[Dict[str, Any]]:
    html = await fetch_html(client, doctor_url)
    soup = BeautifulSoup(html, "html.parser")
    
    # Parse month and year
    months_ru = {
        "январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
        "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
    }
    month = 7  # fallback
    year = 2026  # fallback
    
    for element in soup.find_all(string=True):
        text = element.strip()
        clean_text = text.replace('<<', '').replace('>>', '').strip().lower()
        match = re.match(r'([а-яё]+)\s+(\d{4})', clean_text)
        if match:
            m_name, y_val = match.groups()
            if m_name in months_ru:
                month = months_ru[m_name]
                year = int(y_val)
                break
                
    tickets = []
    
    ticket_divs = soup.find_all('div', class_='ticket')
    for div in ticket_divs:
        day_elem = div.find('div', class_='ticket-daynumber')
        if not day_elem:
            continue
        day_text = day_elem.get_text(strip=True)
        if not day_text.isdigit():
            continue
        day = int(day_text)
        
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        
        links = div.find_all('a')
        for a in links:
            onclick = a.get('onclick', '')
            match = re.search(r'orderTicket\((\d+)\)', onclick)
            if match:
                t_id = match.group(1)
                t_time = a.get_text(strip=True)
                tickets.append({
                    "id": t_id,
                    "date": date_str,
                    "time": t_time
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
                    "tickets": {t["id"]: f"{t['date']} {t['time']}" for t in tix}
                }
    return state
