"""
Stream-Bit Web Views Module
Handles web interface blueprint registration and route organization
"""

from flask import Blueprint, render_template
from src.controllers.web.api_controller import create_api_blueprint


def create_web_blueprint():
    """Create and configure the main web blueprint"""
    web_bp = Blueprint(
        "web",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )

    @web_bp.route("/")
    def index():
        """Redirect to dashboard"""
        from src.models.config import Config

        return render_template("dashboard.html", config=Config)

    @web_bp.route("/dashboard")
    def dashboard():
        """Main dashboard page"""
        from src.models.config import Config

        return render_template("dashboard.html", config=Config)

    @web_bp.route("/status")
    def status():
        """System status page"""
        from src.models.config import Config
        from datetime import datetime

        # Create status data
        status_data = {
            "service": "Stream-Bit Dashboard",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "env": Config.FLASK_ENV,
            "config_valid": Config.validate_config()["valid"],
            "services": {
                "cache": True,  # Cache service is always available
                "athena": True,  # Athena service configured
            },
        }

        return render_template("status.html", config=Config, status=status_data)

    @web_bp.route("/config")
    def config_page():
        """Configuration page (development only)"""
        from src.models.config import Config
        from datetime import datetime

        if Config.FLASK_ENV != "development":
            return render_template(
                "error.html",
                error_code=403,
                error_message="Config page only available in development",
            ), 403

        try:
            validation = Config.validate_config()
            flask_config = Config.get_flask_config()
            cache_config = Config.get_cache_config()
            timing_config = Config.get_timing_config()

            return render_template(
                "config.html",
                validation=validation,
                flask_config=flask_config,
                cache_config=cache_config,
                timing_config=timing_config,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                config=Config,
            )
        except Exception as e:
            return render_template(
                "error.html", error_code=500, error_message=f"Config page error: {e}"
            ), 500

    @web_bp.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        return render_template(
            "error.html", error_code=404, error_message="Page not found"
        ), 404

    @web_bp.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        return render_template(
            "error.html", error_code=500, error_message="Internal server error"
        ), 500

    return web_bp


def register_blueprints(app, athena_service, cache_service):
    """Register all web blueprints with the Flask app"""
    # Register main web blueprint
    web_bp = create_web_blueprint()
    app.register_blueprint(web_bp)

    # Register API blueprint
    api_bp = create_api_blueprint(athena_service, cache_service)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
