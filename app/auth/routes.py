# app/auth/routes.py

from flask import render_template, redirect, url_for, flash, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.models import Kullanici, YuklemeGecmisi
from app import db
from datetime import datetime

# --- LOG YARDIMCI FONKSİYONU ---
def log_kaydet(baslik, detay, tur):
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
        print(f"Log hatası: {e}")

# ----------------------------------------------------
# GİRİŞ / ÇIKIŞ İŞLEMLERİ
# ----------------------------------------------------

@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Eğer zaten giriş yapmışsa ana sayfaya yönlendir
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        kadi = request.form.get('kullanici_adi')
        sifre = request.form.get('sifre')
        
        # Kullanıcıyı veritabanında bul
        user = Kullanici.query.filter_by(kullanici_adi=kadi).first()
        
        # Şifre Kontrolü (Hashlenmiş şifre ile girilen şifreyi karşılaştır)
        if user and check_password_hash(user.sifre, sifre):
            # 1. FLASK-LOGIN İLE OTURUM AÇ
            login_user(user)
            
            # 2. SESSION DEĞİŞKENLERİNİ AYARLA (Template'lerde kullanıldığı için)
            session['rol'] = user.rol
            session['ad_soyad'] = user.ad_soyad
            session['birim'] = user.birim
            session['yetki_duzeyi'] = user.yetki_duzeyi if user.yetki_duzeyi is not None else 0
            
            # Yönlendirme Mantığı
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            # Teknik servis ise Arıza sekmesine git
            if user.rol == 'teknik':
                return redirect(url_for('main.index', tab='ariza')) 
            else:
                return redirect(url_for('main.index'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'danger')
            
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()   # Flask-Login çıkışı
    session.clear() # Tüm session verilerini temizle
    flash('Başarıyla çıkış yapıldı.', 'info')
    return redirect(url_for('auth.login'))

# ----------------------------------------------------
# KULLANICI YÖNETİMİ (CRUD)
# ----------------------------------------------------

@bp.route('/ekle-kullanici', methods=['POST'])
@login_required
def ekle_kullanici():
    if session.get('rol') != 'admin': 
        return redirect(url_for('main.index'))
    
    kadi = request.form.get('kullanici_adi')
    sifre = request.form.get('sifre')
    ad_soyad = request.form.get('ad_soyad')
    rol = request.form.get('rol')
    birim = request.form.get('birim')
    
    try: yetki_duzeyi = int(request.form.get('yetki_duzeyi', 0))
    except: yetki_duzeyi = 0

    # Güvenlik: Panelden yönetici oluşturulamaz (Sadece Ana Admin yapabilir)
    if (rol == 'admin' or yetki_duzeyi >= 3) and current_user.kullanici_adi != 'admin':
        flash("Güvenlik Uyarısı: Sadece Ana Yönetici yeni admin oluşturabilir!", "danger")
        return redirect(url_for('main.index', open_modal='userModal'))
        
    mevcut = Kullanici.query.filter_by(kullanici_adi=kadi).first()
    if mevcut:
        flash("Bu kullanıcı adı zaten kullanılıyor.", "warning")
    else:
        # Yeni kullanıcı oluştur
        yeni_k = Kullanici(
            kullanici_adi=kadi,
            ad_soyad=ad_soyad,
            rol=rol,
            birim=birim,
            yetki_duzeyi=yetki_duzeyi,
            sifre=generate_password_hash(sifre), # ŞİFREYİ HASHLE
            tarih=datetime.now().strftime("%d-%m-%Y %H:%M")
        )
        
        db.session.add(yeni_k)
        db.session.commit()
        log_kaydet("Kullanıcı Eklendi", f"{kadi} ({birim})", "Ekleme")
        flash(f"{kadi} başarıyla eklendi.", "success")
        
    return redirect(url_for('main.index', open_modal='userModal'))

@bp.route('/sil-kullanici/<int:id>')
@login_required
def sil_kullanici(id):
    if session.get('rol') != 'admin': return redirect(url_for('main.index'))
    
    user = Kullanici.query.get(id)
    if user:
        # Admin kendisini veya 'admin' kullanıcısını silemez
        if user.kullanici_adi == 'admin':
            flash("Ana yönetici silinemez!", "danger")
        else:
            kadi = user.kullanici_adi
            db.session.delete(user)
            db.session.commit()
            log_kaydet("Kullanıcı Silindi", f"{kadi}", "Silme")
            flash("Kullanıcı silindi.", "success")
            
    return redirect(url_for('main.index', open_modal='userModal'))

# app/auth/routes.py içerisine ekle

@bp.route('/guncelle-kullanici', methods=['POST'])
@login_required
def guncelle_kullanici():
    if session.get('rol') != 'admin':
        return redirect(url_for('main.index'))

    # Formdan verileri al
    user_id = request.form.get('kullanici_id')
    user = Kullanici.query.get(user_id)
    
    if user:
        # Bilgileri güncelle
        user.kullanici_adi = request.form.get('kullanici_adi')
        user.ad_soyad = request.form.get('ad_soyad')
        user.rol = request.form.get('rol')
        user.birim = request.form.get('birim')
        try:
            user.yetki_duzeyi = int(request.form.get('yetki_duzeyi', 0))
        except:
            user.yetki_duzeyi = 0
            
        # Şifre alanı doluysa şifreyi de güncelle
        sifre = request.form.get('sifre')
        if sifre and sifre.strip() != "":
            user.sifre = generate_password_hash(sifre)
            
        db.session.commit()
        log_kaydet("Kullanıcı Güncellendi", f"{user.kullanici_adi}", "Güncelleme")
        flash("Kullanıcı bilgileri güncellendi.", "success")
    else:
        flash("Kullanıcı bulunamadı.", "danger")
        
    return redirect(url_for('main.index', open_modal='userModal'))