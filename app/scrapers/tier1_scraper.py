"""
Tier 1 scraper using BeautifulSoup for fast, traditional web scraping.
"""

import re
from typing import List, Dict
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models import ProductResult


async def scrape_site(site_config: Dict, query: str, client: httpx.AsyncClient) -> List[ProductResult]:
    """
    Scrape products using pre-configured selectors.

    Args:
        site_config: Site configuration with selectors and URLs
        query: Search query
        client: HTTP client for making requests

    Returns:
        List of ProductResult objects

    Raises:
        ValueError: If no products found
        Exception: For other scraping errors
    """
    search_url = site_config['search_url_template'].format(query=quote(query))
    response = await client.get(
        search_url,
        follow_redirects=True,
        timeout=settings.HTTP_CLIENT_TIMEOUT
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    selectors = site_config['selectors']
    containers = soup.select(selectors['container'])

    results = []
    for container in containers[:5]:  # Limit results per site
        try:
            title_elem = container.select_one(selectors['title'])
            price_elem = container.select_one(selectors['price'])
            link_elem = container.select_one(selectors['link'])

            if not (title_elem and price_elem and link_elem):
                continue

            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'([\d,]+\.?\d*)', price_text.replace(',', ''))
            if not price_match:
                continue

            product = ProductResult(
                product_name=title_elem.get('title', title_elem.get_text(strip=True)),
                price=float(price_match.group(1)),
                currency="GBP",  # TODO: Make this dynamic based on country
                link=urljoin(site_config['base_url'], link_elem.get('href', '')),
                site_name=site_config.get('name'),
                confidence_score=0.9
            )
            results.append(product)
        except Exception:
            # Skip individual product parsing errors
            continue

    if not results:
        raise ValueError("No products found via Tier 1 selectors.")

    return results
