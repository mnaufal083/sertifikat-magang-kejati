from flask import Flask

from config import Config
from app.extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app.routes_admin import admin_bp
    from app.routes_public import public_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)

    with app.app_context():
        db.create_all()

    return app
