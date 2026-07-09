import asyncio
import httpx
from bs4 import BeautifulSoup

async def main():
    async with httpx.AsyncClient() as client:
        res = await client.get('http://self.19crp.by:8028/ticket/')
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # We need to find how specialties are listed
        print("--- HTML BODY ---")
        print(soup.body.text[:2000] if soup.body else "No body")
        print("--- LINKS ---")
        for a in soup.find_all('a'):
            print(a.get('href'), a.text.strip())

if __name__ == '__main__':
    asyncio.run(main())
