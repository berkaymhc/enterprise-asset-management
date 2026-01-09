# app/models.py

from app import db, login_manager  # <--- login_manager EKLENDİ
from flask_login import UserMixin  # <--- UserMixin EKLENDİ
from datetime import datetime

# ----------------------------------------------------
# 1. KULLANICI MODELİ (UserMixin Eklendi)
# ----------------------------------------------------
class Kullanici(UserMixin, db.Model):  # <--- BURAYA DİKKAT: UserMixin eklendi
    __tablename__ = 'kullanici'
    
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(50), unique=True, nullable=False)
    sifre = db.Column(db.String(100), nullable=False)
    ad_soyad = db.Column(db.String(100))
    birim = db.Column(db.String(100))
    rol = db.Column(db.String(20), default='personel') 
    yetki_duzeyi = db.Column(db.Integer, default=0) 
    tarih = db.Column(db.String(20))

    # Flask-Login'in kullanıcı ID'sini alması için gerekli
    def get_id(self):
        return str(self.id)

# ----------------------------------------------------
# 2. FLASK-LOGIN İÇİN YÜKLEME FONKSİYONU (BU EKSİKTİ!)
# ----------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return Kullanici.query.get(int(user_id))


# ----------------------------------------------------
# 3. DİĞER MODELLER (AYNEN KALIYOR)
# ----------------------------------------------------
class Demirbas(db.Model):
    __tablename__ = 'demirbas'
    __table_args__ = (
        db.Index('idx_demirbas_kampus', 'kampus'),
        db.Index('idx_demirbas_ad', 'ad'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    marka = db.Column(db.String(50))
    model = db.Column(db.String(50))
    seri_no = db.Column(db.String(50), unique=True)
    demirbas_no = db.Column(db.String(50), unique=True, nullable=False)
    kategori = db.Column(db.String(50))
    konum = db.Column(db.String(100))
    kampus = db.Column(db.String(100))
    birim = db.Column(db.String(100))
    adet = db.Column(db.Integer, default=1)
    durum = db.Column(db.String(20), default='Aktif')
    kayit_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    qr_kod = db.Column(db.String(200))
    fotograf = db.Column(db.String(100))
    
    # İlişkiler
    arizalar = db.relationship('Ariza', backref='demirbas', lazy=True)

    # --- PERFORMANS GÜNCELLEMESİ (İndeksler) ---
    __table_args__ = (
        db.Index('idx_demirbas_kampus', 'kampus'),
        db.Index('idx_demirbas_konum', 'konum'),
        db.Index('idx_demirbas_ad', 'ad'),
    )

class Personel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ad_soyad = db.Column(db.String(100))
    unvan = db.Column(db.String(100))
    birimi = db.Column(db.String(100))
    sicil_no = db.Column(db.String(50))
    ofis = db.Column(db.String(50))
    email = db.Column(db.String(100))
    telefon = db.Column(db.String(20))
    baslama_tarihi = db.Column(db.String(20))
    kampus = db.Column(db.String(100))

class Ariza(db.Model):
    __tablename__ = 'ariza'
    __table_args__ = (
        db.Index('idx_ariza_demirbas_id', 'demirbas_id'),
        db.Index('idx_ariza_durum', 'durum'),
    )

    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(100), nullable=False)
    aciklama = db.Column(db.Text, nullable=False)
    durum = db.Column(db.String(20), default='Beklemede')
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    
    # İlişkiler
    demirbas_id = db.Column(db.Integer, db.ForeignKey('demirbas.id'), nullable=False)
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=False)
    
    # --- PERFORMANS GÜNCELLEMESİ (İndeksler) ---
    __table_args__ = (
        db.Index('idx_ariza_demirbas_id', 'demirbas_id'),
        db.Index('idx_ariza_durum', 'durum'),
    )

class YuklemeGecmisi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dosya_adi = db.Column(db.String(255))
    tarih = db.Column(db.String(30))
    islem_yapan = db.Column(db.String(100))
    tur = db.Column(db.String(50)) 
    hedef_konum = db.Column(db.String(255))
    
class Kullanici(UserMixin, db.Model):
    # --- BU İKİ SATIRI EKLE (HATA ÇÖZÜCÜ) ---
    __tablename__ = 'kullanici'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(80), unique=True, nullable=False)
    # YENİ EKLENEN SATIR:
    email = db.Column(db.String(120), unique=True, nullable=True) 
    
    sifre = db.Column(db.String(200), nullable=False)
    ad_soyad = db.Column(db.String(100))
    rol = db.Column(db.String(20), default='personel')
    birim = db.Column(db.String(100))
    yetki_duzeyi = db.Column(db.Integer, default=0)
    tarih = db.Column(db.String(20))