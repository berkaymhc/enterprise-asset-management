from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime

# ----------------------------------------------------
# 1. KULLANICI MODELİ
# ----------------------------------------------------
class Kullanici(UserMixin, db.Model):
    __tablename__ = 'kullanici'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    sifre = db.Column(db.String(200), nullable=False)
    ad_soyad = db.Column(db.String(100))
    birim = db.Column(db.String(100))
    
    # Rol: 'admin', 'personel', 'teknik'
    rol = db.Column(db.String(20), default='personel') 
    # Yetki Düzeyi: 0 (İzleyici), 1 (Sorumlu), 2 (Denetçi), 3 (Tam Yetki)
    yetki_duzeyi = db.Column(db.Integer, default=0) 
    
    tarih = db.Column(db.String(20))

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return Kullanici.query.get(int(user_id))

# ----------------------------------------------------
# 2. DEMİRBAŞ MODELİ
# ----------------------------------------------------
class Demirbas(db.Model):
    __tablename__ = 'demirbas'
    __table_args__ = (
        db.Index('idx_demirbas_kampus', 'kampus'),
        db.Index('idx_demirbas_konum', 'konum'),
        db.Index('idx_demirbas_ad', 'ad'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    marka = db.Column(db.String(50))
    model = db.Column(db.String(50))
    seri_no = db.Column(db.String(50), unique=True)
    demirbas_no = db.Column(db.String(50), unique=True, nullable=False)
    
    # EKSİK OLAN SÜTUNLAR EKLENDİ
    cinsi = db.Column(db.String(50)) 
    alim_tarihi = db.Column(db.String(20)) # 'YYYY-MM-DD' formatında tutuyoruz
    
    kategori = db.Column(db.String(50))
    konum = db.Column(db.String(100))
    kampus = db.Column(db.String(100))
    birim = db.Column(db.String(100))
    adet = db.Column(db.Integer, default=1)
    durum = db.Column(db.String(20), default='Aktif')
    kayit_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    qr_kod = db.Column(db.String(200))
    fotograf = db.Column(db.String(100))
    
    arizalar = db.relationship('Ariza', backref='demirbas', lazy=True)

# ----------------------------------------------------
# 3. PERSONEL MODELİ
# ----------------------------------------------------
class Personel(db.Model):
    __tablename__ = 'personel'
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

# ----------------------------------------------------
# 4. ARIZA MODELİ
# ----------------------------------------------------
class Ariza(db.Model):
    __tablename__ = 'ariza'
    __table_args__ = (
        db.Index('idx_ariza_demirbas_id', 'demirbas_id'),
        db.Index('idx_ariza_durum', 'durum'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(100), nullable=False)
    aciklama = db.Column(db.Text, nullable=False)
    durum = db.Column(db.String(20), default='Beklemede')
    
    # EKSİK OLAN SÜTUNLAR EKLENDİ
    oncelik = db.Column(db.String(20), default='Normal') 
    konum = db.Column(db.String(100)) 
    
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Kullanıcı değil string olarak bildiren kişi (Opsiyonel, kullanici_id var zaten)
    bildiren = db.Column(db.String(100)) 

    demirbas_id = db.Column(db.Integer, db.ForeignKey('demirbas.id'), nullable=False)
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=False)

# ----------------------------------------------------
# 5. YÜKLEME GEÇMİŞİ
# ----------------------------------------------------
class YuklemeGecmisi(db.Model):
    __tablename__ = 'yukleme_gecmisi'
    id = db.Column(db.Integer, primary_key=True)
    dosya_adi = db.Column(db.String(255))
    tarih = db.Column(db.String(30))
    islem_yapan = db.Column(db.String(100))
    tur = db.Column(db.String(50)) 
    hedef_konum = db.Column(db.String(255))