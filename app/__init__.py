from flask import Flask
from config import Config
from app.extensions import db, migrate

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Eklentileri Başlat
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Türkçe Karakter Desteği (SQLite için özel fonksiyon)
    from app.utils import turkce_normalize
    with app.app_context():
        @db.event.listens_for(db.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            # Eğer SQLite kullanıyorsak özel fonksiyonu ekle
            if app.config['SQLALCHEMY_DATABASE_URI'].startswith("sqlite"):
                dbapi_connection.create_function("NORMALIZE", 1, turkce_normalize)

    # Blueprintleri (Modülleri) Kaydet (Henüz boşlar ama yerlerini hazırlayalım)
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.inventory import bp as inventory_bp
    app.register_blueprint(inventory_bp) # url_prefix eklemedik çünkü form action'ları direkt /ekle-demirbas diye gidiyor
    # Diğerleri sonra eklenecek...
    
    from app.personnel import bp as personnel_bp
    app.register_blueprint(personnel_bp)

    from app.maintenance import bp as maintenance_bp
    app.register_blueprint(maintenance_bp)
    
    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    return app