import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any
import re

MAIN_TAGS = [
    {'name': 'main'},
    {'name': 'article'},
    {'name': 'section'},
    {'name': 'div', 'attrs': {'id': re.compile(r'(main|content|body|article|news|score)', re.I)}},
    {'name': 'div', 'attrs': {'class': re.compile(r'(main|content|body|article|news|score)', re.I)}},
]

async def web_crawl(url: str, max_length: int = 3000) -> Dict[str, Any]:
    """Intelligent web crawler: extract main content, largest text block, and fallback to visible text."""
    try:
        print(f"[web_crawl] Fetching URL: {url}")
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url)
            print(f"[web_crawl] Status code: {response.status_code}")
            response.raise_for_status()
            html = response.text
        print(f"[web_crawl] HTML length: {len(html)}")
        soup = BeautifulSoup(html, "html.parser")

        # 1. Try main content tags
        for tag in MAIN_TAGS:
            found = soup.find(**tag)
            if found:
                print(f"[web_crawl] Found main content tag: {tag}")
                text = found.get_text(separator=' ', strip=True)
                if len(text) > 100:
                    text = text[:max_length]
                    return {"url": url, "content": text, "strategy": f"main:{tag}"}

        # 2. Find the largest text block (most informative for arbitrary pages)
        def largest_text_block(soup):
            candidates = []
            for tag in soup.find_all(['div', 'section', 'article', 'main', 'p']):
                txt = tag.get_text(separator=' ', strip=True)
                if len(txt) > 100:
                    candidates.append((len(txt), txt, tag.name))
            if candidates:
                candidates.sort(reverse=True)
                print(f"[web_crawl] Largest text block: {candidates[0][2]}, length={candidates[0][0]}")
                return candidates[0][1][:max_length]
            return None
        block = largest_text_block(soup)
        if block:
            return {"url": url, "content": block, "strategy": "largest-block"}

        # 3. Fallback: all visible text, remove scripts/styles/etc
        for tag in soup(['script', 'style', 'noscript', 'header', 'footer', 'nav', 'form', 'svg']):
            tag.decompose()
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        print(f"[web_crawl] Fallback text length: {len(text)}")
        text = text[:max_length]
        return {"url": url, "content": text, "strategy": "fallback"}
    except Exception as e:
        print(f"[web_crawl] Exception: {e}")
        return {"error": f"Crawl failed: {str(e)}", "url": url}
