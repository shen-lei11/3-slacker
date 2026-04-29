import logging

from flask import Flask
from flask_login import LoginManager

from config import Config


login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app() -> Flask:
    Config.validate()

    app = Flask(__name__)
    app.config.from_object(Config)
    logging.getLogger(__name__).info("Supabase: %s", app.config["SUPABASE_URL"])

    login_manager.init_app(app)

    from application import models  # noqa: F401  (registers user_loader)
    from application.auth import auth_bp
    from application.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    return app
