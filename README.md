# Ultimate Price Comparison API

**AI-powered price comparison across multiple e-commerce sites with dynamic site discovery and accurate price extraction.**

## Summary

- 🌍 **Multi-Country**: US, UK, India, Canada, Australia, Germany
- 🤖 **AI-Powered**: Uses Gemini 2.5 Flash for intelligent price extraction
- 🔍 **Dynamic**: Automatically discovers relevant sites per country
- 💰 **Accurate**: Prioritizes retail prices over promotional offers
- ⚡ **Optimized**: Rate-limited for Gemini free tier (10 req/min)

## Setup

**Requirements:** Python 3.12+

```bash
# 1. Clone and setup
git clone <repository-url>
cd lowest-price
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start server
python3 main.py
```

**API Keys needed:**
- **Google AI Studio**: https://aistudio.google.com/app/apikey (free: 10 req/min)
- **SerpAPI**: https://serpapi.com/ (free: 100 searches/month)

**Endpoints:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

## Usage

**Search Products:** `POST /search`
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"country": "US", "query": "iPhone 16 Pro 128GB", "max_results": 5}'
```

**Response:**
```json
{
  "success": true,
  "total_results": 2,
  "results": [
    {
      "link": "https://www.target.com/p/apple-iphone-16-pro-128gb-natural-titanium/-/A-90539822",
      "price": 999.99,
      "currency": "USD",
      "product_name": "Apple iPhone 16 Pro 128GB",
      "site_name": "target.com"
    }
  ]
}
```

**Countries:** US, UK, IN, CA, AU, DE

## Architecture

**Agent-based workflow:** Site Discovery → Query Enhancement → URL Discovery → LLM Extraction → Consolidation

**Tech Stack:** Python 3.12+, FastAPI, LangGraph, Gemini 2.5 Flash, SerpAPI

**Optimizations:**
- Static site cache (saves LLM calls)
- Smart query enhancement (skips LLM for well-formed queries)
- Rate limiting (5 sites max per request for 10 req/min limit)

## Troubleshooting

**Environment issues:**
```bash
# Recreate virtual environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Rate limit exceeded:** Check `/rate-limit-status` endpoint

**No results:** Try different queries, check SerpAPI quota
