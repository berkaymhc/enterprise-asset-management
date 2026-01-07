# app/auth/routes.py - FİNAL DÜZELTİLMİŞ SÜRÜM

from flask import render_template, redirect, url_for, flash, request, session, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from flask_mail import Message # <-- EKLE
from app import mail # <-- EKLE
from app.utils import get_reset_token, verify_reset_token # <-- EKLE
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
        if session.get('rol') == 'teknik':
            return redirect(url_for('main.index', tab='ariza'))
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        kadi = request.form.get('kullanici_adi')
        sifre = request.form.get('sifre')
        
        # HTML'den gelen checkbox değeri
        beni_hatirla = True if request.form.get('beni_hatirla') else False
        
        user = Kullanici.query.filter_by(kullanici_adi=kadi).first()
        
        if user and check_password_hash(user.sifre, sifre):
            # 1. FLASK-LOGIN İLE OTURUM AÇ
            login_user(user, remember=beni_hatirla)
            
            # 2. SESSION DEĞİŞKENLERİNİ AYARLA
            session['rol'] = user.rol
            session['ad_soyad'] = user.ad_soyad
            session['birim'] = user.birim
            session['yetki_duzeyi'] = user.yetki_duzeyi if user.yetki_duzeyi is not None else 0
            
            # Yönlendirme Hedefi Belirle
            next_page = request.args.get('next')
            if not next_page:
                if user.rol == 'teknik':
                    next_page = url_for('main.index', tab='ariza')
                else:
                    next_page = url_for('main.index')
            
            # --- DÜZELTİLEN KISIM BAŞLANGIÇ ---
            
            # Önce response nesnesini oluşturuyoruz (Eksik olan satır buydu!)
            response = make_response(redirect(next_page))
            
            # Sonra içine çerez (cookie) ekleyip çıkarıyoruz
            if beni_hatirla:
                response.set_cookie('last_username', kadi, max_age=30*24*60*60)
            else:
                response.delete_cookie('last_username')
            
            # En son oluşturduğumuz bu response'u döndürüyoruz
            return response
            
            # --- DÜZELTİLEN KISIM BİTİŞ ---
            
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'danger')
            
    # GET İsteği (Sayfa Yüklenirken)
    last_username = request.cookies.get('last_username', '')
    
    return render_template('auth/login.html', last_username=last_username)

@bp.route('/logout')
@login_required
def logout():
    # 1. Flask-Login Çıkışı (Cookie'yi sil emri verir)
    logout_user()
    
    # 2. Sadece bizim eklediğimiz session verilerini sil (session.clear() yapma!)
    for key in ['rol', 'ad_soyad', 'birim', 'yetki_duzeyi']:
        session.pop(key, None)
        
    flash('Başarıyla çıkış yapıldı.', 'info')
    
    # Giriş sayfasına yönlendir
    return redirect(url_for('auth.login'))

# app/auth/routes.py içindeki importlara eklemediysen ekle:
from flask_mail import Message

