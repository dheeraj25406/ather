import httpx
from typing import Dict, Any
import re
from urllib.parse import unquote, urlparse, parse_qs


async def web_search(query: str, max_results: int = 5, **kwargs) -> Dict[str, Any]:
    """Search the web using DuckDuckGo HTML search results with snippets."""
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}

        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            html = response.text

        items = []

        # Extract each result block: link + snippet
        result_blocks = re.findall(
            r'<div[^>]*class="result[^"]*"[^>]*>(.*?)</div>\s*</div>',
            html, re.DOTALL | re.IGNORECASE
        )

        for block in result_blocks:
            if len(items) >= max_results:
                break

            # Extract link and title
            link_match = re.search(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                block, re.DOTALL | re.IGNORECASE
            )
            if not link_match:
                continue

            link = link_match.group(1)
            title = re.sub(r'<.*?>', '', link_match.group(2)).strip()

            # Extract snippet
            snippet_match = re.search(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                block, re.DOTALL | re.IGNORECASE
            )
            snippet = ""
            if snippet_match:
                snippet = re.sub(r'<.*?>', '', snippet_match.group(1)).strip()

            # Resolve DuckDuckGo redirect URLs
            if link.startswith("//") or link.startswith("/l/"):
                full = ("https:" + link) if link.startswith("//") else link
                parsed = urlparse(full)
                qs = parse_qs(parsed.query)
                uddg = qs.get("uddg")
                if uddg:
                    link = unquote(uddg[0])

            items.append({"title": title, "url": link, "snippet": snippet})

        # Fallback: old pattern if block parsing found nothing
        if not items:
            pattern = re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL
            )
            for match in pattern.finditer(html):
                if len(items) >= max_results:
                    break
                link = match.group(1)
                title = re.sub(r'<.*?>', '', match.group(2)).strip()
                if link.startswith("//") or link.startswith("/l/"):
                    full = ("https:" + link) if link.startswith("//") else link
                    parsed = urlparse(full)
                    qs = parse_qs(parsed.query)
                    uddg = qs.get("uddg")
                    if uddg:
                        link = unquote(uddg[0])
                items.append({"title": title, "url": link, "snippet": ""})

        return {
            "query": query,
            "source": "DuckDuckGo",
            "results": items,
            "count": len(items)
        }
    except Exception as e:
        return {"error": f"Search failed: {str(e)}", "query": query}

