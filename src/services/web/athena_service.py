import boto3
from typing import Dict, List, Any, Tuple
import time
import logging
from .cache_service import CacheService
from ...models.config import Config

logger = logging.getLogger(__name__)


class AthenaService:
    """
    Serviço para executar queries no AWS Athena com cache inteligente.

    Funcionalidades:
    - Execução de queries com cache TTL baseado em configuração
    - Queries otimizadas para dados Bitcoin
    - Agregações temporais (hourly, daily)
    - Estatísticas e métricas de performance
    - Configuração centralizada via Config
    """

    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        aws_config = Config.get_aws_config()

        # Configurar cliente Athena
        self.athena = boto3.client(
            "athena",
            region_name=aws_config["region_name"],
            aws_access_key_id=aws_config["aws_access_key_id"],
            aws_secret_access_key=aws_config["aws_secret_access_key"],
        )

        # Configurações do Athena
        self.s3_output = aws_config["athena_output"]
        self.database = aws_config["athena_database"]
        self.workgroup = aws_config["athena_workgroup"]
        self.table_name = aws_config["bitcoin_table"]

        logger.info(
            f"AthenaService initialized - database: {self.database}, table: {self.table_name}"
        )

    def _execute_athena_query(self, query: str) -> List[Dict[str, Any]]:
        """Executa query diretamente no Athena (sem cache)"""
        try:
            logger.info(f"Executing Athena query: {query[:100]}...")

            # Inicia execução da query
            response = self.athena.start_query_execution(
                QueryString=query,
                ResultConfiguration={"OutputLocation": self.s3_output},
                WorkGroup=self.workgroup,
            )

            query_execution_id = response["QueryExecutionId"]
            logger.debug(f"Query execution ID: {query_execution_id}")

            # Aguarda execução completar
            max_wait_time = Config.ATHENA_QUERY_TIMEOUT
            wait_time = 0

            while wait_time < max_wait_time:
                result = self.athena.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = result["QueryExecution"]["Status"]["State"]

                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "CANCELLED"]:
                    error_reason = result["QueryExecution"]["Status"].get(
                        "StateChangeReason", "Unknown error"
                    )
                    raise Exception(f"Query failed: {error_reason}")

                time.sleep(1)
                wait_time += 1

            if wait_time >= max_wait_time:
                raise Exception(f"Query timeout after {max_wait_time} seconds")

            # Busca resultados
            results = self.athena.get_query_results(QueryExecutionId=query_execution_id)

            # Processa resultados
            columns = [
                col["Label"]
                for col in results["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            ]
            rows = []

            for row in results["ResultSet"]["Rows"][1:]:  # Pula header
                values = [col.get("VarCharValue", "") for col in row["Data"]]
                rows.append(dict(zip(columns, values)))

            logger.info(f"Query completed successfully - {len(rows)} rows returned")
            return rows

        except Exception as e:
            logger.error(f"Athena query error: {e}")
            raise

    def _execute_query_with_cache(
        self, query: str, query_type: str = "default"
    ) -> Tuple[Any, bool]:
        """Executa query com cache automático usando TTL específico"""
        cache_ttl = self.cache_service.get_ttl_for_query_type(query_type)

        # Criar função wrapper que já tem a query incluída
        def execute_query():
            return self._execute_athena_query(query)

        result, from_cache = self.cache_service.get_or_set(
            key=self.cache_service._generate_key(query, {}),
            func=execute_query,
            ttl=cache_ttl,
        )

        # Garantir que sempre retornamos uma lista, mesmo se result for None
        if result is None:
            result = []
        return result, from_cache

    def get_first_price_in_range(self, hours: int = 24) -> Dict[str, Any]:
        """Busca o primeiro preço no range especificado para calcular price change"""
        # Usar estrutura similar à hourly mas ordenando por data para pegar o primeiro
        query = f"""
        SELECT 
            date_trunc('hour', coleta) as hour_period,
            avg(cast(price_brl as double)) as avg_price,
            min(coleta) as timestamp,
            count(*) as data_points
        FROM {self.database}.{self.table_name}
        WHERE coleta >= current_timestamp - interval '{hours}' hour
        GROUP BY date_trunc('hour', coleta)
        ORDER BY hour_period ASC
        LIMIT 1
        """

        try:
            result, from_cache = self._execute_query_with_cache(
                query, f"first_price_{hours}h"
            )

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "query_type": f"first_price_{hours}h",
                "hours": hours,
                "cache_ttl": self.cache_service.get_ttl_for_query_type("price_change"),
            }
        except Exception as e:
            logger.error(f"Error getting first price in {hours}h range: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "query_type": f"first_price_{hours}h",
                "hours": hours,
            }

    def get_latest_bitcoin_price(self) -> Dict[str, Any]:
        """Busca último preço do Bitcoin usando estrutura da query hourly que funciona"""
        query = f"""
        SELECT 
            max(coleta) as timestamp,
            avg(cast(price_brl as double)) as price_brl,
            avg(cast(price_usd as double)) as price_usd,
            max(currency) as currency
        FROM {self.database}.{self.table_name}
        WHERE coleta >= current_timestamp - interval '1' hour
        """

        try:
            result, from_cache = self._execute_query_with_cache(query, "latest_price")

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "query_type": "latest_price",
                "cache_ttl": self.cache_service.ttl_latest,
            }
        except Exception as e:
            logger.error(f"Error getting latest price: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "query_type": "latest_price",
            }

    def get_individual_prices_working(self, hours: int = 24) -> Dict[str, Any]:
        """Busca preços individuais sem agrupamento por hora para chart precision"""
        query = f"""
        SELECT 
            coleta as timestamp,
            cast(price_brl as double) as price_brl,
            currency
        FROM {self.database}.{self.table_name}
        WHERE coleta >= current_timestamp - interval '{hours}' hour
        ORDER BY coleta ASC
        LIMIT 1000
        """

        try:
            result, from_cache = self._execute_query_with_cache(
                query, f"individual_raw_{hours}h"
            )

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "query_type": f"individual_raw_{hours}h",
                "hours": hours,
                "cache_ttl": self.cache_service.get_ttl_for_query_type(
                    "individual_prices"
                ),
            }
        except Exception as e:
            logger.error(f"Error getting individual prices: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "query_type": f"individual_raw_{hours}h",
                "hours": hours,
            }

    def get_hourly_prices(self, hours: int = 24) -> Dict[str, Any]:
        """Busca preços agregados por hora com cache otimizado"""
        # Aplicar limites de configuração
        hours = min(hours, Config.MAX_HOURLY_RANGE)
        hours = max(hours, 1)

        query = f"""
        SELECT 
            date_trunc('hour', coleta) as hour_period,
            date_trunc('hour', coleta) as timestamp,
            avg(cast(price_brl as double)) as avg_price,
            min(cast(price_brl as double)) as min_price,
            max(cast(price_brl as double)) as max_price,
            count(*) as data_points,
            stddev(cast(price_brl as double)) / avg(cast(price_brl as double)) * 100 as price_volatility
        FROM {self.database}.{self.table_name}
        WHERE coleta >= current_timestamp - interval '{hours}' hour
        GROUP BY date_trunc('hour', coleta)
        ORDER BY hour_period ASC
        LIMIT {hours + 5}
        """

        try:
            # Usar cache service diretamente para incluir parâmetros específicos
            cache_ttl = self.cache_service.get_ttl_for_query_type("hourly_prices")
            cache_key = self.cache_service._generate_key(query, {"hours": hours})

            def execute_query():
                return self._execute_athena_query(query)

            result, from_cache = self.cache_service.get_or_set(
                key=cache_key,
                func=execute_query,
                ttl=cache_ttl,
            )

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "period_hours": hours,
                "query_type": "hourly_prices",
                "cache_ttl": self.cache_service.ttl_hourly,
            }
        except Exception as e:
            logger.error(f"Error getting hourly prices: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "period_hours": hours,
                "query_type": "hourly_prices",
            }

    def get_individual_prices(self, hours: int = 24) -> Dict[str, Any]:
        """Busca preços individuais sem agrupamento por hora"""
        # Aplicar limites de configuração
        hours = min(hours, Config.MAX_HOURLY_RANGE)
        hours = max(hours, 1)

        query = f"""
        SELECT 
            coleta as timestamp,
            price_brl,
            price_usd
        FROM {self.database}.{self.table_name}
        WHERE coleta >= current_timestamp - interval '{hours}' hour
        ORDER BY coleta ASC
        """

        try:
            # Usar cache service diretamente para incluir parâmetros específicos
            cache_ttl = self.cache_service.get_ttl_for_query_type("individual_prices")
            cache_key = self.cache_service._generate_key(query, {"hours": hours})

            def execute_query():
                return self._execute_athena_query(query)

            result, from_cache = self.cache_service.get_or_set(
                key=cache_key,
                func=execute_query,
                ttl=cache_ttl,
            )

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "period_hours": hours,
                "query_type": "individual_prices",
                "cache_ttl": self.cache_service.ttl_hourly,
            }
        except Exception as e:
            logger.error(f"Error getting individual prices: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "period_hours": hours,
                "query_type": "individual_prices",
            }

    def get_price_statistics(self) -> Dict[str, Any]:
        """Busca estatísticas da última semana com cache otimizado"""
        query = f"""
        SELECT 
            count(*) as total_records,
            avg(cast(price_brl as double)) as avg_price,
            min(cast(price_brl as double)) as min_price,
            max(cast(price_brl as double)) as max_price,
            stddev(cast(price_brl as double)) / avg(cast(price_brl as double)) * 100 as price_volatility,
            min(coleta) as first_record,
            max(coleta) as last_record,
            approx_percentile(cast(price_brl as double), 0.5) as median_price,
            (max(cast(price_brl as double)) - min(cast(price_brl as double))) / min(cast(price_brl as double)) * 100 as daily_variation_percent
        FROM {self.database}.{self.table_name}
        WHERE dt >= date_format(current_date - interval '7' day, '%Y-%m-%d')
        """

        try:
            result, from_cache = self._execute_query_with_cache(query, "statistics")

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "query_type": "statistics",
                "cache_ttl": self.cache_service.ttl_stats,
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "query_type": "statistics",
            }

    def get_recent_trend(self, minutes: int = 60) -> Dict[str, Any]:
        """Busca tendência recente por minutos com cache otimizado"""
        # Aplicar limites de configuração
        minutes = min(minutes, Config.MAX_TREND_RANGE)
        minutes = max(minutes, 5)

        query = f"""
        SELECT 
            date_trunc('minute', coleta) as minute,
            avg(cast(price_brl as double)) as avg_price,
            count(*) as data_points
        FROM {self.database}.{self.table_name}
        WHERE dt >= date_format(current_date - interval '3' day, '%Y-%m-%d')
        GROUP BY date_trunc('minute', coleta)
        ORDER BY minute DESC
        LIMIT 120
        """

        try:
            result, from_cache = self._execute_query_with_cache(query, "recent_trend")

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "period_minutes": minutes,
                "query_type": "recent_trend",
                "cache_ttl": self.cache_service.ttl_trend,
            }
        except Exception as e:
            logger.error(f"Error getting recent trend: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "period_minutes": minutes,
                "query_type": "recent_trend",
            }

    def get_health_check(self) -> Dict[str, Any]:
        """Health check simples - conta registros da última semana"""
        query = f"""
        SELECT 
            count(*) as records_today,
            max(coleta) as last_update,
            min(coleta) as first_update
        FROM {self.database}.{self.table_name}
        WHERE dt >= date_format(current_date - interval '7' day, '%Y-%m-%d')
        """

        try:
            result, from_cache = self._execute_query_with_cache(query, "health_check")

            return {
                "data": result,
                "from_cache": from_cache,
                "count": len(result),
                "query_type": "health_check",
                "cache_ttl": self.cache_service.ttl_health,
                "status": "healthy"
                if len(result) > 0 and result[0].get("records_today", "0") != "0"
                else "warning",
            }
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {
                "data": [],
                "from_cache": False,
                "count": 0,
                "error": str(e),
                "query_type": "health_check",
                "status": "error",
            }

    def get_service_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do serviço (cache + Athena)"""
        cache_stats = self.cache_service.get_stats()
        aws_config = Config.get_aws_config()

        return {
            "athena_config": {
                "database": self.database,
                "table": self.table_name,
                "workgroup": self.workgroup,
                "output_location": self.s3_output,
                "region": aws_config["region_name"],
            },
            "cache_stats": cache_stats,
            "performance_limits": {
                "max_hourly_range": Config.MAX_HOURLY_RANGE,
                "max_trend_range": Config.MAX_TREND_RANGE,
                "query_timeout": Config.ATHENA_QUERY_TIMEOUT,
            },
            "service_status": "healthy",
        }
