import os
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'universite_gizli_anahtar_cok_guclu_olmali'
    
    # SQLite Veritabanı Yolu (SQLAlchemy formatında)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'demirbas.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Yükleme Klasörü (Gerekirse)
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')