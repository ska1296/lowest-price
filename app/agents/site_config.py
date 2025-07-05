"""
Site configuration management for Tier 1 scrapers.
This now focuses ONLY on selectors for a given product page.
"""

from typing import Optional, Dict


# Static configurations for Tier 1 scrapers
# This focuses on product page selectors, not search URLs
SITE_CONFIGS = {
    "books.toscrape.com": {
        "name": "Books To Scrape",
        "currency": "GBP",  # Static currency per domain
        "selectors": {
            "container": "div.product_main",  # Selector for the main product block on the page
            "title": "h1",
            "price": "p.price_color",
        }
    }
    # TODO: Add more configs for direct product pages (e.g., Amazon's #productTitle, #priceblock_ourprice)
    # Examples:
    # "amazon.com": {
    #     "name": "Amazon",
    #     "currency": "USD",
    #     "selectors": {
    #         "container": "#dp-container",
    #         "title": "#productTitle",
    #         "price": ".a-price-whole",
    #     }
    # },
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