@bp.route('/sifre-talep', methods=['POST'])
def sifre_talep():
    girilen = request.form.get('iletisim_bilgisi')
    
    # Otomatik @avrasya.edu.tr tamamlama
    if '@' not in girilen:
        eposta = girilen + '@avrasya.edu.tr'
    else:
        eposta = girilen
        
    user = Kullanici.query.filter_by(email=eposta).first()
    
    if user:
        token = get_reset_token(user.id)
        # Link oluşturuluyor
        link = url_for('auth.sifre_sifirla', token=token, _external=True)
        
        msg = Message('🔒 Şifre Sıfırlama Talebi', recipients=[user.email])
        
        # 1. YEDEK METİN (Eski cihazlar için)
        msg.body = f"Merhaba {user.ad_soyad}, şifrenizi sıfırlamak için şu linke gidin: {link}"
        
        # 2. HTML TASARIM (Asıl görünecek şık kısım)
        msg.html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    
                    <h2 style="color: #092442; text-align: center;">Şifre Sıfırlama</h2>
                    
                    <p>Merhaba <strong>{user.ad_soyad}</strong>,</p>
                    
                    <p>Hesabınız için şifre sıfırlama talebinde bulundunuz. Aşağıdaki butona tıklayarak yeni şifrenizi belirleyebilirsiniz:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{link}" style="background-color: #0d6efd; color: white; padding: 14px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; display: inline-block;">
                            Şifremi Sıfırla
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 13px;">
                        Bu buton 30 dakika süreyle geçerlidir.<br>
                        Eğer butonu göremiyorsanız veya çalışmıyorsa, aşağıdaki bağlantıyı tarayıcınıza yapıştırın:
                    </p>
                    <p style="word-break: break-all; color: #999; font-size: 11px;">{link}</p>
                    
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="text-align: center; color: #aaa; font-size: 11px;">
                        Avrasya Üniversitesi - Envanter Takip Sistemi
                    </p>
                </div>
            </body>
        </html>
        """
        
        try:
            mail.send(msg)
            flash(f"Sıfırlama bağlantısı {user.email} adresine gönderildi.", "info")
        except Exception as e:
            flash(f"Mail gönderilemedi. Hata: {str(e)}", "danger")
            print(f"MAIL HATASI: {e}")
            
    else:
        flash("Bu kullanıcı adıyla kayıtlı bir e-posta bulunamadı.", "warning")
        
    return redirect(url_for('auth.login'))

# --- YENİ ROTA: LİNKE TIKLAYINCA AÇILACAK SAYFA ---
@bp.route('/sifre-sifirla/<token>', methods=['GET', 'POST'])
def sifre_sifirla(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user_id = verify_reset_token(token)
    if user_id is None:
        flash('Sıfırlama bağlantısı geçersiz veya süresi dolmuş.', 'warning')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        sifre = request.form.get('sifre')
        sifre_tekrar = request.form.get('sifre_tekrar')
        
        if sifre != sifre_tekrar:
            flash('Şifreler eşleşmiyor!', 'danger')
            return render_template('auth/reset_password.html', token=token)
            
        user = Kullanici.query.get(user_id)
        user.sifre = generate_password_hash(sifre)
        db.session.commit()
        
        flash('Şifreniz başarıyla güncellendi! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', token=token)

# app/auth/routes.py içindeki ilgili fonksiyonlar

@bp.route('/ekle-kullanici', methods=['POST'])
@login_required
def ekle_kullanici():
    if session.get('rol') != 'admin': 
        return redirect(url_for('main.index'))
    
    kadi = request.form.get('kullanici_adi')
    email = request.form.get('email')  # <-- YENİ: Email alıyoruz
    sifre = request.form.get('sifre')
    ad_soyad = request.form.get('ad_soyad')
    rol = request.form.get('rol')
    birim = request.form.get('birim')
    
    try: yetki_duzeyi = int(request.form.get('yetki_duzeyi', 0))
    except: yetki_duzeyi = 0

    # ... (Güvenlik kontrolleri aynı kalsın) ...

    mevcut = Kullanici.query.filter((Kullanici.kullanici_adi == kadi) | (Kullanici.email == email)).first()
    if mevcut:
        flash("Bu kullanıcı adı veya e-posta zaten kullanılıyor.", "warning")
    else:
        yeni_k = Kullanici(
            kullanici_adi=kadi,
            email=email,  # <-- YENİ: Email'i kaydediyoruz
            ad_soyad=ad_soyad,
            rol=rol,
            birim=birim,
            yetki_duzeyi=yetki_duzeyi,
            sifre=generate_password_hash(sifre),
            tarih=datetime.now().strftime("%d-%m-%Y %H:%M")
        )
        db.session.add(yeni_k)
        db.session.commit()
        log_kaydet("Kullanıcı Eklendi", f"{kadi}", "Ekleme")
        flash(f"{kadi} başarıyla eklendi.", "success")
        
    return redirect(url_for('main.index', open_modal='userModal'))

@bp.route('/guncelle-kullanici', methods=['POST'])
@login_required
def guncelle_kullanici():
    if session.get('rol') != 'admin':
        return redirect(url_for('main.index'))

    user_id = request.form.get('kullanici_id')
    user = Kullanici.query.get(user_id)
    
    if user:
        # ... (Admin kontrolü aynı kalsın) ...

        user.kullanici_adi = request.form.get('kullanici_adi')
        user.email = request.form.get('email') # <-- YENİ: Email güncelliyoruz
        user.ad_soyad = request.form.get('ad_soyad')
        user.rol = request.form.get('rol')
        user.birim = request.form.get('birim')
        try: user.yetki_duzeyi = int(request.form.get('yetki_duzeyi', 0))
        except: user.yetki_duzeyi = 0
            
        sifre = request.form.get('sifre')
        if sifre and sifre.strip() != "":
            user.sifre = generate_password_hash(sifre)
            
        db.session.commit()
        log_kaydet("Kullanıcı Güncellendi", f"{user.kullanici_adi}", "Güncelleme")
        flash("Kullanıcı bilgileri güncellendi.", "success")
    else:
        flash("Kullanıcı bulunamadı.", "danger")
        
    return redirect(url_for('main.index', open_modal='userModal'))

@bp.route('/sil-kullanici/<int:id>')
@login_required
def sil_kullanici(id):
    if session.get('rol') != 'admin': return redirect(url_for('main.index'))
    
    user = Kullanici.query.get(id)
    if user:
        if user.kullanici_adi == 'admin':
            flash("Ana yönetici silinemez!", "danger")
        else:
            kadi = user.kullanici_adi
            db.session.delete(user)
            db.session.commit()
            log_kaydet("Kullanıcı Silindi", f"{kadi}", "Silme")
            flash("Kullanıcı silindi.", "success")
            
    return redirect(url_for('main.index', open_modal='userModal'))