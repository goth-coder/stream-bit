# ₿ Stream-Bit: Near Real-Time Bitcoin Data Pipeline

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-2.3+-green.svg)](https://flask.palletsprojects.com/)
[![AWS](https://img.shields.io/badge/aws-kinesis%20|%20s3%20|%20athena-orange.svg)](https://aws.amazon.com/)

## 🎯 **Overview**

Professional real-time data pipeline for **Bitcoin**, combining **Data Engineering**, **Cloud Computing**, and **Web Development**. The project implements data streaming, data lake storage, advanced analytics, and a responsive web dashboard with live updates.

> **🚀 Demo**: Dashboard with real-time synchronization between Current Price, Chart, and Statistics

### 🏆 **Key Achievements**
- ✅ **Real-time Dashboard** with Server-Sent Events + Chart.js
- ✅ **Complete AWS Pipeline** (Firehose → S3 → Athena)
- ✅ **Intelligent Caching** with TTL optimized by query type
- ✅ **Scalable MVC Architecture** with clean separation of concerns
- ✅ **Smart Synchronization** - updates only on real price changes

## 🏗️ **Technical Architecture**

### **High-Level Architecture**
```mermaid
graph LR
    A[CoinGecko API] --> B[Bitcoin Extractor]
    B --> C[Firehose Stream]
    C --> D[S3 Data Lake]
    D --> E[Athena Analytics]
    E --> F[Flask API + Cache]
    F --> G[Real-time Dashboard]
    
    H[User] --> G
    G --> H
```

### **MVC-ETL Structure**
```
src/
├── controllers/                 # 🎮 Orchestration Layer
│   ├── streaming_controller.py     # Stream pipeline coordination
│   └── web/api_controller.py       # REST API endpoints + SSE
├── models/                      # 📊 Data & Config Layer  
│   ├── config.py                   # Centralized configuration
│   └── data_schemas.py             # Pydantic data schemas
├── views/                       # 🖥️ Presentation Layer
│   └── web/                        # Web interface
│       ├── templates/              # Jinja2 HTML templates
│       ├── static/js/              # JavaScript (Chart.js + SSE)
│       └── static/css/             # Custom CSS styling
└── services/                    # ⚙️ Business Logic Layer
    ├── extractors/                 # Data extraction services
    │   └── bitcoin_extractor.py    # CoinGecko API integration
    ├── loaders/                    # Data loading services
    │   └── firehose_loader.py      # AWS Firehose streaming
    └── web/                        # Web-specific services
        ├── cache_service.py        # TTL cache management
        └── athena_service.py       # AWS Athena queries
```

## ⚡ **Quick Start**

### **1. Prerequisites**
```bash
# Python 3.8+ (recommended 3.11+)
python --version

# AWS CLI configured (optional - for advanced features)
aws configure list
```

### **2. Installation**
```bash
# Clone repository
git clone <repo-url>
cd stream-bit

# Option 1: uv (recommended - faster)
uv sync

# Option 2: traditional pip
pip install -r requirements.txt
```

### **3. Configuration**
```bash
# Copy environment file
cp .env.example .env

# Edit configurations (optional)
# AWS_REGION=us-east-1
# FLASK_DEBUG=True
```

### **4. Run**

#### 🌐 **Web Dashboard** (Main)
```bash
python app.py --mode web --port 8080
```
**Access:**
- 📊 **Dashboard**: http://localhost:8080  
- ❤️ **Health Check**: http://localhost:8080/api/health
- 📈 **Status Page**: http://localhost:8080/status
- ⚙️ **Config**: http://localhost:8080/config (dev mode)

#### 📡 **Streaming Pipeline**
```bash
# Continuous streaming to AWS
python app.py --mode stream

# Single test (demo)
python app.py --mode test
```

## 🌟 **Features and Highlights**

### 🎯 **Real-time Dashboard**
- **📊 Live Chart**: Chart.js with smart updates (only on price changes)
- **⚡ Server-Sent Events**: Data streaming with automatic fallback to polling
- **📈 Dynamic Statistics**: Automatic sync between Current Price, Chart, and Statistics

### ⚙️ **Data Pipeline**
- **🔄 Continuous Extraction**: CoinGecko API with retry logic and rate limiting
- **☁️ AWS Streaming**: Kinesis Firehose for robust ingestion
- **🗄️ Data Lake**: S3 with automatic Hive-style partitioning
- **🔍 Analytics**: AWS Athena + Glue for optimized SQL queries
- **📦 Format Conversion**: Automatic JSON → Parquet via Firehose

### 🧠 **Intelligent Architecture**
- **⚡ TTL Cache**: Optimized by type
- **🔀 Synchronization**: Coordinated updates between all components
- **📊 Performance**: Sliding window (150 points) for fluid charts

### 🔒 **Quality and Reliability**
- **⚠️ Error Handling**: Comprehensive error pages and API responses
- **📝 Structured Logging**: Structured logging with appropriate levels
- **📊 Monitoring**: Health checks and status page with system metrics

## 💻 **Detailed Tech Stack**

### **🐍 Backend Core**
| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.8+ | Main language |
| **Flask** | 2.3+ | Web framework + REST API |
| **TTLCache** | 5.3+ | In-memory cache with TTL |
| **Pydantic** | 2.0+ | Data validation and schemas |
| **asyncio** | Built-in | Async operations |

### **☁️ Cloud & Data**
| Service | Functionality |
|---------|---------------|
| **AWS Kinesis Firehose** | Robust streaming pipeline |
| **AWS S3** | Data lake with Hive partitioning |
| **AWS Athena** | Serverless query engine |
| **AWS Glue** | Data catalog + format conversion |
| **CoinGecko API** | Bitcoin data source |

### **🎨 Frontend & UI**
| Technology | Version | Purpose |
|------------|---------|---------|
| **Bootstrap** | 5.3 | Responsive CSS framework |
| **Chart.js** | 4.4 | Interactive charts |
| **Server-Sent Events** | HTML5 | Real-time updates |
| **Jinja2** | 3.1+ | Template engine |
| **Vanilla JavaScript** | ES6+ | DOM manipulation |

### **� Development & Quality**
| Tool | Functionality |
|------|---------------|
| **structlog** | Structured logging |
| **mypy** | Static type checking |

## 🎯 **Use Cases and Examples**

### **👨‍💻 For Developers**
```bash
# Development mode with hot-reload
python app.py --mode web --port 8080 --debug

# Application health check  
curl http://localhost:8080/api/health
# Response: {"status": "healthy", "timestamp": "2025-09-16T10:30:00Z"}

# Config page (debug info)
curl http://localhost:8080/config
```

### **📊 For Data Analysis**
```bash
# Latest Bitcoin price
curl http://localhost:8080/api/bitcoin/latest
# Response: {"price_brl": 617094.0, "timestamp": "2025-09-16T10:30:00Z"}

# Historical hourly data (last 24h)
curl http://localhost:8080/api/bitcoin/hourly?hours=24

# Statistics by period
curl "http://localhost:8080/api/bitcoin/statistics?hours=6"
# Response: {"avg": 615000, "min": 610000, "max": 620000, "count": 360}
```

### **🔍 For Monitoring**
```bash
# Complete status page
curl http://localhost:8080/status

# Cache metrics
curl http://localhost:8080/api/cache/stats
# Response: {"hits": 245, "misses": 12, "hit_rate": 95.3}
```

### **📡 For DevOps**
```bash
# Stream mode (production)
python app.py --mode stream --log-level INFO

# Test mode (validation)  
python app.py --mode test
```

## 🚀 **Performance and Metrics**

### **⚡ Performance Benchmarks**
| Metric | Value | Observation |
|--------|-------|-------------|
| **API Latency** | <200ms | TTL cache optimized |
| **Stream Throughput** | 100+ req/min | CoinGecko rate limits |
| **Chart Update** | <50ms | Only real changes (>R$ 0.01) |
| **Memory Usage** | ~50MB | TTL cache + sliding window |

### **🎯 Implemented Optimizations**
- ✅ **Smart Caching**: TTL differentiated by query type
- ✅ **Sliding Window**: Maximum 150 points in chart for fluidity
- ✅ **Price Change Detection**: Only updates on changes >R$ 0.01
- ✅ **Async Operations**: ConcurrentFutures for I/O operations
- ✅ **Query Optimization**: Partition projection in Athena

## 📚 **Complete Documentation**

| Document | Content |
|----------|---------|
| **[README.md](README.md)** | Setup, features, and usage |
| **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** | Endpoints and examples |

---

> **💡 Tip**: Use `python app.py --help` to see all available options

**Developed with ❤️ to demonstrate competencies in Data Engineering, Cloud Computing, and APIs**
