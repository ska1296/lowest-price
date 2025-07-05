"""
HTML preprocessing utility for LLM extraction.
Cleans and simplifies HTML content to make it easier for LLMs to parse.
"""

import re
from bs4 import BeautifulSoup


def preprocess_html_for_llm(html: str) -> str:
    """
    Cleans and simplifies HTML content to make it easier for an LLM to parse.
    Implements stripping, focusing on main content, and adding semantic hints.
    
    Args:
        html: Raw HTML content from a webpage
        
    Returns:
        Cleaned and simplified text with semantic hints
    """
    if not html:
        return ""
        
    soup = BeautifulSoup(html, 'lxml')

    # 1. Remove irrelevant tags but keep some structure
    for tag in soup(["script", "style", "svg", "iframe", "noscript"]):
        tag.decompose()

    # Remove navigation and footer but keep header (might have product info)
    for tag in soup(["nav", "footer"]):
        tag.decompose()

    # 2. Remove recommendation/related product sections that confuse the LLM
    for tag in soup(class_=re.compile(r'recommend|related|similar|also-bought|customers-also|suggestions|carousel', re.I)):
        tag.decompose()
    for tag in soup(id=re.compile(r'recommend|related|similar|also-bought|customers-also|suggestions|carousel', re.I)):
        tag.decompose()

    # 3. Heuristically find the main content area to focus on
    main_content = (
        soup.find('main') or
        soup.find(id=re.compile(r'main|content|body|product', re.I)) or
        soup.find(class_=re.compile(r'product-detail|pdp|product-info|main-content', re.I)) or
        soup.body
    )
    if not main_content:
        return ""  # Return empty if no body content

    # 4. Add semantic hints to the text of remaining elements - prioritize main product info
    simplified_text = []

    # First, look for the main product title (usually H1)
    main_title = main_content.find('h1')
    if main_title:
        title_text = main_title.get_text(strip=True)
        if title_text:
            simplified_text.append(f"[MAIN PRODUCT TITLE]: {title_text}")

    # Then process other elements
    for element in main_content.find_all(['h1', 'h2', 'h3', 'span', 'div', 'p', 'li', 'b', 'strong']):
        text = element.get_text(separator=' ', strip=True)
        if not text or len(text) < 3:
            continue

        # Skip if this is the main title we already added
        if element == main_title:
            continue

        # Combine class and id for keyword searching
        attrs_str = ' '.join(element.get('class', [])) + ' ' + element.get('id', '')

        # Add hints based on attributes - this is crucial for the LLM
        if any(keyword in attrs_str.lower() for keyword in ['price', 'cost', 'amount', 'offer', 'money', 'dollar']):
            simplified_text.append(f"[PRICE HINT]: {text}")
        elif any(keyword in attrs_str.lower() for keyword in ['title', 'name', 'heading', 'brand', 'product']) and element.name in ['h1', 'h2']:
            simplified_text.append(f"[PRODUCT TITLE]: {text}")
        elif element.name in ['h2', 'h3'] and len(text) > 10:
            simplified_text.append(f"[HEADER {element.name.upper()}]: {text}")
        elif any(keyword in attrs_str.lower() for keyword in ['stock', 'availability', 'available', 'inventory']):
            simplified_text.append(f"[AVAILABILITY HINT]: {text}")
        else:
            # Only add text if it seems meaningful and not too long
            if 5 <= len(text) <= 200 and (re.search(r'\d', text) or any(word in text.lower() for word in ['product', 'item', 'buy', 'add', 'cart'])):
                simplified_text.append(text)

    # 4. Join the text lines and limit the size
    final_text = '\n'.join(simplified_text)
    return final_text[:8000]  # Limit to 8k chars of the most relevant content


def extract_product_hints(html: str) -> dict:
    """
    Extract specific product information hints from HTML structure.
    
    Args:
        html: Raw HTML content
        
    Returns:
        Dictionary with extracted hints
    """
    if not html:
        return {}
        
    soup = BeautifulSoup(html, 'lxml')
    hints = {}
    
    # Look for common e-commerce patterns
    price_selectors = [
        '[class*="price"]',
        '[id*="price"]',
        '.price-current',
        '.price-now',
        '.sale-price',
        '.offer-price'
    ]
    
    title_selectors = [
        'h1',
        '[class*="title"]',
        '[class*="name"]',
        '[id*="title"]',
        '[id*="name"]'
    ]
    
    # Extract price hints
    for selector in price_selectors:
        elements = soup.select(selector)
        for elem in elements:
            text = elem.get_text(strip=True)
            if text and re.search(r'[\d,]+\.?\d*', text):
                hints['price_candidates'] = hints.get('price_candidates', [])
                hints['price_candidates'].append(text)
    
    # Extract title hints
    for selector in title_selectors:
        elements = soup.select(selector)
        for elem in elements:
            text = elem.get_text(strip=True)
            if text and len(text) > 5:
                hints['title_candidates'] = hints.get('title_candidates', [])
                hints['title_candidates'].append(text)
    
    return hints
