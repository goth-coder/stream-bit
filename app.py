"""
Stream-Bit: Bitcoin Streaming Dashboard Application

Aplicação unificada que combina:
- Pipeline de streaming Bitcoin (extrator + Firehose + S3 + Athena)
- Dashboard web Flask com cache inteligente
- API REST para consultas otimizadas
- Interface near-real-time com polling/SSE

Arquitetura MVC unificada:
- Models: configuração centralizada
- Controllers: API endpoints + streaming pipeline
- Views: templates + static files
- Services: cache, athena, extractors, loaders
"""

# Configurar encoding UTF-8 para suporte a emojis no Windows
import sys
import os
import locale

# Forçar UTF-8 encoding
if sys.platform.startswith("win"):
    # Windows: configurar console para UTF-8
    try:
        # Configurar codepage do console para UTF-8
        os.system("chcp 65001 > nul 2>&1")

        # Configurar locale para UTF-8 se possível
        try:
            locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, "C.UTF-8")
            except locale.Error:
                pass  # Usar locale padrão

        # Configurar variável de ambiente para UTF-8
        os.environ["PYTHONIOENCODING"] = "utf-8"

    except Exception as e:
        print(f"Warning: Could not configure UTF-8 encoding: {e}")

import logging
from flask import Flask

# Adicionar src ao path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Imports da aplicação
from src.models.config import Config
from src.services.web.cache_service import CacheService
from src.services.web.athena_service import AthenaService


# Configurar logging
def setup_logging():
    """Configura logging centralizado com suporte a UTF-8"""

    # Handlers com encoding UTF-8 explícito
    handlers = []

    # File handler com UTF-8
    try:
        file_handler = logging.FileHandler(Config.LOG_FILE, encoding="utf-8")
        handlers.append(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler with UTF-8: {e}")
        # Fallback sem encoding específico
        handlers.append(logging.FileHandler(Config.LOG_FILE))

    # Stream handler com UTF-8 se possível
    try:
        if sys.platform.startswith("win"):
            # Windows: usar stdout com encoding UTF-8
            import io

            stream_handler = logging.StreamHandler(
                io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            )
        else:
            # Linux/Mac: usar stdout padrão
            stream_handler = logging.StreamHandler(sys.stdout)
        handlers.append(stream_handler)
    except Exception as e:
        print(f"Warning: Could not create UTF-8 stream handler: {e}")
        # Fallback para stream handler padrão
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format=Config.LOG_FORMAT,
        handlers=handlers,
        force=True,  # Força reconfiguração se já existir
    )
    return logging.getLogger(__name__)


def create_app():
    """Factory para criar a aplicação Flask"""
    logger = setup_logging()

    # Validar configuração
    config_validation = Config.validate_config()
    if not config_validation["valid"]:
        logger.error(f"Invalid configuration: {config_validation['errors']}")
        for error in config_validation["errors"]:
            logger.error(f"  - {error}")

    if config_validation["warnings"]:
        for warning in config_validation["warnings"]:
            logger.warning(f"  - {warning}")

    # Criar aplicação Flask
    app = Flask(
        __name__,
        static_folder="src/views/web/static",
        template_folder="src/views/web/templates",
    )

    # Configurar Flask
    flask_config = Config.get_flask_config()
    app.config.update(flask_config)

    logger.info(
        f"Flask app created - ENV: {flask_config['ENV']}, DEBUG: {flask_config['DEBUG']}"
    )

    # Inicializar serviços
    try:
        cache_service = CacheService()
        athena_service = AthenaService(cache_service)
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        if Config.FLASK_ENV == "development":
            # Em desenvolvimento, continuar mesmo com erro nos serviços
            cache_service = None
            athena_service = None
        else:
            raise

    # Registrar blueprints
    if cache_service and athena_service:
        from src.views.web import register_blueprints

        register_blueprints(app, athena_service, cache_service)
        logger.info("Web blueprints registered successfully")
    else:
        logger.warning("Services not available, only basic routes registered")

    return app


def run_streaming_pipeline():
    """Executa o pipeline de streaming em modo standalone"""
    logger = setup_logging()
    logger.info("Starting streaming pipeline...")

    try:
        # Import dinâmico para evitar dependencies circulares
        from src.controllers.streaming_controller import StreamingController

        # Configurar timing
        timing_config = Config.get_timing_config()
        aws_config = Config.get_aws_config()

        controller = StreamingController(
            extraction_interval=timing_config["streaming_interval"],
            firehose_stream_name=aws_config["firehose_stream"],
        )

        logger.info(
            f"Streaming controller initialized with {timing_config['streaming_interval']}s interval"
        )

        # Executar pipeline continuamente
        controller.run_continuous_streaming()

    except KeyboardInterrupt:
        logger.info("Streaming pipeline stopped by user")
    except Exception as e:
        logger.error(f"Streaming pipeline error: {e}")
        raise


