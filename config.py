import os
import secrets  # EKLENDİ
import sys      # EKLENDİ
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        # 32 byte (64 karakter) güvenli rastgele hex oluştur
        SECRET_KEY = secrets.token_hex(32)
        # Geliştiriciyi uyar (Standart hata çıktısına yaz)
        print(
            "UYARI: SECRET_KEY çevresel değişkeni ayarlanmamış. "
            "Oturum güvenliği için rastgele bir anahtar oluşturuldu. "
            "Her yeniden başlatmada oturumlar sonlanabilir.", 
            file=sys.stderr
        )
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'demirbas.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- NATRO HOSTING MAIL AYARLARI ---
    # Genellikle 'mail.alanadi.com' olur. Kendi domainini yaz.
    MAIL_SERVER = 'smtp.office365.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True   # TLS Açık
    MAIL_USE_SSL = False  # SSL Kapalı
    
    # Oluşturduğun noreply hesabı
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = ('Envanter Sistemi', MAIL_USERNAME)