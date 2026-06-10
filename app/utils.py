from functools import wraps
from flask import session, redirect, url_for, flash
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, session
from datetime import datetime

def normalize_text(text):
    if text is None: return ""
    replacements = {
        'İ': 'i', 'I': 'i', 'ı': 'i', 'Ş': 's', 'ş': 's',
        'Ç': 'c', 'ç': 'c', 'Ö': 'o', 'ö': 'o',
        'Ü': 'u', 'ü': 'u', 'Ğ': 'g', 'ğ': 'g'
    }
    new_text = ""
    for char in text:
        new_text += replacements.get(char, char)
    return new_text.lower()

def format_phone(phone):
    if not phone: return ""
    clean = ''.join(filter(str.isdigit, str(phone)))
    if len(clean) >= 10:
        clean = clean[-10:]
        return f"+90 {clean[:3]} {clean[3:6]} {clean[6:8]} {clean[8:]}"
    return phone

def to_upper(text):
    if not text: return ""
    return text.replace('i', 'İ').replace('ı', 'I').upper()

def to_title(text):
    if not text: return ""
    words = text.split()
    new_words = []
    for word in words:
        if not word: continue
        first = word[0]
        rest = word[1:].replace('I', 'ı').replace('İ', 'i').lower()
        new_words.append(first + rest)
    return " ".join(new_words)

def get_reset_token(user_id, expires_sec=1800):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(user_id, salt='password-reset-salt')

def verify_reset_token(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = s.loads(token, salt='password-reset-salt', max_age=1800)
    except:
        return None
    return user_id

def save_picture(form_picture, folder='profile_pics'):
    pass 

def save_log(title, detail, log_type):
    from app import db
    from app.models import UploadHistory
    try:
        log = UploadHistory(
            file_name=title, 
            target_location=detail, 
            type=log_type, 
            upload_date=datetime.now().strftime("%d-%m-%Y %H:%M"),
            uploaded_by=session.get('full_name', 'System')
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if current_app:
            current_app.logger.error(f"Save Log Error: {e}")