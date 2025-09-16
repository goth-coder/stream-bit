from typing import Any, Optional, Dict, Callable
from cachetools import TTLCache
import json
import hashlib
import logging
from ...models.config import Config

logger = logging.getLogger(__name__)


class CacheService:
    """
    Serviço de cache inteligente com TTL para otimizar queries no Athena.

    Funcionalidades:
    - Cache em memória com TTL configurável
    - Configuração centralizada via Config
    - Geração automática de chaves baseada em queries
    - Padrão cache-aside com fallback automático
    - Métricas de hit/miss para debug
    """

    def __init__(self, config: Optional[Dict] = None):
        cache_config = config or Config.get_cache_config()

        self.cache_type = cache_config["cache_type"]
        self.default_ttl = cache_config["default_ttl"]
        self.max_size = cache_config["max_size"]

        # TTL específicos por tipo de query
        self.ttl_latest = cache_config["ttl_latest"]
        self.ttl_hourly = cache_config["ttl_hourly"]
        self.ttl_stats = cache_config["ttl_stats"]
        self.ttl_trend = cache_config["ttl_trend"]
        self.ttl_health = cache_config["ttl_health"]

        self.stats = {"hits": 0, "misses": 0, "sets": 0, "errors": 0}

        if self.cache_type == "memory":
            self._cache = TTLCache(maxsize=self.max_size, ttl=self.default_ttl)
            logger.info(
                f"Initialized TTLCache with maxsize={self.max_size}, ttl={self.default_ttl}s"
            )
        else:
            raise ValueError(f"Cache type '{self.cache_type}' not supported yet")

    def _generate_key(self, query: str, params: Optional[Dict] = None) -> str:
        """Gera chave única para cache baseada na query e parâmetros"""
        content = f"{query}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()[:16]  # 16 chars suficientes

    def get(self, key: str) -> Optional[Any]:
        """Recupera valor do cache"""
        try:
            if self.cache_type == "memory":
                value = self._cache.get(key)
                if value is not None:
                    self.stats["hits"] += 1
                    logger.debug(f"Cache HIT for key: {key}")
                    return value
                else:
                    self.stats["misses"] += 1
                    logger.debug(f"Cache MISS for key: {key}")
                    return None
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache GET error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Armazena valor no cache"""
        try:
            ttl = ttl or self.default_ttl

            if self.cache_type == "memory":
                # TTLCache não aceita TTL por item, usa TTL global
                self._cache[key] = value
                self.stats["sets"] += 1
                logger.debug(f"Cache SET for key: {key} (ttl={ttl}s)")
                return True
            return False
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache SET error for key {key}: {e}")
            return False

    def get_or_set(
        self, key: str, func: Callable, ttl: Optional[int] = None, *args, **kwargs
    ):
        """
        Padrão cache-aside: busca no cache ou executa função

        Returns:
            tuple: (value, from_cache: bool)
        """
        # Tenta buscar no cache primeiro
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value, True  # (value, from_cache)

        # Cache miss - executa função
        try:
            fresh_value = func(*args, **kwargs)
            self.set(key, fresh_value, ttl)
            return fresh_value, False
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Function execution error for cache key {key}: {e}")
            raise

    def query_cache(
        self,
        query: str,
        params: Optional[Dict] = None,
        func: Optional[Callable] = None,
        ttl: Optional[int] = None,
        *args,
        **kwargs,
    ):
        """
        Helper específico para queries com geração automática de chave

        Args:
            query: SQL query string
            params: Query parameters
            func: Function to execute on cache miss
            ttl: Cache TTL in seconds

        Returns:
            tuple: (result, from_cache: bool)
        """
        cache_key = self._generate_key(query, params)

        if func is None:
            # Apenas verificar se existe no cache
            cached_value = self.get(cache_key)
            return cached_value, cached_value is not None

        return self.get_or_set(cache_key, func, ttl, *args, **kwargs)

    def get_ttl_for_query_type(self, query_type: str) -> int:
        """Retorna TTL específico para tipo de query"""
        ttl_map = {
            "latest_price": self.ttl_latest,
            "hourly_prices": self.ttl_hourly,
            "individual_prices": self.ttl_hourly,  # Mesmo TTL que hourly
            "statistics": self.ttl_stats,
            "recent_trend": self.ttl_trend,
            "health_check": self.ttl_health,
            "price_change": self.ttl_latest,  # Price change com TTL similar ao latest
        }

        # Para first_price com horas específicas, usar TTL baseado no range
        if query_type.startswith("first_price_"):
            hours = query_type.split("_")[-1].replace("h", "")
            try:
                hours_int = int(hours)
                if hours_int <= 6:
                    return self.ttl_latest  # Range pequeno, cache curto
                elif hours_int <= 24:
                    return self.ttl_hourly  # Range médio
                else:
                    return self.ttl_stats  # Range longo, cache mais longo
            except ValueError:
                pass

        return ttl_map.get(query_type, self.default_ttl)

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache para debug"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        stats = {
            "cache_type": self.cache_type,
            "default_ttl": self.default_ttl,
            "max_size": self.max_size,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "sets": self.stats["sets"],
            "errors": self.stats["errors"],
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            "ttl_config": {
                "latest": self.ttl_latest,
                "hourly": self.ttl_hourly,
                "stats": self.ttl_stats,
                "trend": self.ttl_trend,
                "health": self.ttl_health,
            },
        }

        if self.cache_type == "memory":
            stats.update(
                {
                    "current_size": len(self._cache),
                    "memory_info": {
                        "currsize": getattr(self._cache, "currsize", len(self._cache)),
                        "maxsize": self._cache.maxsize,
                    },
                }
            )

        return stats

    def clear(self) -> bool:
        """Limpa todo o cache"""
        try:
            if self.cache_type == "memory":
                self._cache.clear()
                logger.info("Cache cleared successfully")
                return True
            return False
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache CLEAR error: {e}")
            return False

    def expire_key(self, key: str) -> bool:
        """Remove uma chave específica do cache"""
        try:
            if self.cache_type == "memory":
                if key in self._cache:
                    del self._cache[key]
                    logger.debug(f"Cache key expired: {key}")
                    return True
                return False
            return False
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache EXPIRE error for key {key}: {e}")
            return False
