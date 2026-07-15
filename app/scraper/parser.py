import httpx
import asyncio
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
                url = urljoin(BASE_URL, href)
                if url.startswith(BASE_URL):
                    specialties.append({
                        "id": job_id,
                        "name": a.get_text(strip=True),
                        "url": url
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
                url = urljoin(BASE_URL, href)
                if url.startswith(BASE_URL):
                    doctors.append({
                        "id": doc_id,
                        "name": a.get_text(strip=True),
                        "url": url
                    })
    return doctors

async def get_tickets_for_doctor(client: httpx.AsyncClient, doctor_url: str) -> List[Dict[str, Any]]:
    from datetime import datetime
    current_year = datetime.now().year
    current_month = datetime.now().month
    tickets = []

    for offset in range(5): # Check 5 weeks ahead (up to 35 days)
        url = doctor_url
        if "?" in url:
            url += f"&Offset={offset}"
        else:
            url += f"?Offset={offset}"

        html = await fetch_html(client, url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Parse month and year
        months_ru = {
            "январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
            "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
        }
        month = current_month
        year = current_year
        
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

async def fetch_free_proxies() -> List[str]:
    proxies = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get("https://proxylist.geonode.com/api/proxy-list?country=BY&limit=10&protocols=http%2Chttps")
            if res.status_code == 200:
                data = res.json()
                for item in data.get("data", []):
                    proxies.append(f"http://{item['ip']}:{item['port']}")
        except Exception as e:
            logger.error(f"Geonode API error: {e}")
            
        try:
            res = await client.get("https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=BY")
            if res.status_code == 200:
                for line in res.text.splitlines():
                    if line.strip():
                        proxies.append(f"http://{line.strip()}")
        except Exception as e:
            logger.error(f"ProxyScrape API error: {e}")
            
    return list(set(proxies))

async def scrape_all_tickets(use_proxy_fallback: bool = False) -> Dict[str, Any]:
    state = {}
    sem = asyncio.Semaphore(5)  # Limit concurrent requests to prevent clinic website block
    
    proxies_to_try = [None]
    if use_proxy_fallback:
        logger.info("VPN not found. Fetching free proxies for fallback...")
        free_proxies = await fetch_free_proxies()
        logger.info(f"Found {len(free_proxies)} free BY proxies.")
        if free_proxies:
            proxies_to_try = free_proxies
        else:
            logger.error("No free proxies found. Cannot proceed without BY IP.")
            return {}

    for proxy in proxies_to_try:
        try:
            logger.info(f"Attempting to scrape using proxy: {proxy}")
            async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
                # Test connection first
                await fetch_html(client, BASE_URL)
                logger.info(f"Connection successful using proxy {proxy}")
                
                specialties = await get_specialties(client)
                
                async def fetch_doctor_tickets(spec_name, doc):
                    async with sem:
                        try:
                            tix = await get_tickets_for_doctor(client, doc["url"])
                            return spec_name, doc["name"], doc["id"], tix
                        except Exception as e:
                            logger.error(f"Error fetching tickets for doctor {doc['name']}: {e}")
                            return spec_name, doc["name"], doc["id"], None

                tasks = []
                for spec in specialties:
                    state[spec["name"]] = {"id": spec["id"], "doctors": {}}
                    try:
                        docs = await get_doctors_for_specialty(client, spec["url"])
                        for doc in docs:
                            tasks.append(fetch_doctor_tickets(spec["name"], doc))
                    except Exception as e:
                        logger.error(f"Error fetching doctors for specialty {spec['name']}: {e}")
                        
                results = await asyncio.gather(*tasks)
                
                for spec_name, doc_name, doc_id, tix in results:
                    if tix is None:
                        continue
                    state[spec_name]["doctors"][doc_name] = {
                        "id": doc_id,
                        "tickets": {t["id"]: f"{t['date']} {t['time']}" for t in tix}
                    }
                    
                # If we reached here, parsing succeeded!
                return state
        except Exception as e:
            logger.warning(f"Proxy {proxy} failed or blocked: {e}")
            continue

    logger.error("All proxies failed to connect.")
    return {}
