import os
from typing import Dict, Any
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()


class Config:
    """
    Configuração centralizada para toda a aplicação Stream-Bit.

    Inclui configurações para:
    - Pipeline de streaming (extractors, loaders)
    - Dashboard Flask (web interface)
    - Cache (TTL, performance)
    - AWS Services (Athena, S3, Firehose)
    - Logging e debug
    """

    # === STREAMING PIPELINE CONFIG ===

    # Bitcoin API
    BITCOIN_API_URL = os.getenv(
        "BITCOIN_API_URL", "https://api.coingecko.com/api/v3/simple/price"
    )
    BITCOIN_API_PARAMS = {
        "ids": "bitcoin",
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
    }

    # AWS Configuration
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Firehose
    FIREHOSE_STREAM_NAME = os.getenv("FIREHOSE_STREAM_NAME")
    S3_DATA_LAKE_BUCKET = os.getenv("S3_DATA_LAKE_BUCKET")

    # Athena
    ATHENA_DATABASE = os.getenv("ATHENA_DATABASE")
    ATHENA_WORKGROUP = os.getenv("ATHENA_WORKGROUP", "primary")
    ATHENA_OUTPUT_LOCATION = os.getenv("ATHENA_OUTPUT_LOCATION")
    BITCOIN_TABLE_NAME = os.getenv("BITCOIN_TABLE_NAME")

    # === FLASK WEB CONFIG ===

    # Flask Application
    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FLASK_SECRET_KEY = os.getenv(
        "FLASK_SECRET_KEY", "bitcoin-dashboard-dev-key-change-in-production"
    )
    FLASK_DEBUG = FLASK_ENV == "development"

    # Cache Configuration
    CACHE_TYPE = os.getenv("CACHE_TYPE", "memory")  # memory ou redis
    CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", 60))
    CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", 1000))

    # Cache TTL específico por tipo de query (otimizado para performance e freshness)
    CACHE_TTL_LATEST = int(
        os.getenv("CACHE_TTL_LATEST", 60)
    )  # Latest price: 1min (mais fresco)
    CACHE_TTL_HOURLY = int(
        os.getenv("CACHE_TTL_HOURLY", 180)
    )  # Hourly data: 3min (reduzido)
    CACHE_TTL_STATS = int(
        os.getenv("CACHE_TTL_STATS", 300)
    )  # Statistics: 5min (reduzido)
    CACHE_TTL_TREND = int(
        os.getenv("CACHE_TTL_TREND", 120)
    )  # Recent trend: 2min (reduzido)
    CACHE_TTL_HEALTH = int(
        os.getenv("CACHE_TTL_HEALTH", 180)
    )  # Health check: 3min (reduzido)

    # === TIMING CONFIG ===

    # Extractor timing
    EXTRACTOR_SLEEP_BASE = int(os.getenv("EXTRACTOR_SLEEP_BASE", 6))
    EXTRACTOR_SLEEP_JITTER_MIN = int(os.getenv("EXTRACTOR_SLEEP_JITTER_MIN", 2))
    EXTRACTOR_SLEEP_JITTER_MAX = int(os.getenv("EXTRACTOR_SLEEP_JITTER_MAX", 5))

    # Streaming timing
    STREAMING_INTERVAL = int(os.getenv("STREAMING_INTERVAL", 8))

    # Frontend polling timing
    FRONTEND_POLL_INTERVAL = int(os.getenv("FRONTEND_POLL_INTERVAL", 15))  # 15s
    SSE_UPDATE_INTERVAL = int(os.getenv("SSE_UPDATE_INTERVAL", 15))  # 15s

    # === LOGGING CONFIG ===

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = os.getenv("LOG_FILE", "stream-bit.log")

    # === PERFORMANCE CONFIG ===

    # Query limits para evitar queries muito pesadas
    MAX_HOURLY_RANGE = int(os.getenv("MAX_HOURLY_RANGE", 168))  # 1 semana
    MAX_TREND_RANGE = int(os.getenv("MAX_TREND_RANGE", 1440))  # 24 horas

    # Timeouts
    ATHENA_QUERY_TIMEOUT = int(os.getenv("ATHENA_QUERY_TIMEOUT", 60))  # 1 minuto
    API_REQUEST_TIMEOUT = int(os.getenv("API_REQUEST_TIMEOUT", 30))  # 30 segundos

    @classmethod
    def get_flask_config(cls) -> Dict[str, Any]:
        """Retorna configurações específicas do Flask"""
        return {
            "SECRET_KEY": cls.FLASK_SECRET_KEY,
            "DEBUG": cls.FLASK_DEBUG,
            "HOST": cls.FLASK_HOST,
            "PORT": cls.FLASK_PORT,
            "ENV": cls.FLASK_ENV,
        }

    @classmethod
    def get_cache_config(cls) -> Dict[str, Any]:
        """Retorna configurações específicas do cache"""
        return {
            "cache_type": cls.CACHE_TYPE,
            "default_ttl": cls.CACHE_DEFAULT_TTL,
            "max_size": cls.CACHE_MAX_SIZE,
            "ttl_latest": cls.CACHE_TTL_LATEST,
            "ttl_hourly": cls.CACHE_TTL_HOURLY,
            "ttl_stats": cls.CACHE_TTL_STATS,
            "ttl_trend": cls.CACHE_TTL_TREND,
            "ttl_health": cls.CACHE_TTL_HEALTH,
        }

    @classmethod
    def get_aws_config(cls) -> Dict[str, Any]:
        """Retorna configurações específicas da AWS"""
        return {
            "region_name": cls.AWS_REGION,
            "aws_access_key_id": cls.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": cls.AWS_SECRET_ACCESS_KEY,
            "firehose_stream": cls.FIREHOSE_STREAM_NAME,
            "s3_bucket": cls.S3_DATA_LAKE_BUCKET,
            "athena_database": cls.ATHENA_DATABASE,
            "athena_workgroup": cls.ATHENA_WORKGROUP,
            "athena_output": cls.ATHENA_OUTPUT_LOCATION,
            "bitcoin_table": cls.BITCOIN_TABLE_NAME,
        }

    @classmethod
    def get_timing_config(cls) -> Dict[str, Any]:
        """Retorna configurações de timing"""
        return {
            "extractor_base": cls.EXTRACTOR_SLEEP_BASE,
            "extractor_jitter_min": cls.EXTRACTOR_SLEEP_JITTER_MIN,
            "extractor_jitter_max": cls.EXTRACTOR_SLEEP_JITTER_MAX,
            "streaming_interval": cls.STREAMING_INTERVAL,
            "frontend_poll": cls.FRONTEND_POLL_INTERVAL,
            "sse_update": cls.SSE_UPDATE_INTERVAL,
        }

    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Valida configurações críticas e retorna status"""
        errors = []
        warnings = []

        # Validações críticas
        if not cls.AWS_ACCESS_KEY_ID:
            errors.append("AWS_ACCESS_KEY_ID not configured")

        if not cls.AWS_SECRET_ACCESS_KEY:
            errors.append("AWS_SECRET_ACCESS_KEY not configured")

        if cls.FLASK_SECRET_KEY == "bitcoin-dashboard-dev-key-change-in-production":
            warnings.append("Using default Flask secret key - change in production")

        # Validações de ranges
        if cls.CACHE_DEFAULT_TTL < 10:
            warnings.append("Cache TTL very low - may cause excessive queries")

        if cls.FRONTEND_POLL_INTERVAL < 5:
            warnings.append("Frontend polling very frequent - may overload API")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "config_source": "environment" if cls.AWS_ACCESS_KEY_ID else "defaults",
        }
