#!/usr/bin/env python3
"""
Debug script to test price extraction from specific URLs.
"""

import asyncio
import httpx
from app.utils.html_cleaner import preprocess_html_for_llm

async def debug_price_extraction():
    """Debug price extraction from Verizon iPhone page."""
    
    url = "https://www.verizon.com/smartphones/apple-iphone-16-pro/"
    
    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}) as client:
        print(f"🌐 Fetching from {url}...")
        response = await client.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        
        print(f"📄 Received {len(response.text)} characters")
        
        # Clean the HTML
        cleaned_html = preprocess_html_for_llm(response.text)
        
        print(f"🧹 Cleaned HTML length: {len(cleaned_html)} characters")
        print("\n" + "="*80)
        print("CLEANED HTML CONTENT:")
        print("="*80)
        print(cleaned_html[:3000])  # Show first 3000 chars
        print("\n" + "="*80)
        
        # Look for price-related content specifically
        lines = cleaned_html.split('\n')
        price_lines = [line for line in lines if any(keyword in line.lower() for keyword in ['price', '$', 'cost', 'pay', 'month'])]
        
        print("PRICE-RELATED LINES:")
        print("="*80)
        for line in price_lines[:20]:  # Show first 20 price-related lines
            print(f"  {line.strip()}")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(debug_price_extraction())
