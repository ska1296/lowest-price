# Ultimate Price Comparison API

A robust, backend-only tool that can reliably fetch the best price for a given product by comparing prices from multiple relevant websites for a specified country.

## Architecture

This application uses a clean functional architecture with a tiered, agent-based workflow built with LangGraph:

- **Tier 1**: Fast BeautifulSoup scrapers with pre-configured selectors
- **Tier 2**: Self-healing LLM-based extraction when Tier 1 fails
- **Agent-based workflow**: Site selection, query enhancement, scraping, healing, and consolidation
- **Functional design**: No unnecessary classes, simple functions for better maintainability

## Project Structure

```
├── app/                          # Main application package
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # FastAPI application
│   ├── config.py                # Configuration settings
│   ├── models.py                # Pydantic models and data structures
│   ├── services/                # Business logic services
│   │   ├── __init__.py
│   │   └── price_comparison_service.py  # Main service functions
│   ├── routers/                 # API route handlers
│   │   ├── __init__.py
│   │   ├── search.py            # Search endpoints
│   │   └── health.py            # Health check endpoints
│   ├── core/                    # Core business logic
│   │   ├── __init__.py
│   │   ├── cache.py             # SQLite cache functions
│   │   └── workflow.py          # LangGraph workflow functions
│   ├── agents/                  # LLM agent functions
│   │   ├── __init__.py
│   │   ├── llm_agents.py        # Site discovery, query enhancement, extraction
│   │   └── site_config.py       # Static site configurations
│   └── scrapers/                # Web scraping functions
│       ├── __init__.py
│       └── tier1_scraper.py     # BeautifulSoup-based scraping
├── requirements.txt             # Python dependencies
├── main.py                     # Main entry point and startup script
├── blueprint                   # Architecture blueprint
└── problem.txt                 # Original problem statement
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Google Cloud Project:**
   ```bash
   export GCLOUD_PROJECT="your-gcp-project-id"
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

   Or with uvicorn directly:
   ```bash
   uvicorn app.main:app --reload
   ```

## API Usage

### Search Products

**POST** `/search`

```json
{
  "country": "US",
  "query": "iPhone 16 Pro, 128GB",
  "max_results": 5
}
```

**Response:**
```json
{
  "success": true,
  "total_results": 3,
  "search_time_ms": 2500,
  "results": [
    {
      "link": "https://example.com/product",
      "price": 999.0,
      "currency": "USD",
      "product_name": "Apple iPhone 16 Pro",
      "site_name": "Example Store",
      "availability": "in-stock",
      "confidence_score": 0.9
    }
  ],
  "metadata": {
    "enhanced_query": "Apple iPhone 16 Pro 128GB",
    "sites_checked": 4,
    "tier_stats": {
      "tier1_success": 1,
      "tier2_success": 2,
      "tier1_fails": 1
    }
  }
}
```

### Health Check

**GET** `/health`

Returns application health status.

## Supported Countries

- US (United States)
- IN (India)
- GB (United Kingdom)
- CA (Canada)
- AU (Australia)
- DE (Germany)

## Technology Stack

- **Python**: Core programming language
- **FastAPI**: High-performance web framework
- **LangGraph**: Agent workflow orchestration
- **Gemini Pro**: LLM for site discovery and data extraction
- **LangChain**: LLM integration framework
- **BeautifulSoup4**: HTML parsing for Tier 1 scraping
- **httpx**: Async HTTP client
- **SQLite**: Local caching
- **Pydantic**: Data validation and serialization

## Development

The application is designed with functional programming principles for simplicity and maintainability:

- **Add new sites**: Update `SITE_CONFIGS` in `app/agents/site_config.py`
- **Modify workflow**: Edit functions in `app/core/workflow.py`
- **Add new agents**: Add functions to `app/agents/llm_agents.py`
- **Extend scrapers**: Add functions to `app/scrapers/tier1_scraper.py`
- **Add business logic**: Add functions to `app/services/price_comparison_service.py`

## API Documentation

Once running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
