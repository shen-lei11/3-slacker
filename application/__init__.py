import logging

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app() -> Flask:
    Config.validate()

    app = Flask(__name__)
    app.config.from_object(Config)
    logging.getLogger(__name__).info("DB: %s", app.config["SQLALCHEMY_DATABASE_URI"])

    db.init_app(app)
    login_manager.init_app(app)

    from application.auth import auth_bp
    from application.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    with app.app_context():
        from application import models

        db.create_all()

    return app
