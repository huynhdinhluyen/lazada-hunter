# 🛍️ Lazada Hunter — Automated E-Commerce Intelligence & Market Analytics Platform

> **An enterprise-grade, full-stack automated platform for real-time Lazada product harvesting, LLM-powered market intelligence & competitive pricing analysis, high-performance semantic vector search (Qdrant Cloud), sub-millisecond in-memory caching (Redis Cloud), automated background price monitoring (APScheduler), and multi-channel instant broadcasting (Telegram Bot).**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.3-black.svg?logo=next.js)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg?logo=postgresql)](https://www.postgresql.org)
[![Qdrant Cloud](https://img.shields.io/badge/Vector_DB-Qdrant_Cloud_(HNSW)-DC2626.svg?logo=qdrant)](https://cloud.qdrant.io)
[![Redis Cloud](https://img.shields.io/badge/Cache-Redis_Cloud_(<1ms)-DC382D.svg?logo=redis)](https://redis.io)
[![NVIDIA NIM](https://img.shields.io/badge/AI_Engine-NVIDIA_NIM_%26_Gemini-76B900.svg?logo=nvidia)](https://build.nvidia.com)
[![Telegram Bot](https://img.shields.io/badge/Notifications-Telegram_Bot-26A5E4.svg?logo=telegram)](https://telegram.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?logo=typescript)](https://www.typescriptlang.org)
[![Playwright](https://img.shields.io/badge/Crawler-Playwright_Stealth-45ba4b.svg?logo=playwright)](https://playwright.dev)

---

## 📑 Table of Contents

1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Key Capabilities](#2-key-capabilities)
3. [System Architecture](#3-system-architecture)
4. [End-to-End Data Workflow](#4-end-to-end-data-workflow)
5. [Installation & Deployment Guide](#5-installation--deployment-guide)
6. [API Reference Documentation](#6-api-reference-documentation)
7. [Demonstration & Verification Script](#7-demonstration--verification-script)
8. [License & Credits](#8-license--credits)

---

## 1. Executive Summary & Problem Statement

### 📌 Industry Challenge
Modern e-commerce enterprises, retailers, and market analysts face critical challenges when monitoring dynamic marketplaces like Lazada:
- **High-Frequency Price Volatility**: Flash sales, promotional vouchers, and artificial price hikes occur continuously, necessitating 24/7 automated monitoring.
- **Unstructured & SEO-Spammed Titles**: Raw listing titles are cluttered with spam keywords, making programmatic cataloging and cross-shop comparison inaccurate.
- **Massive Customer Feedback Volume**: Hundreds of thousands of subjective reviews prevent manual analysis of genuine product defects or competitive advantages.
- **Query Latency & Token Expenses**: Repeated large language model (LLM) invocations for identical consumer queries result in high latency and unsustainable API token costs.

### 💡 The Solution: Lazada Hunter
**Lazada Hunter** bridges the gap between web automation and artificial intelligence:
- 🕷️ **Multi-Layer Stealth Harvester**: Extracts titles, historical pricing, discounts, sales volume, rating metrics, technical specifications, and customer reviews using anti-bot evasions and multi-layer context extraction (`window.dataLayer`, `window.pdpTrackingData`, script regex, and DOM fallback).
- 🔗 **Direct URL Ingestion in Chat**: Allows users to paste live Lazada product URLs directly into the chat box for instantaneous crawling, review synthesis, and structured evaluation.
- 🧠 **Multi-LLM Dynamic Router**: Employs **NVIDIA NIM (Llama 3.1 8B / 70B)** as the primary engine for high-throughput cost efficiency, with automated failover to **Google Gemini Flash** and rule-based heuristics.
- ⚡ **Qdrant Cloud Vector Search & Redis Hot Cache**: Leverages **Qdrant Cloud** for HNSW semantic retrieval and **Redis Cloud** for sub-millisecond query deduplication (< 1ms).
- ⏰ **Automated Watchlist Background Price Tracker**: Runs a 30-minute scheduled cron job (`APScheduler`) to monitor saved items, log price time-series, and trigger Telegram alerts exclusively when genuine price reductions occur ($\ge 5\%$).
- 📢 **Instant Telegram Broadcasting**: Automatically formats rich product media bulletins (photo, live price, discount, review summary, direct link) directly to Telegram channels.
- 💻 **Modern Web Dashboard (Next.js 16)**: Premium Glassmorphism interface featuring dedicated URL routing (`/chat`, `/catalog`, `/watchlist`, `/telegram`), Grid/Table view toggles, time-series price charts, and multi-format exports (**Excel**, **CSV**, **JSON**).

---

## 2. Key Capabilities

### 💬 1. Intelligent AI Shopping Advisor
- **Natural Language Understanding**: Understands colloquial purchasing inquiries (e.g., *"Find gaming wireless mouse under 300k"*).
- **Direct Lazada Link Ingestion**: Users can paste any Lazada product URL directly into the chat input. The system automatically fetches live page data, extracts reviews, generates competitive pricing bounds, and renders an interactive product card.
- **6-Intent Classification Engine**:
  1. `RECOMMENDATION`: Recommends top-rated products aligned with user budget constraints.
  2. `COMPARISON`: Compares technical specifications and customer satisfaction between multiple items.
  3. `UNREALISTIC_CONSTRAINTS`: Detects and warns against suspicious pricing (e.g., *"iPhone 16 Pro Max 5 million VND"*).
  4. `CLARIFICATION_NEEDED`: Requests additional criteria when user intent is ambiguous.
  5. `CHITCHAT_OUT_OF_SCOPE`: Converses naturally for general inquiries.
  6. `SAFETY_GUARD`: Filters harmful or malicious queries.
- **Semantic Caching**: Instant response retrieval from Redis RAM for identical or synonymous queries across all chat turns.

### 📦 2. Comprehensive Product Catalog & Market Insights
- **Dual Presentation Modes**: Switch seamlessly between **Grid View** (uniform card heights with clamped 2-line titles) and **Table View** (dense professional data table).
- **In-Depth AI Analysis Modal**:
  - Standardized product naming and category classification.
  - Overall sentiment score (scale of 1.0 to 10.0).
  - Concise technical quality summary.
  - Side-by-side **Pros** and **Cons** extracted from actual buyer reviews.
  - **Market-Competitive Price Suggestions** (Minimum, Optimal, Maximum).
  - Target audience recommendation and purchasing verdict.
- **Time-Series Price Volatility Chart**: Interactive SVG visualizer displaying historical price movements.
- **Multi-Format Data Export**: One-click generation of styled **Excel (.xlsx)**, **CSV (UTF-8 with BOM)**, and **JSON** files.

### 📌 3. User Watchlist & Background Price Tracking
- **One-Click Bookmarking**: Bookmark products directly from the AI Chat recommendations or the Product Catalog.
- **Instant Telegram Notification**: Automatically dispatches a formatted photo bulletin to Telegram upon saving a product.
- **Automated Background Price Tracker**: Scheduled background worker scans all items in user watchlists every 30 minutes, recording fluctuations into PostgreSQL `PriceHistory`.
- **Dual-Layer Price Drop Guardrail**: Guarantees that Telegram price alerts are dispatched **exclusively when prices drop** compared to prior records ($\text{new\_price} < \text{old\_price}$ with $\ge 5\%$ drop), filtering out unchanged or increased prices.

### 📢 4. Telegram Notification Center
- **Automated Media Bulletins (`sendPhoto`)**: Sends photo-backed HTML summaries upon product bookmarking or price drops.
- **Real-Time Price Drop Alerts**: Triggered whenever a watched product drops below the user-configured percentage threshold.
- **Diagnostic Controls**: Real-time Telegram Bot connection verification, webhook latency testing, and interactive ping test.

---

## 3. System Architecture

Lazada Hunter is structured around a **Micro-Modular Architecture**, ensuring strict separation of concerns across presentation, orchestration, AI inference, and cloud storage:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. CLIENT LAYER (Next.js 16 + React 19 + TypeScript + TailwindCSS)          │
│ • Distinct Subroutes: /chat · /catalog · /watchlist · /telegram             │
│ • Glassmorphism Theme · Non-leaking Modal Portals · Responsive Layouts      │
│ • Client-side Export Engines (Excel .xlsx, CSV UTF-8 BOM, JSON)             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ RESTful API (HTTP / JSON)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│ 2. CORE BACKEND SERVICE (FastAPI + Asynchronous Python 3.10+)               │
│ • Dual-Write Data Pipeline (PostgreSQL + Qdrant Cloud)                      │
│ • In-Memory Hot Cache & Multi-Turn Semantic Query Deduplication             │
│ • Background Watchlist Scheduler (APScheduler Cron Worker)                  │
│ • Centralized Exception Handling, CORS, Health Probes & Loguru Telemetry    │
└──────────────────┬───────────────────┬───────────────────┬──────────────────┘
                   │                   │                   │
┌──────────────────▼──┐ ┌──────────────▼───┐ ┌─────────────▼────────────────┐
│ 3. VECTOR DATABASE  │ │ 4. RELATIONAL DB │ │ 5. IN-MEMORY HOT CACHE       │
│ • Qdrant Cloud      │ │ • PostgreSQL 15+ │ │ • Redis Cloud                │
│ • HNSW Vector Index │ │ • Products Table │ │ • Semantic Deduplication     │
│ • 384D Cosine       │ │ • Price History  │ │ • Dynamic Tiered TTL (2h/24h)│
│ • Payload Indexing  │ │ • Watchlists     │ │ • Sub-millisecond Latency    │
└──────────────────┬──┘ └──────────────────┘ └──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────────────────────┐
│ 6. AI & DYNAMIC MODEL ROUTER                                                │
│ • Intent Classifier (6 Shopping Intents + Direct URL Detection)             │
│ • Primary: NVIDIA NIM (Llama 3.1 8B/70B) ──Failover──▶ Google Gemini Flash  │
│ • Fallback Engine: Heuristic Rule-Based Parsing (100% Uptime Guarantee)     │
│ • Pydantic Structured Outputs: Quality, Pros/Cons, Price Suggestions        │
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────────────────────┐
│ 7. BROWSER HARVESTING & TELEGRAM BROADCASTING                               │
│ • Playwright Stealth (Chromium Headless, Anti-Bot WAF Evasions)             │
│ • Multi-Layer Extraction: window.dataLayer + Script Regex + DOM V2 Fallback │
│ • Telegram Bot Service (HTML Rich Media Bulletins, Price Drop Alerts)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. End-to-End Data Workflow

```mermaid
flowchart TD
    User([User: Chat Query / Lazada URL Paste / Watchlist]) --> NextJS[Next.js 16 Web Dashboard]
    NextJS --> FastAPI[FastAPI Backend Engine]

    subgraph Chat_And_Search [AI Shopping Assistant & Search Flow]
        FastAPI --> CheckURL{Direct Lazada URL?}
        CheckURL -->|Yes: Direct Link| SingleCrawl[Playwright: Single Product PDP Extraction]
        CheckURL -->|No: Text Query| CacheCheck{Check Redis Cache?}
        CacheCheck -->|Cache Hit < 1ms| ReturnCached[Return Cached Response Immediately]
        CacheCheck -->|Cache Miss| QdrantSearch[Qdrant Cloud: HNSW Semantic Search]
        QdrantSearch --> HasEnough{Sufficient items in DB?}
        HasEnough -->|>= 2 Candidates| AIRouter[AI Model Router: NVIDIA NIM / Gemini]
        HasEnough -->|0-1 Candidates| LiveSearch[Trigger Playwright Search Harvester]
    end

    subgraph Crawling_Engine [Data Extraction & Dual-Write Ingestion]
        SingleCrawl --> ParsePDP[Extract: Name, Price, Specs, Reviews, Canonical URL]
        LiveSearch --> ParseCatalog[Extract: List Items, JSON-LD, Images, Ratings]
        ParsePDP --> DualWrite[Data Pipeline: Dual-Write]
        ParseCatalog --> DualWrite
        DualWrite --> SavePG[(PostgreSQL Database)]
        DualWrite --> SaveQdrant[(Qdrant Cloud Vector Store)]
        DualWrite --> AIRouter
    end

    subgraph Background_Monitoring [Scheduled Watchlist Monitoring]
        CronJob[APScheduler: 30-min Recurring Cron] --> QueryWatchlist[Fetch Watched Product URLs]
        QueryWatchlist --> RefreshPrice[Live Scrape Latest Prices]
        RefreshPrice --> DetectDrop{New Price < Old Price & Drop >= 5%?}
        DetectDrop -->|Yes: Genuine Price Drop| TgAlert[Send Telegram Price Drop Alert]
        DetectDrop -->|No: Unchanged / Increased| SkipAlert[Log & Skip Notification]
    end

    subgraph Output_Distribution [Intelligence Delivery & Distribution]
        AIRouter --> GenInsights[Generate Insights: Pros/Cons, Price Evaluation, Verdict]
        GenInsights --> SaveRedisCache[(Store into Redis Hot Cache)]
        GenInsights --> ReturnUser[Render on Web Dashboard: Chat / Grid / Table]
    end
```

---

## 5. Installation & Deployment Guide

### 5.1. Prerequisites
Ensure the host environment meets the following specifications:
- **Python**: 3.10, 3.11, or 3.12
- **Node.js**: 18.x or later (20.x+ recommended)
- **PostgreSQL**: 14.x or later (Local or Managed Cloud Instance)
- **Redis**: Local Redis or Redis Cloud Instance
- **Qdrant**: Free cluster at [Qdrant Cloud](https://cloud.qdrant.io)

---

### 5.2. Environment Configuration

#### ⚙️ Backend Configuration (`server/.env`):
Create `server/.env` with the following parameters:
```env
# 1. PostgreSQL Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_postgres_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ecommerce_crawler

# 2. Redis Cloud / In-Memory Cache
REDIS_URL=redis://default:your_redis_password@your_redis_host:17709

# 3. Qdrant Cloud Vector Database
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_CLUSTER_ENDPOINT=https://your-cluster-id.us-west-1-0.aws.cloud.qdrant.io:6333
QDRANT_COLLECTION_NAME=products

# 4. AI Engine & LLM API Keys
NVIDIA_API_KEY=nvapi-your_nvidia_nim_key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
GEMINI_API_KEY=your_google_gemini_api_key

# 5. Telegram Bot Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_NOTIFY_ON_PRICE_DROP=True
PRICE_DROP_ALERT_THRESHOLD_PERCENT=5.0
WATCHLIST_CRON_INTERVAL_MINUTES=30

# 6. Web Harvester Configuration
CRAWLER_HEADLESS=True
CRAWLER_TIMEOUT_SECONDS=30
CRAWLER_MAX_CONCURRENCY=3
```

#### ⚙️ Frontend Configuration (`client/.env.local`):
Create `client/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_SECRET=lazada_hunter_super_secure_jwt_secret_2026
NEXTAUTH_URL=http://localhost:3000
```

---

### 5.3. Backend Setup (FastAPI)

1. Open a terminal in the project directory and navigate to the server folder:
   ```bash
   cd server
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright browser dependencies:
   ```bash
   playwright install chromium
   ```

5. Initialize the PostgreSQL schema and Qdrant collection indexes:
   ```bash
   python main.py init-db
   ```

6. Start the FastAPI backend server:
   ```bash
   python main.py server --host 0.0.0.0 --port 8000 --reload
   ```

> 🌐 **Interactive OpenAPI/Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)  
> 🌐 **Health Check Diagnostic**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

### 5.4. Frontend Setup (Next.js 16)

1. Open a new terminal window and navigate to the client directory:
   ```bash
   cd client
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Launch the development server:
   ```bash
   npm run dev
   ```

4. Access the web dashboard in your browser:
   ```
   http://localhost:3000
   ```

---

## 6. API Reference Documentation

| Method | Endpoint | Description |
| :---: | :--- | :--- |
| `POST` | `/api/v1/chat` | Chat with AI Shopping Advisor (Direct URL analysis + Semantic search + Redis Hot Cache) |
| `GET` | `/api/v1/products` | Query product catalog (Full-text search, pagination, `has_ai` filter, sorting) |
| `GET` | `/api/v1/products/{id}` | Fetch individual product specifications, price history, and AI insights |
| `GET` | `/api/v1/products/{id}/price-history` | Fetch time-series price fluctuation data for chart rendering |
| `GET` | `/api/v1/products/export/excel` | Export all products and AI analysis to formatted **Excel (.xlsx)** |
| `GET` | `/api/v1/products/export/csv` | Export catalog data to **CSV (UTF-8 with BOM)** |
| `GET` | `/api/v1/products/export/json` | Export full structured catalog to **JSON Schema** format |
| `POST` | `/api/v1/ai/analyze-product/{id}` | Execute LLM review summarization and competitive pricing for a product |
| `POST` | `/api/v1/ai/batch-analyze` | Batch analyze all unanalyzed products in the database |
| `GET` | `/api/v1/watchlist` | Retrieve user watchlist items with embedded product specifications |
| `POST` | `/api/v1/watchlist` | Add product to watchlist and trigger instant Telegram photo bulletin |
| `DELETE`| `/api/v1/watchlist/{product_id}` | Remove product from user watchlist |
| `GET` | `/api/v1/watchlist/check/{product_id}`| Check if product is currently saved in watchlist |
| `GET` | `/api/v1/watchlist/tracker/status` | Retrieve status of the automated background watchlist price tracker |
| `POST` | `/api/v1/watchlist/tracker/trigger` | Manually trigger on-demand price refresh and Telegram alert check |
| `POST` | `/api/v1/telegram/broadcast-product/{id}` | Dispatch formatted product photo bulletin directly to Telegram |
| `GET` | `/api/v1/telegram/status` | Verify Telegram Bot connection status and webhook latency |
| `POST` | `/api/v1/telegram/test` | Send test ping message to the configured Telegram chat |
| `GET` | `/api/v1/health` | Comprehensive health check across PostgreSQL, Redis Cloud, Qdrant, & Telegram |

---

## 7. Demonstration & Verification Script

Follow this 4-step walk-through to test or record a comprehensive demo (2–3 minutes):

### 🎬 Recommended Demonstration Flow:

1. **Step 1: AI Shopping Advisor & Sub-Millisecond Cache (`/chat`)**
   - Select a quick prompt chip: *"Tìm chuột không dây gaming dưới 300k"*.
   - Observe semantic product recommendations retrieved from **Qdrant Cloud**.
   - Send the same query again: Witness instantaneous response delivery (**< 1ms**) served directly from **Redis Hot Cache**.
   - Test an unrealistic query: *"Tìm iPhone 16 Pro Max 5 triệu new seal"* to trigger the guardrail warning.

2. **Step 2: Direct Lazada Link Ingestion & Instant AI Analysis (`/chat`)**
   - Copy any live Lazada product link (e.g., `https://www.lazada.vn/products/...`).
   - Paste it directly into the chat input box and hit send.
   - Observe real-time harvesting, LLM review summarization, sentiment scoring, and competitive price analysis returned with an embedded product card.

3. **Step 3: Product Catalog, Price History & Watchlist Bookmark (`/catalog` & `/watchlist`)**
   - Navigate to the **Product Catalog** tab (`/catalog`).
   - Toggle between **Grid View** and **Table View**.
   - Click **"AI Analysis"** on any card to inspect pros/cons, sentiment score, and pricing bounds.
   - Click **"Price History"** to view the time-series fluctuation chart.
   - Click the **Bookmark** icon: Verify that the product is saved and instantly dispatched as a media bulletin to your Telegram channel!
   - Click **"Export Excel (.xlsx)"** to download the structured spreadsheet report.

4. **Step 4: Background Watchlist Cron Tracker & Telegram Alerts (`/telegram`)**
   - Navigate to the **Telegram Notification Center** tab (`/telegram`).
   - Click **"Gửi tin nhắn kiểm tra (Test Ping)"** to verify Telegram Bot connectivity.
   - The automated cron job will continuously track all bookmarked items every 30 minutes, dispatching alerts exclusively when price reductions occur.

---

## 8. License & Credits

- **Core Technologies**: FastAPI, Next.js 16, PostgreSQL, Qdrant Cloud, Redis Cloud, NVIDIA NIM, Google Gemini, Playwright, APScheduler.
- **License**: MIT License.

*Lazada Hunter &copy; 2026. All rights reserved.*
