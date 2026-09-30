import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Пожалуйста, войдите в систему."
login_manager.login_message_category = "warning"

csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "500 per hour"],
    storage_uri="memory://",
)


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "barbershop.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["WTF_CSRF_TIME_LIMIT"] = None

    app.config["UPLOAD_FOLDER"] = os.path.join(basedir, "app", "static", "uploads", "salons")
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    from .auth import auth_bp
    from .main import main_bp
    from .moderator import moderator_bp
    from .admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(moderator_bp, url_prefix="/moderator")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # DDoS-гард закомментирован — включайте после отладки
    # from .security import register_ddos_guard
    # register_ddos_guard(app)

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {"now": datetime.utcnow()}

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    with app.app_context():
        db.create_all()

        from .media_sync import sync_salon_photos, sync_all_cover_covers
        try:
            sync_salon_photos(app)
            sync_all_cover_covers(app)
        except Exception as e:
            print(f"[SYNC] ошибка: {e}")

    return app