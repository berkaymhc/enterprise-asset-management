from flask import render_template, redirect, url_for, flash, request, session
from werkzeug.security import check_password_hash
from app.auth import bp
from app.models import Kullanici, YuklemeGecmisi # Veritabanı modelimizi çağırdık
from app import db
from datetime import datetime
from app.utils import login_required # Bunu kullanacağız

@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Eğer zaten giriş yapmışsa ana sayfaya at
    if session.get('logged_in'):
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        kadi = request.form.get('kullanici_adi')
        sifre = request.form.get('sifre')
        
        # --- ESKİ YÖNTEM (SQL) ---
        # cur.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (kadi,))
        
        # --- YENİ YÖNTEM (ORM) ---
        user = Kullanici.query.filter_by(kullanici_adi=kadi).first()
        
        if user and check_password_hash(user.sifre_hash, sifre):
            session['logged_in'] = True
            session['kullanici_adi'] = user.kullanici_adi
            session['rol'] = user.rol
            session['ad_soyad'] = user.ad_soyad
            session['birim'] = user.birim
            session['yetki_duzeyi'] = user.yetki_duzeyi if user.yetki_duzeyi is not None else 0
            
            # Yönlendirme Mantığı
            if session['rol'] == 'teknik' or session['yetki_duzeyi'] == 0:
                # 'main.index' diyerek diğer modüle yönlendiriyoruz
                return redirect(url_for('main.index', tab='ariza')) 
            else:
                return redirect(url_for('main.index'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'danger')
            
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

# --- LOG FONKSİYONU (Auth için) ---
def log_kaydet(baslik, detay, tur):
    try:
        log = YuklemeGecmisi(
            dosya_adi=baslik, hedef_konum=detay, tur=tur, 
            tarih=datetime.now().strftime("%d-%m-%Y %H:%M"),
            islem_yapan=session.get('ad_soyad', 'Sistem')
        )
        db.session.add(log)
        db.session.commit()
    except: pass


# --- KULLANICI YÖNETİMİ (CRUD) ---

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

    # Güvenlik Duvarı: Arayüzden Admin oluşturulamaz
    if rol == 'admin' or yetki_duzeyi >= 3:
        flash("Güvenlik Uyarısı: Panelden yönetici oluşturulamaz!", "danger")
        return redirect(url_for('main.index', open_modal='userModal'))
        
    mevcut = Kullanici.query.filter_by(kullanici_adi=kadi).first()
    if mevcut:
        flash("Bu kullanıcı adı zaten kullanılıyor.", "warning")
    else:
        yeni_k = Kullanici(
            kullanici_adi=kadi,
            ad_soyad=ad_soyad,
            rol=rol,
            birim=birim,
            yetki_duzeyi=yetki_duzeyi,
            tarih=datetime.now().strftime("%d-%m-%Y %H:%M")
        )
        yeni_k.set_password(sifre) # Modeli kullanarak şifrele
        
        db.session.add(yeni_k)
        db.session.commit()
        log_kaydet("Kullanıcı Eklendi", f"{kadi} ({birim})", "Ekleme")
        flash(f"{kadi} başarıyla eklendi.", "success")
        
    return redirect(url_for('main.index', open_modal='userModal'))

@bp.route('/guncelle-kullanici', methods=['POST'])
@login_required
def guncelle_kullanici():
    if session.get('rol') != 'admin': return redirect(url_for('main.index'))
    
    u_id = request.form.get('user_id')
    user = Kullanici.query.get(u_id)
    
    if user:
        # Admin kendisi dışında kimseyi admin yapamaz (güvenlik)
        rol = request.form.get('rol')
        try: yetki = int(request.form.get('yetki_duzeyi', 0))
        except: yetki = 0
        
        if (rol == 'admin' or yetki >= 3) and user.kullanici_adi != 'admin':
             flash("Yetki yükseltme engellendi.", "danger")
             return redirect(url_for('main.index', open_modal='userModal'))

        user.ad_soyad = request.form.get('ad_soyad')
        user.kullanici_adi = request.form.get('kullanici_adi')
        user.rol = rol
        user.birim = request.form.get('birim')
        user.yetki_duzeyi = yetki
        
        sifre = request.form.get('sifre')
        if sifre and sifre.strip() != "":
            user.set_password(sifre)
            
        db.session.commit()
        log_kaydet("Kullanıcı Güncellendi", f"{user.kullanici_adi}", "Düzenleme")
        flash("Kullanıcı güncellendi.", "success")
        
    return redirect(url_for('main.index', open_modal='userModal'))

@bp.route('/sil-kullanici/<int:id>')
@login_required
def sil_kullanici(id):
    if session.get('rol') != 'admin': return redirect(url_for('main.index'))
    
    user = Kullanici.query.get(id)
    if user:
        # Admin kendisini silemez
        if user.kullanici_adi == 'admin':
            flash("Ana yönetici silinemez!", "danger")
        else:
            db.session.delete(user)
            db.session.commit()
            log_kaydet("Kullanıcı Silindi", f"{user.kullanici_adi}", "Silme")
            flash("Kullanıcı silindi.", "warning")
            
    return redirect(url_for('main.index', open_modal='userModal'))