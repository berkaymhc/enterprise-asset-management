from functools import wraps
from flask import session, redirect, url_for, flash
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

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

def get_reset_token(user_id, expires_sec=1800): # 30 Dakika geçerli
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(user_id, salt='sifre-sifirlama-tuzu')

def verify_reset_token(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = s.loads(token, salt='sifre-sifirlama-tuzu', max_age=1800)
    except:
        return None
    return user_id