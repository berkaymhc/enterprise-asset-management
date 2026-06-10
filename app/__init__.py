# app/__init__.py

from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

# 1. DEFINE GLOBAL OBJECTS
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 2. BIND EXTENSIONS TO THE APP
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # Login Manager Settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = ""
    login_manager.login_message_category = 'warning'

    # 3. TEXT NORMALIZATION SUPPORT (For SQLite)
    from app.utils import normalize_text
    with app.app_context():
        @db.event.listens_for(db.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if app.config['SQLALCHEMY_DATABASE_URI'].startswith("sqlite"):
                dbapi_connection.create_function("NORMALIZE", 1, normalize_text)

    # 4. REGISTER BLUEPRINTS
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.inventory import bp as inventory_bp
    app.register_blueprint(inventory_bp)
    
    from app.personnel import bp as personnel_bp
    app.register_blueprint(personnel_bp)

    from app.maintenance import bp as maintenance_bp
    app.register_blueprint(maintenance_bp)
    
    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    return app