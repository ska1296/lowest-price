"""
Cache management for the price comparison application.
"""

import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from app.config import settings


# Initialize database on module import
def _initialize_database():
    """Initialize the SQLite database with required tables."""
    with sqlite3.connect(settings.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS country_sites
            (
                country TEXT PRIMARY KEY,
                sites TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


# Initialize on import
_initialize_database()


async def get_country_sites(country: str) -> Optional[List[Dict]]:
    """
    Retrieve cached sites for a country.

    Args:
        country: Country code to look up

    Returns:
        List of site dictionaries if found and not expired, None otherwise
    """
    loop = asyncio.get_event_loop()

    def db_read():
        with sqlite3.connect(settings.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sites, last_updated FROM country_sites WHERE country = ?",
                (country,)
            )
            row = cursor.fetchone()
            if row:
                sites_json, last_updated_str = row
                last_updated = datetime.fromisoformat(last_updated_str)
                if datetime.utcnow() - last_updated < timedelta(hours=settings.CACHE_DURATION_HOURS):
                    return json.loads(sites_json)
        return None

    return await loop.run_in_executor(None, db_read)


async def cache_country_sites(country: str, sites: List[Dict]):
    """
    Cache sites for a country.

    Args:
        country: Country code
        sites: List of site dictionaries to cache
    """
    loop = asyncio.get_event_loop()

    def db_write():
        with sqlite3.connect(settings.DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "REPLACE INTO country_sites (country, sites, last_updated) VALUES (?, ?, ?)",
                (country, json.dumps(sites), datetime.utcnow().isoformat())
            )
            conn.commit()

    await loop.run_in_executor(None, db_write)
