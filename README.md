# Ultimate Price Comparison API v3.0

A robust, backend-only tool that can reliably fetch the best price for a given product by comparing prices from multiple relevant websites for a specified country.

## Architecture

This application uses a clean functional architecture with a fully dynamic, config-free agent-based workflow built with LangGraph and SerpApi:

- **Dynamic Site Discovery**: LLM discovers relevant e-commerce sites per country with caching
- **Smart URL Discovery**: SerpApi finds actual product pages instead of guessing search URLs
- **LLM-based Extraction**: Intelligent extraction from any website without hardcoded selectors
- **Dynamic Currency**: Extracts currency contextually from product pages
- **Agent-based workflow**: Site selection → Query enhancement → URL discovery → LLM extraction → Consolidation
- **Config-free**: No hardcoded site configurations - works with any e-commerce website
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
│   └── agents/                  # LLM agent functions
│       ├── __init__.py
│       ├── llm_agents.py        # Site discovery, query enhancement, LLM extraction
│       └── product_url_discovery.py  # SerpApi URL discovery agent
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

2. **Set up environment variables:**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env with your actual values:
   # GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
   # SERPAPI_API_KEY=your-serpapi-api-key
   ```

3. **Get API Keys:**
   - **Google Cloud**: Download service account key with Vertex AI access
   - **SerpApi**: Sign up at https://serpapi.com/ for a free API key

4. **Run the application:**
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
      "tier2_success": 3,
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
- **Gemini Pro**: LLM for site discovery and intelligent data extraction
- **LangChain**: LLM integration framework
- **SerpAPI**: Product URL discovery via Google Search
- **httpx**: Async HTTP client
- **SQLite**: Local caching
- **Pydantic**: Data validation and serialization

## Development

The application is designed with functional programming principles for simplicity and maintainability:

- **Modify workflow**: Edit agent functions in `app/core/workflow.py`
- **Add new agents**: Add functions to `app/agents/llm_agents.py`
- **Enhance URL discovery**: Modify `app/agents/product_url_discovery.py`
- **Add business logic**: Add functions to `app/services/price_comparison_service.py`
- **No site configs needed**: The system works dynamically with any e-commerce website

## API Documentation

Once running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
