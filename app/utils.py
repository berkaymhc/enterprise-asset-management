from functools import wraps
from flask import session, redirect, url_for, flash
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, session
from datetime import datetime

def turkce_normalize(metin):
    if metin is None: return ""
    degisim = {
        'İ': 'i', 'I': 'i', 'ı': 'i', 'Ş': 's', 'ş': 's',
        'Ç': 'c', 'ç': 'c', 'Ö': 'o', 'ö': 'o',
        'Ü': 'u', 'ü': 'u', 'Ğ': 'g', 'ğ': 'g'
    }
    yeni_metin = ""
    for harf in metin:
        yeni_metin += degisim.get(harf, harf)
    return yeni_metin.lower()

def format_telefon(tel):
    if not tel: return ""
    temiz = ''.join(filter(str.isdigit, str(tel)))
    if len(temiz) >= 10:
        temiz = temiz[-10:]
        return f"+90 {temiz[:3]} {temiz[3:6]} {temiz[6:8]} {temiz[8:]}"
    return tel
def tr_upper(text):
    """Türkçe karakterlere uygun büyük harfe çevirme"""
    if not text: return ""
    return text.replace('i', 'İ').replace('ı', 'I').upper()

def tr_title(text):
    """Türkçe karakterlere uygun Başlık Formatı"""
    if not text: return ""
    kelimeler = text.split()
    yeni_kelimeler = []
    for kelime in kelimeler:
        if not kelime: continue
        ilk = kelime[0]
        # Geri kalanını küçültürken I -> ı, İ -> i dönüşümü yap
        kalan = kelime[1:].replace('I', 'ı').replace('İ', 'i').lower()
        yeni_kelimeler.append(ilk + kalan)
    return " ".join(yeni_kelimeler)

def get_reset_token(user_id, expires_sec=1800):
    """Şifre sıfırlama için güvenli token oluşturur (30 dk geçerli)"""
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(user_id, salt='sifre-sifirlama-tuzu')

def verify_reset_token(token):
    """Gelen tokenı doğrular ve user_id döndürür"""
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = s.loads(token, salt='sifre-sifirlama-tuzu', max_age=1800)
    except:
        return None
    return user_id

def save_picture(form_picture, folder='profile_pics'):
    """Resim yükleme fonksiyonu (Varsa kalsın)"""
    pass # Mevcut resim yükleme kodun varsa buraya ekleyebilirsin

def log_kaydet(baslik, detay, tur):
    """Sistem genelinde işlem geçmişini kaydeder"""
    from app import db
    from app.models import YuklemeGecmisi
    try:
        log = YuklemeGecmisi(
            dosya_adi=baslik, 
            hedef_konum=detay, 
            tur=tur, 
            tarih=datetime.now().strftime("%d-%m-%Y %H:%M"),
            islem_yapan=session.get('ad_soyad', 'Sistem')
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if current_app:
            current_app.logger.error(f"Log Kaydetme Hatası: {e}")