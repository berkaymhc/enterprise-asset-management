import os
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'guclu-gizli-anahtar-123'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'demirbas.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- NATRO HOSTING MAIL AYARLARI ---
    # Genellikle 'mail.alanadi.com' olur. Kendi domainini yaz.
    MAIL_SERVER = 'smtp.office365.com'  # <-- BURAYI DEĞİŞTİRDİK    MAIL_PORT = 587
    MAIL_USE_TLS = True  # Natro genelde TLS yerine direkt bağlantı veya SSL ister
    MAIL_USE_SSL = False  # Hata alırsan burayı True, Portu 465 yapmayı dene
    
    # Oluşturduğun noreply hesabı
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = ('Envanter Sistemi', MAIL_USERNAME)