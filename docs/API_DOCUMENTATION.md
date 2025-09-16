# 📊 API Documentation - Stream-Bit

Complete documentation of the REST API endpoints, real-time streams, and integration examples for the **Stream-Bit** Bitcoin data pipeline project.

## 📋 **Index**

1. [Quick Start](#-quick-start)
2. [Authentication](#-authentication)
3. [Core Endpoints](#-core-endpoints)
4. [Real-Time Streams](#-real-time-streams)
5. [Error Handling](#-error-handling)
6. [Client Examples](#-client-examples)
7. [Performance and Caching](#-performance-and-caching)
8. [Schema and Data Types](#-schema-and-data-types)

## 🚀 **Quick Start**

### **Base URL**
```
http://localhost:8080
```

### **Basic Usage**
```bash
# Application health check
curl http://localhost:8080/api/health

# Latest Bitcoin price
curl http://localhost:8080/api/bitcoin/latest

# Historical data (last 6 hours)
curl "http://localhost:8080/api/bitcoin/hourly?hours=6"
```

### **Response Formats**
All endpoints return JSON with standardized structure:
```json
{
  "data": {...},
  "timestamp": "2025-01-16T10:30:00Z",
  "status": "success",
  "cache_info": {
    "hit": true,
    "ttl_remaining": 25
  }
}
```

## 🔐 **Authentication**

Currently the API does **not require authentication** for read operations. All endpoints are publicly accessible.

> **🔒 Production Note**: In production environments, consider implementing API keys or rate limiting.

## 🎯 **Core Endpoints**

### **1. Health Check**
**`GET /api/health`**

System health check and service status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-16T10:30:00Z",
  "uptime": "2d 14h 32m",
  "services": {
    "api": "operational",
    "cache": "operational",
    "extractor": "operational"
  }
}
```

**Status Codes:**
- `200`: System healthy
- `503`: System degraded or error

---

### **2. Latest Bitcoin Price**
**`GET /api/bitcoin/latest`**

Get current Bitcoin price in BRL with metadata.

**Response:**
```json
{
  "data": {
    "price_brl": 617094.0,
    "price_usd": 108250.0,
    "timestamp": "2025-01-16T10:30:00Z",
    "change_24h": 2.34,
    "volume_24h": 28500000000,
    "market_cap": 2100000000000
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "status": "success",
  "cache_info": {
    "hit": true,
    "ttl_remaining": 28
  }
}
```

**Parameters:** None

**Cache:** 30 seconds TTL

---

### **3. Hourly Historical Data**
**`GET /api/bitcoin/hourly`**

Get historical hourly data for charts and analysis.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | integer | 24 | Hours to retrieve (max: 168) |
| `limit` | integer | 150 | Maximum points returned |

**Example:**
```bash
curl "http://localhost:8080/api/bitcoin/hourly?hours=12&limit=50"
```

**Response:**
```json
{
  "data": {
    "prices": [
      {
        "timestamp": "2025-01-16T09:00:00Z",
        "price_brl": 615000.0,
        "price_usd": 107890.0
      },
      {
        "timestamp": "2025-01-16T10:00:00Z", 
        "price_brl": 617094.0,
        "price_usd": 108250.0
      }
    ],
    "total_points": 12,
    "period_hours": 12,
    "interval": "1h"
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "status": "success",
  "cache_info": {
    "hit": false,
    "ttl_remaining": 60
  }
}
```

**Cache:** 60 seconds TTL

---

### **4. Statistical Summary**
**`GET /api/bitcoin/statistics`**

Statistical calculations for specified periods.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours` | integer | 24 | Period for calculation |
| `include_trend` | boolean | false | Include trend analysis |

**Example:**
```bash
curl "http://localhost:8080/api/bitcoin/statistics?hours=6&include_trend=true"
```

**Response:**
```json
{
  "data": {
    "period_hours": 6,
    "total_points": 360,
    "statistics": {
      "average": 615847.23,
      "minimum": 610000.0,
      "maximum": 620000.0,
      "median": 615500.0,
      "std_deviation": 2845.67,
      "variance": 8096847.12
    },
    "trend": {
      "direction": "upward",
      "strength": 0.67,
      "change_percent": 1.23
    },
    "period": {
      "start": "2025-01-16T04:30:00Z",
      "end": "2025-01-16T10:30:00Z"
    }
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "status": "success",
  "cache_info": {
    "hit": true,
    "ttl_remaining": 95
  }
}
```

**Cache:** 120 seconds TTL

---

### **5. Cache Statistics**
**`GET /api/cache/stats`**

Information about cache performance and metrics.

**Response:**
```json
{
  "data": {
    "cache_stats": {
      "total_requests": 1245,
      "cache_hits": 1187,
      "cache_misses": 58,
      "hit_rate": 95.34
    },
    "memory_usage": {
      "current_size": 24576,
      "max_size": 1048576,
      "utilization": 2.34
    },
    "ttl_info": {
      "latest": 30,
      "hourly": 60,
      "statistics": 120,
      "cache_stats": 300
    }
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "status": "success"
}
```

**Cache:** 300 seconds TTL

---

### **6. System Status**
**`GET /status`**

Complete status page with detailed metrics.

**Response:**
```json
{
  "system": {
    "status": "operational",
    "uptime": "2d 14h 32m",
    "timestamp": "2025-01-16T10:30:00Z"
  },
  "services": {
    "api_server": "operational",
    "cache_service": "operational", 
    "bitcoin_extractor": "operational",
    "athena_connector": "operational"
  },
  "performance": {
    "avg_response_time": 145,
    "requests_per_minute": 34,
    "error_rate": 0.02
  },
  "cache": {
    "hit_rate": 95.34,
    "memory_usage": 2.34,
    "active_keys": 156
  },
  "last_update": "2025-01-16T10:29:45Z"
}
```

## 📡 **Real-Time Streams**

### **Server-Sent Events (SSE)**
**`GET /api/bitcoin/stream`**

Real-time Bitcoin price stream using Server-Sent Events.

**Connection:**
```javascript
const eventSource = new EventSource('/api/bitcoin/stream');

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('New price:', data.price_brl);
};

eventSource.onerror = function(event) {
    console.error('SSE connection error:', event);
};
```

**Event Format:**
```
data: {"price_brl": 617094.0, "timestamp": "2025-01-16T10:30:00Z", "change": 150.5}

data: {"price_brl": 617244.5, "timestamp": "2025-01-16T10:30:30Z", "change": 150.5}
```

**Event Types:**
- `price_update`: New price (only when change > R$ 0.01)
- `heartbeat`: Connection maintenance (every 30s)
- `error`: Error notifications

### **WebSocket Alternative**
Currently not implemented. Use SSE with polling fallback.

## ⚠️ **Error Handling**

### **Standard Error Format**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid parameter 'hours': must be between 1 and 168",
    "details": {
      "parameter": "hours",
      "provided": 200,
      "allowed_range": "1-168"
    }
  },
  "timestamp": "2025-01-16T10:30:00Z",
  "status": "error"
}
```

### **HTTP Status Codes**
| Code | Description | Usage |
|------|-------------|-------|
| `200` | Success | Request completed successfully |
| `400` | Bad Request | Invalid parameters or format |
| `404` | Not Found | Endpoint not found |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Server processing error |
| `503` | Service Unavailable | Service degraded |

### **Common Error Codes**
| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Invalid parameters |
| `DATA_NOT_FOUND` | No data for period |
| `EXTERNAL_API_ERROR` | CoinGecko API error |
| `CACHE_ERROR` | Cache service error |
| `DATABASE_ERROR` | Athena query error |

### **Error Examples**
```bash
# Invalid parameter
curl "http://localhost:8080/api/bitcoin/hourly?hours=999"
# Response: 400 Bad Request

# Non-existent endpoint
curl "http://localhost:8080/api/invalid"
# Response: 404 Not Found
```

## 🔧 **Client Examples**

### **Python Client**
```python
import requests
from datetime import datetime

class StreamBitClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        
    def get_latest_price(self):
        """Get latest Bitcoin price"""
        response = requests.get(f"{self.base_url}/api/bitcoin/latest")
        response.raise_for_status()
        return response.json()
    
    def get_hourly_data(self, hours=24):
        """Get hourly historical data"""
        params = {"hours": hours}
        response = requests.get(
            f"{self.base_url}/api/bitcoin/hourly", 
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_statistics(self, hours=24, include_trend=False):
        """Get statistical summary"""
        params = {
            "hours": hours,
            "include_trend": include_trend
        }
        response = requests.get(
            f"{self.base_url}/api/bitcoin/statistics",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def stream_prices(self, callback):
        """Stream real-time prices via SSE"""
        import sseclient
        
        url = f"{self.base_url}/api/bitcoin/stream"
        response = requests.get(url, stream=True)
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            if event.data:
                import json
                data = json.loads(event.data)
                callback(data)

# Usage example
client = StreamBitClient()

# Latest price
latest = client.get_latest_price()
print(f"Bitcoin: R$ {latest['data']['price_brl']:,.2f}")

# Last 6 hours
historical = client.get_hourly_data(hours=6)
prices = historical['data']['prices']
print(f"Retrieved {len(prices)} hourly points")

# Statistics
stats = client.get_statistics(hours=24, include_trend=True)
avg_price = stats['data']['statistics']['average']
trend = stats['data']['trend']['direction']
print(f"24h average: R$ {avg_price:,.2f} (trend: {trend})")

# Real-time stream
def on_price_update(data):
    print(f"New price: R$ {data['price_brl']:,.2f}")

client.stream_prices(on_price_update)
```

### **JavaScript Client**
```javascript
class StreamBitClient {
    constructor(baseUrl = 'http://localhost:8080') {
        this.baseUrl = baseUrl;
    }
    
    async getLatestPrice() {
        const response = await fetch(`${this.baseUrl}/api/bitcoin/latest`);
        if (!response.ok) throw new Error('Failed to fetch latest price');
        return await response.json();
    }
    
    async getHourlyData(hours = 24) {
        const url = `${this.baseUrl}/api/bitcoin/hourly?hours=${hours}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch hourly data');
        return await response.json();
    }
    
    async getStatistics(hours = 24, includeTrend = false) {
        const params = new URLSearchParams({
            hours: hours.toString(),
            include_trend: includeTrend.toString()
        });
        const url = `${this.baseUrl}/api/bitcoin/statistics?${params}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch statistics');
        return await response.json();
    }
    
    streamPrices(callback, onError = console.error) {
        const eventSource = new EventSource(`${this.baseUrl}/api/bitcoin/stream`);
        
        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                callback(data);
            } catch (error) {
                onError('Failed to parse SSE data:', error);
            }
        };
        
        eventSource.onerror = (error) => {
            onError('SSE connection error:', error);
        };
        
        return eventSource; // For manual connection management
    }
}

// Usage example
const client = new StreamBitClient();

// Latest price
client.getLatestPrice()
    .then(data => {
        console.log(`Bitcoin: R$ ${data.data.price_brl.toLocaleString()}`);
    })
    .catch(console.error);

// Historical data for chart
client.getHourlyData(12)
    .then(data => {
        const prices = data.data.prices;
        console.log(`Retrieved ${prices.length} hourly points`);
        
        // Use with Chart.js
        updateChart(prices);
    })
    .catch(console.error);

// Real-time updates
const eventSource = client.streamPrices(
    (data) => {
        console.log(`New price: R$ ${data.price_brl.toLocaleString()}`);
        updateDashboard(data);
    },
    (error) => {
        console.error('Stream error:', error);
        // Implement fallback to polling
        fallbackToPolling();
    }
);

// Connection management
window.addEventListener('beforeunload', () => {
    eventSource.close();
});
```

### **Node.js Client**
```javascript
const axios = require('axios');
const EventSource = require('eventsource');

class StreamBitClient {
    constructor(baseUrl = 'http://localhost:8080') {
        this.baseUrl = baseUrl;
    }
    
    async getLatestPrice() {
        const response = await axios.get(`${this.baseUrl}/api/bitcoin/latest`);
        return response.data;
    }
    
    async getHourlyData(hours = 24) {
        const response = await axios.get(`${this.baseUrl}/api/bitcoin/hourly`, {
            params: { hours }
        });
        return response.data;
    }
    
    async getStatistics(hours = 24, includeTrend = false) {
        const response = await axios.get(`${this.baseUrl}/api/bitcoin/statistics`, {
            params: { 
                hours,
                include_trend: includeTrend
            }
        });
        return response.data;
    }
    
    streamPrices(callback, onError = console.error) {
        const eventSource = new EventSource(`${this.baseUrl}/api/bitcoin/stream`);
        
        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                callback(data);
            } catch (error) {
                onError('Failed to parse SSE data:', error);
            }
        };
        
        eventSource.onerror = (error) => {
            onError('SSE connection error:', error);
        };
        
        return eventSource;
    }
}

// Usage example
const client = new StreamBitClient();

(async () => {
    try {
        // Latest price
        const latest = await client.getLatestPrice();
        console.log(`Bitcoin: R$ ${latest.data.price_brl.toLocaleString()}`);
        
        // Statistics
        const stats = await client.getStatistics(24, true);
        const avg = stats.data.statistics.average;
        const trend = stats.data.trend.direction;
        console.log(`24h average: R$ ${avg.toLocaleString()} (${trend})`);
        
        // Real-time stream
        const eventSource = client.streamPrices(
            (data) => {
                console.log(`New price: R$ ${data.price_brl.toLocaleString()}`);
            },
            console.error
        );
        
        // Graceful shutdown
        process.on('SIGINT', () => {
            eventSource.close();
            process.exit(0);
        });
        
    } catch (error) {
        console.error('Error:', error.message);
    }
})();
```

## ⚡ **Performance and Caching**

### **Cache Strategy**
| Endpoint | TTL | Rationale |
|----------|-----|-----------|
| `/api/bitcoin/latest` | 30s | Real-time updates needed |
| `/api/bitcoin/hourly` | 60s | Historical data, less critical |
| `/api/bitcoin/statistics` | 120s | Computationally expensive |
| `/api/cache/stats` | 300s | Administrative data |

### **Performance Tips**
1. **Use appropriate periods**: Don't request more data than needed
2. **Respect cache TTL**: Avoid excessive requests within TTL
3. **Use SSE for real-time**: More efficient than polling
4. **Implement client-side caching**: Reduce redundant requests

### **Rate Limiting**
- **No current limits**: Open for development/demo
- **Planned limits**: 1000 requests/hour in production
- **Burst allowance**: Up to 10 requests/minute

### **Performance Metrics**
```bash
# Cache performance
curl http://localhost:8080/api/cache/stats

# System status
curl http://localhost:8080/status
```

## 📊 **Schema and Data Types**

### **Price Data Schema**
```json
{
  "price_brl": "number (float)",
  "price_usd": "number (float)", 
  "timestamp": "string (ISO 8601)",
  "change_24h": "number (float, optional)",
  "volume_24h": "number (float, optional)",
  "market_cap": "number (float, optional)"
}
```

### **Historical Data Schema**
```json
{
  "prices": [
    {
      "timestamp": "string (ISO 8601)",
      "price_brl": "number (float)",
      "price_usd": "number (float)"
    }
  ],
  "total_points": "number (integer)",
  "period_hours": "number (integer)",
  "interval": "string ('1h', '1d', etc.)"
}
```

### **Statistics Schema**
```json
{
  "period_hours": "number (integer)",
  "total_points": "number (integer)",
  "statistics": {
    "average": "number (float)",
    "minimum": "number (float)",
    "maximum": "number (float)",
    "median": "number (float)",
    "std_deviation": "number (float)",
    "variance": "number (float)"
  },
  "trend": {
    "direction": "string ('upward'|'downward'|'stable')",
    "strength": "number (float, 0-1)",
    "change_percent": "number (float)"
  },
  "period": {
    "start": "string (ISO 8601)",
    "end": "string (ISO 8601)"
  }
}
```

### **Standard Response Schema**
```json
{
  "data": "object (specific to endpoint)",
  "timestamp": "string (ISO 8601)",
  "status": "string ('success'|'error')",
  "cache_info": {
    "hit": "boolean",
    "ttl_remaining": "number (seconds)"
  }
}
```

### **Error Response Schema**
```json
{
  "error": {
    "code": "string (error code)",
    "message": "string (human-readable message)",
    "details": "object (optional additional info)"
  },
  "timestamp": "string (ISO 8601)",
  "status": "string ('error')"
}
```

---

## 🔗 **Additional Resources**

- **[Main README](README.md)**: Setup and general overview
- **[Architecture](ARCHITECTURE.md)**: System design and diagrams
- **[Deployment](DEPLOYMENT.md)**: Production deployment guide
- **[Changelog](changelog.md)**: Version history

---

## 📞 **Support**

For questions about the API or integration issues:

1. **Check logs**: System logs contain detailed error information
2. **Health check**: Use `/api/health` to verify system status
3. **Test endpoints**: Use test environment for experimentation
4. **Documentation**: This document contains complete specifications

---

> **💡 Tip**: Use browser developer tools to inspect real requests in the dashboard. All calls made by the frontend are documented here.

**Comprehensive REST API for Bitcoin data analysis and real-time monitoring**
