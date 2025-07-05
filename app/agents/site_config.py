"""
Site configuration management for Tier 1 scrapers.
"""

from typing import Optional, Dict


# Static configurations for Tier 1 scrapers
# This does NOT know which sites belong to which country.
# It only provides the 'how-to' for scraping a known site.
SITE_CONFIGS = {
    "books.toscrape.com": {
        "name": "Books To Scrape",
        "search_url_template": "http://books.toscrape.com/catalogue/search.html?q={query}",
        "base_url": "http://books.toscrape.com",
        "selectors": {
            "container": "article.product_pod",
            "title": "h3 a",
            "price": "p.price_color",
            "link": "h3 a",
        }
    }
    # TODO: Add more pre-written Tier 1 scraper configs here for other sites.
    # Examples:
    # "amazon.com": {...},
    # "ebay.com": {...},
    # "bestbuy.com": {...},
}


def get_site_config(site_domain: str) -> Optional[Dict]:
    """
    Get configuration for a specific site domain.

    Args:
        site_domain: The domain name of the site

    Returns:
        Configuration dictionary if found, None otherwise
    """
    return SITE_CONFIGS.get(site_domain)


def add_site_config(site_domain: str, config: Dict):
    """
    Add a new site configuration.

    Args:
        site_domain: The domain name of the site
        config: Configuration dictionary
    """
    SITE_CONFIGS[site_domain] = config


def list_supported_sites() -> list:
    """
    Get list of all supported site domains.

    Returns:
        List of supported site domain names
    """
    return list(SITE_CONFIGS.keys())
