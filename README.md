# 🛒 Price Comparison API

> **AI-powered price comparison across multiple e-commerce sites with dynamic site discovery and accurate price extraction.**

## 🎬 Demo Video

[![Watch Demo](https://img.shields.io/badge/🎬_Watch_Demo_Video-Loom-00D2FF?style=for-the-badge&logo=loom)](https://www.loom.com/share/f41e25484b2f4add89a35c9f861f1e10?sid=490f6f32-1877-47e4-968a-06496e97b170)

*Click above to see the API in action!*

## ✨ Features

🌍 **Multi-Country Support** • US, UK, India, Canada, Australia, Germany
🤖 **AI-Powered Extraction** • Uses Gemini 2.5 Flash for intelligent price parsing
🔍 **Dynamic Site Discovery** • Automatically finds relevant e-commerce sites
💰 **Accurate Pricing** • Prioritizes retail prices over promotional offers
⚡ **Rate-Limited** • Optimized for Gemini free tier (10 requests/minute)

## 🚀 Quick Start

### Prerequisites
![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square&logo=python)

### Installation

```bash
# 1. Clone and setup environment
git clone git@github.com:ska1296/lowest-price.git
cd lowest-price
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env with your credentials

# 3. Launch the API
python3 main.py
```

### 🔑 API Keys Required

| Service | URL | Free Tier |
|---------|-----|-----------|
| **Google AI Studio** | [Get API Key](https://aistudio.google.com/app/apikey) | 10 requests/min |
| **SerpAPI** | [Get API Key](https://serpapi.com/) | 100 searches/month |

### 🌐 Endpoints

- **API Server**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📖 Usage

### Search Products

**Endpoint:** `POST /search`

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"country": "US", "query": "iPhone 16 Pro 128GB"}'
```

### Response Format

```json
{
  "success": true,
  "total_results": 3,
  "search_time_ms": 8500,
  "results": [
    {
      "link": "https://www.target.com/p/apple-iphone-16-pro-128gb/-/A-90539822",
      "price": 999.99,
      "currency": "USD",
      "product_name": "Apple iPhone 16 Pro 128GB Natural Titanium",
      "site_name": "target.com",
      "availability": "in-stock",
      "confidence_score": 0.95
    }
  ],
  "metadata": {
    "enhanced_query": "iPhone 16 Pro 128GB",
    "sites_checked": 5
  }
}
```

### 🌍 Supported Countries

| Code | Country | Code | Country |
|------|---------|------|---------|
| `US` | United States | `CA` | Canada |
| `GB` | United Kingdom | `AU` | Australia |
| `IN` | India | `DE` | Germany |

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
