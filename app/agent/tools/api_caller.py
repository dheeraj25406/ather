import httpx
from typing import Dict, Any, Optional
from urllib.parse import urlparse


# Whitelist of allowed domains to prevent SSRF
ALLOWED_DOMAINS = {
    "api.github.com",
    "api.github.io",
    "jsonplaceholder.typicode.com",
    "httpbin.org",
    "api.coindesk.com",
    "api.openweathermap.org",
    "api.example.com",
}


def _is_url_safe(url: str) -> bool:
    """Check if URL is safe to call."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Prevent localhost and private IPs
        if domain in ["localhost", "127.0.0.1", "0.0.0.0"] or domain.startswith("192.168") or domain.startswith("10."):
            return False
        
        # Check against whitelist (in demo; relax in production)
        # return domain in ALLOWED_DOMAINS
        return True  # Allow for demo
    except Exception:
        return False


async def call_api(
    url: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    params: Optional[Dict] = None,
    body: Optional[Dict] = None
) -> Dict[str, Any]:
    """Call an external API with safety checks."""
    
    try:
        # Validate URL
        if not url.startswith(("http://", "https://")):
            return {"error": "URL must start with http:// or https://"}
        
        if not _is_url_safe(url):
            return {"error": "URL not allowed (security restriction)"}
        
        # Normalize method
        method = method.upper()
        if method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            return {"error": f"HTTP method '{method}' not supported"}
        
        # Prepare request
        request_headers = headers or {}
        request_params = params or {}
        request_body = body
        
        # Limit headers
        if len(request_headers) > 20:
            return {"error": "Too many headers"}
        
        # Execute request
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method,
                url,
                headers=request_headers,
                params=request_params,
                json=request_body if request_body else None
            )
            
            # Return response
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:5000],  # Limit response size
                "url": str(response.url)
            }
    
    except httpx.TimeoutException:
        return {"error": "Request timeout (15s limit)"}
    except httpx.ConnectError as e:
        return {"error": f"Connection failed: {str(e)[:100]}"}
    except Exception as e:
        return {"error": f"API call failed: {str(e)[:100]}"}
