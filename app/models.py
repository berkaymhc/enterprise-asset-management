from datetime import datetime
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class Kullanici(db.Model):
    __tablename__ = 'kullanicilar'
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(64), unique=True, nullable=False)
    sifre_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(20), default='personel')
    ad_soyad = db.Column(db.String(100))
    birim = db.Column(db.String(100))
    yetki_duzeyi = db.Column(db.Integer, default=0)
    tarih = db.Column(db.String(20))

    def set_password(self, password):
        self.sifre_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.sifre_hash, password)

class Demirbas(db.Model):
    __tablename__ = 'demirbaslar'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(150), nullable=False)
    cinsi = db.Column(db.String(100))
    kampus = db.Column(db.String(100))
    konum = db.Column(db.String(200), nullable=False)
    adet = db.Column(db.Integer, nullable=False, default=1)
    tarih = db.Column(db.String(20), default=datetime.now().strftime("%Y-%m-%d"))

    # İlişki: Bir demirbaşın birden çok arızası olabilir
    arizalar = db.relationship('Ariza', backref='demirbas', lazy=True)

class Personel(db.Model):
    __tablename__ = 'personeller'
    id = db.Column(db.Integer, primary_key=True)
    ad_soyad = db.Column(db.String(100), nullable=False)
    unvan = db.Column(db.String(100))
    birimi = db.Column(db.String(100))
    kampus = db.Column(db.String(100))
    ofis = db.Column(db.String(100), nullable=False)
    telefon = db.Column(db.String(20))
    email = db.Column(db.String(100))
    tarih = db.Column(db.DateTime, default=datetime.now)

class Ariza(db.Model):
    __tablename__ = 'arizalar'
    id = db.Column(db.Integer, primary_key=True)
    konum = db.Column(db.String(200), nullable=False)
    baslik = db.Column(db.String(200), nullable=False)
    aciklama = db.Column(db.Text)
    bildiren = db.Column(db.String(100))
    durum = db.Column(db.String(50), default='Bekliyor')
    oncelik = db.Column(db.String(20), default='Normal')
    tarih = db.Column(db.String(20))
    islem_yapan = db.Column(db.String(100))
    iptal_nedeni = db.Column(db.String(255))
    
    # İlişki (Foreign Key)
    demirbas_id = db.Column(db.Integer, db.ForeignKey('demirbaslar.id'), nullable=True)

class YuklemeGecmisi(db.Model):
    __tablename__ = 'yukleme_gecmisi'
    id = db.Column(db.Integer, primary_key=True)
    dosya_adi = db.Column(db.String(255))
    hedef_konum = db.Column(db.String(255))
    tur = db.Column(db.String(50))
    tarih = db.Column(db.String(20))
    islem_yapan = db.Column(db.String(100))