def run_combined_mode():
    """Executa web dashboard e streaming pipeline concomitantemente"""
    import threading
    import time

    logger = setup_logging()
    logger.info("Starting combined mode: Web Dashboard + Streaming Pipeline")

    # Flag para controlar threads
    stop_threads = threading.Event()

    def streaming_worker():
        """Worker thread para o streaming pipeline"""
        try:
            logger.info("🔄 Starting streaming pipeline in background...")

            from src.controllers.streaming_controller import StreamingController

            timing_config = Config.get_timing_config()
            aws_config = Config.get_aws_config()

            controller = StreamingController(
                extraction_interval=timing_config["streaming_interval"],
                firehose_stream_name=aws_config["firehose_stream"],
            )

            # Executar enquanto não for sinalizado para parar
            while not stop_threads.is_set():
                try:
                    success = controller.run_single_cycle()  # Executa uma iteração
                    if success:
                        logger.info("✅ Streaming cycle completed successfully")
                    time.sleep(timing_config["streaming_interval"])
                except Exception as e:
                    logger.error(f"Streaming iteration error: {e}")
                    time.sleep(30)  # Aguarda mais tempo em caso de erro

        except Exception as e:
            logger.error(f"Streaming worker error: {e}")

    def web_worker():
        """Worker thread para a web application"""
        try:
            logger.info("🌐 Starting web dashboard...")

            app = create_app()
            host = Config.FLASK_HOST
            port = Config.FLASK_PORT

            print("\n🚀 Stream-Bit Dashboard + Pipeline starting...")
            print(f"📊 Dashboard: http://{host}:{port}/")
            print(f"⚙️  Config: http://{host}:{port}/config")
            print(f"📈 API: http://{host}:{port}/api/health")
            print("🔄 Pipeline: Running in background")
            print(f"💾 Environment: {Config.FLASK_ENV}")
            print("🔧 Press Ctrl+C to stop\n")

            app.run(host=host, port=port, debug=False, use_reloader=False)

        except Exception as e:
            logger.error(f"Web worker error: {e}")
        finally:
            stop_threads.set()  # Sinalizar para parar outras threads

    try:
        # Iniciar thread do streaming
        streaming_thread = threading.Thread(target=streaming_worker, daemon=True)
        streaming_thread.start()

        # Aguardar um pouco para o streaming inicializar
        time.sleep(2)

        # Executar web app na thread principal
        web_worker()

    except KeyboardInterrupt:
        logger.info("Combined mode stopped by user")
        stop_threads.set()
    except Exception as e:
        logger.error(f"Combined mode error: {e}")
        stop_threads.set()
        raise


def main():
    """Ponto de entrada principal da aplicação"""
    import argparse

    parser = argparse.ArgumentParser(description="Stream-Bit Bitcoin Dashboard")
    parser.add_argument(
        "--mode",
        choices=["web", "stream", "combined", "test"],
        default="combined",
        help="Modo de execução: web (só dashboard), stream (só pipeline), combined (ambos), test (validação)",
    )
    parser.add_argument("--host", default=None, help="Host Flask")
    parser.add_argument("--port", type=int, default=None, help="Porta Flask")

    args = parser.parse_args()

    if args.mode == "stream":
        # Modo pipeline apenas
        run_streaming_pipeline()
    elif args.mode == "combined":
        # Modo combinado: web + streaming
        run_combined_mode()
    elif args.mode == "test":
        # Modo teste
        logger = setup_logging()
        logger.info("Running configuration test...")
        validation = Config.validate_config()
        print(f"Configuration valid: {validation['valid']}")
        if validation["errors"]:
            print("Errors:", validation["errors"])
        if validation["warnings"]:
            print("Warnings:", validation["warnings"])
    else:
        # Modo web apenas (padrão legado)
        app = create_app()

        # Usar argumentos da linha de comando se fornecidos
        host = args.host or Config.FLASK_HOST
        port = args.port or Config.FLASK_PORT

        print("\n🚀 Stream-Bit Dashboard starting...")
        print(f"📊 Dashboard: http://{host}:{port}/")
        print(f"⚙️  Config: http://{host}:{port}/config")
        print(f"📈 API: http://{host}:{port}/api/health")
        print(f"💾 Environment: {Config.FLASK_ENV}")
        print("🔧 Press Ctrl+C to stop\n")

        app.run(host=host, port=port, debug=Config.FLASK_DEBUG)


if __name__ == "__main__":
    main()
