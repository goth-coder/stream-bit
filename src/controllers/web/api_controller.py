from flask import Blueprint, jsonify, request, Response
from datetime import datetime
import json
import time
import logging
from ...models.config import Config

# Import the analytics engine
try:
    from ...services.analytics.athena_engine import AthenaEngine
except ImportError:
    AthenaEngine = None

logger = logging.getLogger(__name__)


def create_api_blueprint(athena_service, cache_service):
    """Cria blueprint da API com dependências injetadas e configuração centralizada"""

    api_bp = Blueprint("api", __name__, url_prefix="/api")
    timing_config = Config.get_timing_config()

    @api_bp.route("/health")
    def health():
        """Health check endpoint com validação de configuração"""
        try:
            health_data = athena_service.get_health_check()
            config_validation = Config.validate_config()

            return jsonify(
                {
                    "status": "healthy" if config_validation["valid"] else "warning",
                    "service": "bitcoin-dashboard-api",
                    "timestamp": datetime.now().isoformat(),
                    "athena_status": health_data.get("status", "unknown"),
                    "config_validation": config_validation,
                    "version": "1.0.0",
                }
            )
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return jsonify(
                {
                    "status": "unhealthy",
                    "service": "bitcoin-dashboard-api",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                }
            ), 500

    @api_bp.route("/bitcoin/test")
    def test_data():
        """Test endpoint com dados mockados para verificar frontend"""
        return jsonify(
            {
                "success": True,
                "data": {
                    "price": 65432.50,
                    "change_24h": 1234.75,
                    "change_24h_percent": 1.92,
                    "market_cap": 1285000000000,
                    "volume_24h": 28500000000,
                    "timestamp": datetime.now().isoformat(),
                },
                "cache_info": {"cached": False, "ttl": 30, "query_type": "mock"},
                "timestamp": datetime.now().isoformat(),
            }
        )

    @api_bp.route("/bitcoin/latest")
    def latest_price():
        """Latest Bitcoin price - usando hourly para pegar último valor"""
        try:
            # Usar a query hourly que sabemos que funciona, mas com 1 hora
            result = athena_service.get_hourly_prices(1)

            # Extrair dados do último registro
            price_data = {}
            if result["data"] and len(result["data"]) > 0:
                row = result["data"][-1]  # Último item
                price_data = {
                    "price_brl": float(
                        row.get("avg_price", 0)
                    ),  # Usar avg_price da hourly
                    "price_usd": float(row.get("avg_price", 0))
                    / 5.5,  # Conversão aproximada
                    "timestamp": row.get("timestamp"),
                    "currency": "BRL",
                    "change_24h": 0,  # Placeholder
                    "change_24h_percent": 0,  # Placeholder
                }

            response_data = {
                "success": True,
                "data": price_data,
                "from_cache": result["from_cache"],
                "count": len(price_data) if price_data else 0,
                "timestamp": datetime.now().isoformat(),
                "query_type": "latest_from_hourly",
                "cache_ttl": result.get("cache_ttl", "unknown"),
            }

            if "error" in result:
                response_data["warning"] = result["error"]

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in latest_price: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/price-change")
    def price_change():
        """Calcula mudança de preço baseada no range especificado"""
        hours = request.args.get("hours", 24, type=int)

        # Aplicar limites de configuração
        hours = min(hours, Config.MAX_HOURLY_RANGE)
        hours = max(hours, 1)

        try:
            # Buscar preço atual (mais recente)
            latest_result = athena_service.get_hourly_prices(1)

            # Buscar primeiro preço do range
            first_result = athena_service.get_first_price_in_range(hours)

            price_change_data = {}

            if (
                latest_result["data"]
                and len(latest_result["data"]) > 0
                and first_result["data"]
                and len(first_result["data"]) > 0
            ):
                # Extrair preços - ajustar para novos campos
                latest_price = float(latest_result["data"][-1].get("avg_price", 0))
                first_price = float(
                    first_result["data"][0].get("avg_price", 0)
                )  # Mudança aqui

                if first_price > 0:  # Evitar divisão por zero
                    # Calcular mudanças
                    change_absolute = latest_price - first_price
                    change_percent = (change_absolute / first_price) * 100

                    price_change_data = {
                        "price_change_percent": round(change_percent, 2),
                        "price_change_absolute": round(change_absolute, 2),
                        "range_hours": hours,
                        "first_price": round(first_price, 2),
                        "latest_price": round(latest_price, 2),
                        "first_timestamp": first_result["data"][0].get("timestamp"),
                        "latest_timestamp": latest_result["data"][-1].get("timestamp"),
                        "is_positive": change_percent >= 0,
                    }
                else:
                    price_change_data = {
                        "error": "Invalid first price for calculation",
                        "range_hours": hours,
                    }
            else:
                price_change_data = {
                    "error": "Insufficient data for price change calculation",
                    "range_hours": hours,
                    "latest_data_count": len(latest_result["data"])
                    if latest_result["data"]
                    else 0,
                    "first_data_count": len(first_result["data"])
                    if first_result["data"]
                    else 0,
                }

            response_data = {
                "success": True,
                "data": price_change_data,
                "from_cache": latest_result.get("from_cache", False)
                or first_result.get("from_cache", False),
                "timestamp": datetime.now().isoformat(),
                "query_type": "price_change",
                "cache_info": {
                    "latest_from_cache": latest_result.get("from_cache", False),
                    "first_from_cache": first_result.get("from_cache", False),
                },
            }

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error calculating price change: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "range_hours": hours,
                }
            ), 500

    @api_bp.route("/bitcoin/hourly")
    def hourly_prices():
        """Hourly Bitcoin prices com validação de limites"""
        hours = request.args.get("hours", 24, type=int)

        # Aplicar limites de configuração
        hours = min(hours, Config.MAX_HOURLY_RANGE)
        hours = max(hours, 1)

        try:
            result = athena_service.get_hourly_prices(hours)

            # Transformar dados para o formato esperado pelo frontend
            chart_data = []
            if result["data"]:
                for row in result["data"]:
                    chart_data.append(
                        {
                            "timestamp": row.get(
                                "timestamp"
                            ),  # Agora usando timestamp da query
                            "hour_period": row.get("hour_period"),  # Período agrupado
                            "price": float(row.get("avg_price", 0)),
                            "avg_price": float(row.get("avg_price", 0)),
                            "min_price": float(row.get("min_price", 0)),
                            "max_price": float(row.get("max_price", 0)),
                            "data_points": int(row.get("data_points", 0)),
                            "volatility": float(row.get("price_volatility", 0))
                            if row.get("price_volatility")
                            else 0,
                        }
                    )

            response_data = {
                "success": True,
                "data": chart_data,
                "from_cache": result["from_cache"],
                "count": result["count"],
                "period_hours": hours,
                "timestamp": datetime.now().isoformat(),
                "query_type": result["query_type"],
                "cache_ttl": result.get("cache_ttl", "unknown"),
            }

            if "error" in result:
                response_data["warning"] = result["error"]

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in hourly_prices: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "period_hours": hours,
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/individual")
    def individual_prices():
        """Individual Bitcoin prices sem agrupamento por hora"""
        hours = request.args.get("hours", 24, type=int)

        # Aplicar limites de configuração
        hours = min(hours, Config.MAX_HOURLY_RANGE)
        hours = max(hours, 1)

        try:
            result = athena_service.get_individual_prices(hours)

            # Transformar dados para o formato esperado pelo frontend
            chart_data = []
            if result["data"]:
                for row in result["data"]:
                    chart_data.append(
                        {
                            "timestamp": row.get("timestamp"),
                            "price": float(row.get("price_brl", 0)),
                            "price_brl": float(row.get("price_brl", 0)),
                            "price_usd": float(row.get("price_usd", 0)),
                        }
                    )

            response_data = {
                "success": True,
                "data": chart_data,
                "from_cache": result["from_cache"],
                "count": result["count"],
                "period_hours": hours,
                "timestamp": datetime.now().isoformat(),
                "query_type": result["query_type"],
                "cache_ttl": result.get("cache_ttl", "unknown"),
            }

            if "error" in result:
                response_data["warning"] = result["error"]

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in individual_prices: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "period_hours": hours,
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/chart-data")
    def chart_data():
        """Chart data com pontos individuais para maior precisão"""
        hours = request.args.get("hours", 24, type=int)
        hours = min(hours, Config.MAX_HOURLY_RANGE)
        hours = max(hours, 1)

        try:
            # Use individual points instead of hourly aggregation
            result = athena_service.get_individual_prices_working(hours)

            chart_data = []
            if result["data"]:
                for row in result["data"]:
                    chart_data.append(
                        {
                            "timestamp": row.get("timestamp"),
                            "price_brl": float(row.get("price_brl", 0)),
                            "currency": row.get("currency", "BRL"),
                        }
                    )

            response_data = {
                "success": True,
                "data": chart_data,
                "from_cache": result["from_cache"],
                "count": result["count"],
                "period_hours": hours,
                "timestamp": datetime.now().isoformat(),
                "query_type": "individual_chart_data",
                "cache_ttl": result.get("cache_ttl", "unknown"),
            }

            if "error" in result:
                response_data["warning"] = result["error"]

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in chart_data: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "period_hours": hours,
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/statistics")
    def bitcoin_statistics():
        """Bitcoin statistics for specific time range"""
        hours = request.args.get("hours", 24, type=int)

        # Aplicar limites de configuração
        hours = min(hours, Config.MAX_HOURLY_RANGE)
        hours = max(hours, 1)

        try:
            # Usar get_hourly_prices para calcular statistics do range específico
            result = athena_service.get_hourly_prices(hours)

            if result.get("data") and len(result["data"]) > 0:
                # Calcular statistics dos dados do range
                prices = [float(row.get("avg_price", 0)) for row in result["data"]]
                data_points = sum(
                    int(row.get("data_points", 0)) for row in result["data"]
                )

                stats_data = {
                    "min_price": min(prices) if prices else 0,
                    "max_price": max(prices) if prices else 0,
                    "avg_price": sum(prices) / len(prices) if prices else 0,
                    "total_records": data_points,
                    "price_volatility": ((max(prices) - min(prices)) / min(prices))
                    * 100
                    if prices and min(prices) > 0
                    else 0,
                    "time_range_hours": hours,
                }

                response_data = {
                    "success": True,
                    "data": stats_data,
                    "from_cache": result["from_cache"],
                    "count": len(result["data"]),
                    "timestamp": datetime.now().isoformat(),
                    "query_type": f"statistics_{hours}h",
                    "cache_ttl": result.get("cache_ttl", "unknown"),
                }

                return jsonify(response_data)
            else:
                return jsonify(
                    {
                        "success": False,
                        "error": "No data available for statistics calculation",
                        "period_hours": hours,
                        "timestamp": datetime.now().isoformat(),
                    }
                ), 404

        except Exception as e:
            logger.error(f"Error in bitcoin_statistics: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "period_hours": hours,
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/stats")
    def bitcoin_stats():
        """Bitcoin statistics com cache longo"""
        try:
            result = athena_service.get_price_statistics()

            response_data = {
                "success": True,
                "data": result["data"],
                "from_cache": result["from_cache"],
                "count": result["count"],
                "timestamp": datetime.now().isoformat(),
                "query_type": result["query_type"],
                "cache_ttl": result.get("cache_ttl", "unknown"),
            }

            if "error" in result:
                response_data["warning"] = result["error"]

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in bitcoin_stats: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/analytics/summary")
    def analytics_summary():
        """Get detailed Bitcoin analytics using athena_engine"""
        try:
            hours = request.args.get("hours", 24, type=int)
            hours = min(hours, 168)  # Max 1 week
            hours = max(hours, 1)

            if AthenaEngine:
                athena_engine = AthenaEngine()

                # Get price summary
                stats_df = athena_engine.get_price_summary(hours=hours)

                if stats_df is not None and not stats_df.empty:
                    stats_dict = {
                        "min_price": float(stats_df["min_price"].iloc[0]),
                        "max_price": float(stats_df["max_price"].iloc[0]),
                        "avg_price": float(stats_df["avg_price"].iloc[0]),
                        "volatility": float(stats_df["volatility"].iloc[0]),
                        "data_points": int(stats_df["data_points"].iloc[0]),
                        "time_range_hours": hours,
                    }

                    return jsonify(
                        {
                            "success": True,
                            "data": stats_dict,
                            "source": "athena_analytics",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            # Fallback to AthenaService
            result = athena_service.get_price_statistics()

            if result["data"] and len(result["data"]) > 0:
                row = result["data"][0]
                fallback_stats = {
                    "min_price": float(row.get("min_price", 0)),
                    "max_price": float(row.get("max_price", 0)),
                    "avg_price": float(row.get("avg_price", 0)),
                    "price_volatility": float(row.get("price_volatility", 0))
                    if row.get("price_volatility")
                    else 0,
                    "total_records": int(row.get("total_records", 0)),
                    "time_range_hours": hours,
                }
            else:
                # Fallback to mock data
                fallback_stats = {
                    "min_price": 64200.00,
                    "max_price": 66800.00,
                    "avg_price": 65432.50,
                    "price_volatility": 3.2,
                    "total_records": hours * 60,
                    "time_range_hours": hours,
                }

            return jsonify(
                {
                    "success": True,
                    "data": fallback_stats,
                    "source": "fallback",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            logger.error(f"Error in analytics_summary: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/analytics/trends")
    def analytics_trends():
        """Get hourly Bitcoin trends for charting using athena_engine"""
        try:
            hours = request.args.get("hours", 24, type=int)
            hours = min(hours, 168)  # Max 1 week
            hours = max(hours, 1)

            if AthenaEngine:
                athena_engine = AthenaEngine()

                # Get hourly trends
                trends_df = athena_engine.get_hourly_trends(hours=hours)

                if trends_df is not None and not trends_df.empty:
                    # Convert to chart format
                    chart_data = {
                        "labels": trends_df["hour"].dt.strftime("%m-%d %H:%M").tolist(),
                        "prices": trends_df["avg_price"].tolist(),
                        "volumes": trends_df["total_volume"].tolist(),
                        "data_points": len(trends_df),
                        "time_range_hours": hours,
                    }

                    return jsonify(
                        {
                            "success": True,
                            "data": chart_data,
                            "source": "athena_analytics",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            # Fallback to generated mock data
            import math
            from datetime import timedelta

            now = datetime.now()
            labels = []
            prices = []
            volumes = []

            for i in range(hours):
                time_point = now - timedelta(hours=hours - 1 - i)
                labels.append(time_point.strftime("%m-%d %H:%M"))

                # Generate realistic price variation
                base_price = 65432.50
                variation = math.sin(i * 0.3) * 800 + (i % 5 - 2) * 300
                prices.append(base_price + variation)

                # Generate volume data
                base_volume = 1200000000
                volume_variation = math.cos(i * 0.2) * 300000000
                volumes.append(base_volume + volume_variation)

            chart_data = {
                "labels": labels,
                "prices": prices,
                "volumes": volumes,
                "data_points": len(labels),
                "time_range_hours": hours,
            }

            return jsonify(
                {
                    "success": True,
                    "data": chart_data,
                    "source": "fallback",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            logger.error(f"Error in analytics_trends: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/trend")
    def recent_trend():
        """Recent Bitcoin trend com limites configurados"""
        minutes = request.args.get("minutes", 60, type=int)

        # Aplicar limites de configuração
        minutes = min(minutes, Config.MAX_TREND_RANGE)
        minutes = max(minutes, 5)

        try:
            result = athena_service.get_recent_trend(minutes)

            response_data = {
                "success": True,
                "data": result["data"],
                "from_cache": result["from_cache"],
                "count": result["count"],
                "period_minutes": minutes,
                "timestamp": datetime.now().isoformat(),
                "query_type": result["query_type"],
                "cache_ttl": result.get("cache_ttl", "unknown"),
            }

            if "error" in result:
                response_data["warning"] = result["error"]

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error in recent_trend: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "period_minutes": minutes,
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/bitcoin/stream")
    def bitcoin_stream():
        """Server-Sent Events com timing configurado"""

        def generate():
            logger.info("SSE stream started")
            sse_interval = timing_config["sse_update"]

            while True:
                try:
                    # Busca dados mais recentes
                    result = athena_service.get_latest_bitcoin_price()

                    # Formata como SSE
                    data = {
                        "price_data": result["data"][0] if result["data"] else None,
                        "from_cache": result["from_cache"],
                        "timestamp": datetime.now().isoformat(),
                        "status": "ok",
                        "cache_ttl": result.get("cache_ttl", "unknown"),
                    }

                    yield f"data: {json.dumps(data)}\n\n"

                    # Aguarda intervalo configurado
                    time.sleep(sse_interval)

                except Exception as e:
                    logger.error(f"SSE error: {e}")
                    error_data = {
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                        "status": "error",
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                    time.sleep(30)  # Aguarda mais em caso de erro

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )

    @api_bp.route("/system/stats")
    def system_stats():
        """Estatísticas completas do sistema"""
        try:
            stats = athena_service.get_service_stats()
            config_validation = Config.validate_config()

            return jsonify(
                {
                    "success": True,
                    "data": stats,
                    "config_status": config_validation,
                    "timing_config": timing_config,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/cache/stats")
    def cache_stats():
        """Estatísticas específicas do cache"""
        try:
            cache_stats = cache_service.get_stats()

            return jsonify(
                {
                    "success": True,
                    "data": cache_stats,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/cache/clear", methods=["POST"])
    def clear_cache():
        """Limpa todo o cache (para debug)"""
        try:
            success = cache_service.clear()

            if success:
                return jsonify(
                    {
                        "success": True,
                        "message": "Cache cleared successfully",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            else:
                return jsonify(
                    {
                        "success": False,
                        "message": "Failed to clear cache",
                        "timestamp": datetime.now().isoformat(),
                    }
                ), 500

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/config/validate")
    def validate_config():
        """Valida configuração atual"""
        try:
            validation = Config.validate_config()
            flask_config = Config.get_flask_config()
            aws_config = Config.get_aws_config()

            # Omitir dados sensíveis
            safe_aws_config = {
                k: v
                for k, v in aws_config.items()
                if k not in ["aws_access_key_id", "aws_secret_access_key"]
            }

            return jsonify(
                {
                    "success": True,
                    "validation": validation,
                    "flask_config": flask_config,
                    "aws_config": safe_aws_config,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Error validating config: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/pipeline/status", methods=["GET"])
    def pipeline_status():
        """Retorna status do pipeline de extração"""
        try:
            # Use cache service to store pipeline status
            pipeline_data = cache_service.get("pipeline_status") or {
                "running": False,
                "last_extraction": None,
            }

            return jsonify(
                {
                    "success": True,
                    "data": pipeline_data,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Error getting pipeline status: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/pipeline/toggle", methods=["POST"])
    def toggle_pipeline():
        """Liga ou desliga o pipeline de extração"""
        try:
            # Get current status from cache
            pipeline_data = cache_service.get("pipeline_status") or {
                "running": False,
                "last_extraction": None,
            }
            current_status = pipeline_data.get("running", False)
            new_status = not current_status

            # Update pipeline status
            new_pipeline_data = {
                "running": new_status,
                "last_extraction": datetime.now().isoformat()
                if new_status
                else pipeline_data.get("last_extraction"),
                "toggled_at": datetime.now().isoformat(),
            }

            # Store in cache with long TTL (1 hour)
            cache_service.set("pipeline_status", new_pipeline_data, ttl=3600)

            # Here you would actually start/stop the extraction process
            # For now, this is a simple toggle

            return jsonify(
                {
                    "success": True,
                    "data": {
                        **new_pipeline_data,
                        "message": f"Pipeline {'started' if new_status else 'stopped'}",
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Error toggling pipeline: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    @api_bp.route("/live-stream")
    def live_stream():
        """Server-Sent Events para atualizações em tempo real do dashboard"""

        def event_stream():
            import time

            retry_count = 0
            max_retries = 1000  # Almost indefinite

            while retry_count < max_retries:
                try:
                    # Sempre enviar dados, independente do pipeline status
                    # O dashboard deve funcionar mesmo sem pipeline ativo

                    # Get latest data using our working API
                    latest_result = athena_service.get_hourly_prices(1)
                    if (
                        latest_result
                        and latest_result.get("data")
                        and len(latest_result["data"]) > 0
                    ):
                        price_data = {
                            "price_brl": float(
                                latest_result["data"][-1].get("avg_price", 0)
                            ),
                            "timestamp": latest_result["data"][-1].get("timestamp"),
                            "from_cache": latest_result.get("from_cache", False),
                        }

                        yield f"data: {
                            json.dumps(
                                {
                                    'type': 'price_update',
                                    'data': price_data,
                                    'timestamp': datetime.now().isoformat(),
                                }
                            )
                        }\n\n"

                    # Get cache stats
                    cache_stats = cache_service.get_stats()
                    yield f"data: {
                        json.dumps(
                            {
                                'type': 'cache_stats',
                                'data': cache_stats,
                                'timestamp': datetime.now().isoformat(),
                            }
                        )
                    }\n\n"

                    # Get statistics update - usando função simples
                    try:
                        # Buscar estatísticas básicas usando hourly data (performance)
                        hourly_result = athena_service.get_hourly_prices(24)

                        if hourly_result.get("data") and len(hourly_result["data"]) > 0:
                            prices = [
                                float(row.get("avg_price", 0))
                                for row in hourly_result["data"]
                            ]
                            data_points = sum(
                                int(row.get("data_points", 0))
                                for row in hourly_result["data"]
                            )

                            stats_data = {
                                "min_price": min(prices),
                                "max_price": max(prices),
                                "avg_price": sum(prices) / len(prices),
                                "total_records": data_points,
                                "price_volatility": (
                                    (max(prices) - min(prices)) / min(prices)
                                )
                                * 100
                                if min(prices) > 0
                                else 0,
                                "time_range_hours": 24,
                            }

                            yield f"data: {
                                json.dumps(
                                    {
                                        'type': 'statistics_update',
                                        'data': stats_data,
                                        'timestamp': datetime.now().isoformat(),
                                    }
                                )
                            }\n\n"
                    except Exception as stats_error:
                        logger.warning(f"SSE statistics error: {stats_error}")

                    retry_count = 0  # Reset on success
                    time.sleep(10)  # Update every 10 seconds

                except Exception as e:
                    retry_count += 1
                    logger.warning(f"SSE error (attempt {retry_count}): {e}")

                    if retry_count >= max_retries:
                        yield f"data: {
                            json.dumps(
                                {
                                    'type': 'stream_ended',
                                    'message': f'Stream ended due to too many errors ({retry_count})',
                                    'timestamp': datetime.now().isoformat(),
                                }
                            )
                        }\n\n"
                        break

                    time.sleep(min(retry_count * 2, 30))  # Exponential backoff

        response = Response(
            event_stream(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )
        return response

    def get_latest_price_internal():
        """Internal version of latest price for SSE"""
        try:
            result, from_cache = athena_service.get_latest_bitcoin_price()
            if result and result.get("success", False) and result.get("data"):
                price_data = (
                    result["data"][0]
                    if isinstance(result["data"], list)
                    else result["data"]
                )

                return {
                    "success": True,
                    "data": {
                        "price": float(price_data.get("price_usd", 0)),
                        "currency": "BRL",
                        "timestamp": price_data.get("timestamp", ""),
                        "change_24h": 0,  # Will be calculated later
                        "change_24h_percent": 0,
                    },
                    "from_cache": from_cache,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"Error in get_latest_price_internal: {e}")
            return {"success": False, "error": str(e)}

    @api_bp.route("/live-data/toggle", methods=["POST"])
    def toggle_live_data():
        """Liga/desliga pipeline + SSE em uma ação"""
        try:
            # Get current status
            pipeline_data = cache_service.get("pipeline_status") or {"running": False}
            current_status = pipeline_data.get("running", False)
            new_status = not current_status

            # Update pipeline status
            new_pipeline_data = {
                "running": new_status,
                "last_extraction": datetime.now().isoformat()
                if new_status
                else pipeline_data.get("last_extraction"),
                "toggled_at": datetime.now().isoformat(),
                "mode": "live_data",
            }

            # Store in cache with long TTL (1 hour)
            cache_service.set("pipeline_status", new_pipeline_data, ttl=3600)

            return jsonify(
                {
                    "success": True,
                    "data": {
                        **new_pipeline_data,
                        "message": f"Live data {'started' if new_status else 'stopped'}",
                        "sse_endpoint": "/api/live-stream" if new_status else None,
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Error toggling live data: {e}")
            return jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    # Error handlers para o blueprint
    @api_bp.errorhandler(404)
    def not_found(error):
        return jsonify(
            {
                "success": False,
                "error": "Endpoint not found",
                "timestamp": datetime.now().isoformat(),
            }
        ), 404

    @api_bp.errorhandler(500)
    def internal_error(error):
        return jsonify(
            {
                "success": False,
                "error": "Internal server error",
                "timestamp": datetime.now().isoformat(),
            }
        ), 500

    return api_bp
