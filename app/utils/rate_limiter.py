"""
Rate limiter for Gemini API calls to stay within free tier limits.
"""

import asyncio
import time
from typing import Dict, Any
from collections import deque

class GeminiRateLimiter:
    """Rate limiter for Gemini API calls (10 requests per minute)."""
    
    def __init__(self, max_requests_per_minute: int = 10):
        self.max_requests = max_requests_per_minute
        self.requests = deque()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make an API call, waiting if necessary."""
        async with self.lock:
            now = time.time()
            
            # Remove requests older than 1 minute
            while self.requests and now - self.requests[0] > 60:
                self.requests.popleft()
            
            # If we're at the limit, wait until we can make another request
            if len(self.requests) >= self.max_requests:
                # Calculate how long to wait
                oldest_request = self.requests[0]
                wait_time = 60 - (now - oldest_request) + 1  # Add 1 second buffer
                
                if wait_time > 0:
                    print(f"⏳ Rate limit reached. Waiting {wait_time:.1f}s before next Gemini call...")
                    await asyncio.sleep(wait_time)
                    
                    # Remove old requests again after waiting
                    now = time.time()
                    while self.requests and now - self.requests[0] > 60:
                        self.requests.popleft()
            
            # Record this request
            self.requests.append(now)
            print(f"🤖 Gemini API call {len(self.requests)}/{self.max_requests} in current minute")

# Global rate limiter instance
gemini_rate_limiter = GeminiRateLimiter()


# Static site cache to reduce LLM calls for site discovery
STATIC_SITE_CACHE = {
    "US": [
        {"domain": "amazon.com", "base_url": "https://www.amazon.com"},
        {"domain": "bestbuy.com", "base_url": "https://www.bestbuy.com"},
        {"domain": "target.com", "base_url": "https://www.target.com"},
        {"domain": "walmart.com", "base_url": "https://www.walmart.com"},
        {"domain": "apple.com", "base_url": "https://www.apple.com"},
        {"domain": "verizon.com", "base_url": "https://www.verizon.com"},
        {"domain": "att.com", "base_url": "https://www.att.com"},
        {"domain": "costco.com", "base_url": "https://www.costco.com"},
    ],
    "GB": [
        {"domain": "amazon.co.uk", "base_url": "https://www.amazon.co.uk"},
        {"domain": "johnlewis.com", "base_url": "https://www.johnlewis.com"},
        {"domain": "argos.co.uk", "base_url": "https://www.argos.co.uk"},
        {"domain": "currys.co.uk", "base_url": "https://www.currys.co.uk"},
        {"domain": "very.co.uk", "base_url": "https://www.very.co.uk"},
        {"domain": "ebay.co.uk", "base_url": "https://www.ebay.co.uk"},
        {"domain": "apple.com", "base_url": "https://www.apple.com"},
        {"domain": "carphonewarehouse.com", "base_url": "https://www.carphonewarehouse.com"},
    ],
    "IN": [
        {"domain": "amazon.in", "base_url": "https://www.amazon.in"},
        {"domain": "flipkart.com", "base_url": "https://www.flipkart.com"},
        {"domain": "reliancedigital.in", "base_url": "https://www.reliancedigital.in"},
        {"domain": "croma.com", "base_url": "https://www.croma.com"},
        {"domain": "vijaysales.com", "base_url": "https://www.vijaysales.com"},
        {"domain": "tatacliq.com", "base_url": "https://www.tatacliq.com"},
        {"domain": "apple.com", "base_url": "https://www.apple.com"},
        {"domain": "snapdeal.com", "base_url": "https://www.snapdeal.com"},
    ],
    "CA": [
        {"domain": "amazon.ca", "base_url": "https://www.amazon.ca"},
        {"domain": "bestbuy.ca", "base_url": "https://www.bestbuy.ca"},
        {"domain": "costco.ca", "base_url": "https://www.costco.ca"},
        {"domain": "canadiantire.ca", "base_url": "https://www.canadiantire.ca"},
        {"domain": "apple.com", "base_url": "https://www.apple.com"},
        {"domain": "rogers.com", "base_url": "https://www.rogers.com"},
        {"domain": "bell.ca", "base_url": "https://www.bell.ca"},
        {"domain": "telus.com", "base_url": "https://www.telus.com"},
    ],
    "AU": [
        {"domain": "amazon.com.au", "base_url": "https://www.amazon.com.au"},
        {"domain": "jbhifi.com.au", "base_url": "https://www.jbhifi.com.au"},
        {"domain": "harveynorman.com.au", "base_url": "https://www.harveynorman.com.au"},
        {"domain": "officeworks.com.au", "base_url": "https://www.officeworks.com.au"},
        {"domain": "apple.com", "base_url": "https://www.apple.com"},
        {"domain": "telstra.com.au", "base_url": "https://www.telstra.com.au"},
        {"domain": "optus.com.au", "base_url": "https://www.optus.com.au"},
        {"domain": "bigw.com.au", "base_url": "https://www.bigw.com.au"},
    ],
    "DE": [
        {"domain": "amazon.de", "base_url": "https://www.amazon.de"},
        {"domain": "mediamarkt.de", "base_url": "https://www.mediamarkt.de"},
        {"domain": "saturn.de", "base_url": "https://www.saturn.de"},
        {"domain": "otto.de", "base_url": "https://www.otto.de"},
        {"domain": "apple.com", "base_url": "https://www.apple.com"},
        {"domain": "telekom.de", "base_url": "https://www.telekom.de"},
        {"domain": "vodafone.de", "base_url": "https://www.vodafone.de"},
        {"domain": "notebooksbilliger.de", "base_url": "https://www.notebooksbilliger.de"},
    ]
}

def get_static_sites(country: str) -> list:
    """Get static site list for a country to avoid LLM calls."""
    return STATIC_SITE_CACHE.get(country, STATIC_SITE_CACHE.get("US", []))
