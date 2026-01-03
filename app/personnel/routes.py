# app/personnel/routes.py

import openpyxl
from flask import redirect, url_for, request, session, flash, render_template
from app.personnel import bp
from app import db
from app.models import Personel, YuklemeGecmisi, Demirbas
from flask_login import login_required, current_user
from app.utils import tr_upper, format_telefon, turkce_normalize
from datetime import datetime

# --- LOG FONKSİYONU ---
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
    except: pass

# --- EXCEL YÜKLEME ---
@bp.route('/yukle-personel', methods=['POST'])
@login_required
def yukle_personel():
    if 'dosya' not in request.files: return redirect(url_for('main.index'))
    dosya = request.files['dosya']
    
    if dosya and dosya.filename != '':
        try:
            wb = openpyxl.load_workbook(dosya)
            ws = wb.active
            eklenen_sayisi = 0
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or row[0] is None: continue
                
                # Excel Sütunları: 0:Ad, 1:Ünvan, 2:Birim, 3:Kampüs, 4:Ofis, 5:Telefon, 6:Email
                ad_soyad = row[0]
                unvan = row[1] if len(row) > 1 else ""
                birim = row[2] if len(row) > 2 else ""
                kampus = row[3] if len(row) > 3 and row[3] else "Merkez"
                ofis = row[4] if len(row) > 4 else ""
                
                # Telefon ve Email (Hata düzeltmeleriyle)
                raw_tel = str(row[5]) if len(row) > 5 and row[5] else ""
                telefon = format_telefon(raw_tel) # utils'den gelen fonksiyon
                
                email = row[6] if len(row) > 6 and row[6] else ""
                
                # Mükerrer Kontrol (ORM)
                mevcut = Personel.query.filter_by(ad_soyad=ad_soyad, ofis=ofis).first()
                
                if not mevcut:
                    yeni_p = Personel(
                        ad_soyad=ad_soyad, unvan=unvan, birimi=birim,
                        kampus=kampus, ofis=ofis, telefon=telefon, email=email
                    )
                    db.session.add(yeni_p)
                    eklenen_sayisi += 1
            
            if eklenen_sayisi > 0:
                db.session.commit()
                log_kaydet("Personel Listesi Yüklendi", f"{eklenen_sayisi} Kişi Eklendi", "Yükleme")
                flash(f"{eklenen_sayisi} personel başarıyla yüklendi.", "success")
            else:
                flash("Yeni personel bulunamadı.", "warning")
                
        except Exception as e:
            flash(f"Hata: {str(e)}", "danger")
            
    return redirect(url_for('main.index', tab='personel'))

# --- CRUD İŞLEMLERİ ---

@bp.route('/ekle-personel', methods=['POST'])
@login_required
def ekle_personel():
    ad_soyad = request.form.get('ad_soyad')
    unvan = request.form.get('unvan')
    birimi = request.form.get('birimi')
    kampus = request.form.get('kampus')
    ofis = request.form.get('ofis')
    telefon = request.form.get('telefon')
    
    # Email oluşturma (Prefix + Domain)
    email_prefix = request.form.get('email_prefix')
    email = f"{email_prefix}@avrasya.edu.tr" if email_prefix else ""

    # Veritabanı Nesnesi
    yeni_p = Personel(
        ad_soyad=ad_soyad, # <--- DÜZELTİLDİ (Direkt gelen veriyi kaydet)
        unvan=unvan,
        birimi=birimi,
        kampus=kampus,
        ofis=ofis,
        email=email,
        telefon=telefon
    )
    
    db.session.add(yeni_p)
    db.session.commit()
    
    flash("Personel eklendi.", "success")
    return redirect(url_for('main.index', tab='personel'))

@bp.route('/guncelle-personel', methods=['POST'])
@login_required
def guncelle_personel():
    p_id = request.form.get('id')
    personel = Personel.query.get(p_id)
    
    if personel:
        personel.ad_soyad = request.form.get('ad_soyad')
        personel.unvan = request.form.get('unvan')
        personel.birimi = request.form.get('birimi')
        personel.kampus = request.form.get('kampus')
        personel.ofis = request.form.get('ofis')
        personel.email = request.form.get('email')
        personel.telefon = format_telefon(request.form.get('telefon'))
        
        db.session.commit()
        log_kaydet(f"{personel.ad_soyad} Güncellendi", f"Ofis: {personel.ofis}", "Düzenleme")
        flash("Personel güncellendi.", "success")
        
    return redirect(url_for('main.index', tab='personel'))

@bp.route('/sil-personel/<int:id>')
@login_required
def sil_personel(id):
    if int(session.get('yetki_duzeyi', 0)) < 3: return redirect(url_for('main.index', tab='personel'))
    
    personel = Personel.query.get(id)
    if personel:
        log_kaydet(f"{personel.ad_soyad} Silindi", f"Ofis: {personel.ofis}", "Silme")
        db.session.delete(personel)
        db.session.commit()
        flash("Personel silindi.", "warning")
        
    return redirect(url_for('main.index', tab='personel'))

@bp.route('/sifirla-personel')
@login_required
def sifirla_personel():
    if int(session.get('yetki_duzeyi', 0)) < 3: return redirect(url_for('main.index'))
    
    try:
        db.session.query(Personel).delete()
        db.session.commit()
        log_kaydet("Tüm Personel Listesi Silindi", "Veritabanı Sıfırlama", "Sıfırlama")
        flash("Personel listesi sıfırlandı.", "danger")
    except:
        db.session.rollback()
        
    return redirect(url_for('main.index', tab='personel'))

# --- TOPLU İŞLEMLER ---

@bp.route('/toplu-sil-personel', methods=['POST'])
@login_required
def toplu_sil_personel():
    if session.get('rol') != 'admin': return redirect(url_for('main.index', tab='personel'))
    
    ids = request.form.getlist('secilen_ids')
    if ids:
        Personel.query.filter(Personel.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        flash(f"{len(ids)} personel silindi.", "success")
        
    return redirect(url_for('main.index', tab='personel'))

@bp.route('/toplu-tasi-personel', methods=['POST'])
@login_required
def toplu_tasi_personel():
    if int(session.get('yetki_duzeyi', 0)) < 1: return redirect(url_for('main.index', tab='personel'))
    
    ids = request.form.getlist('secilen_ids')
    yeni_birim = request.form.get('yeni_birim')
    yeni_kampus = request.form.get('yeni_kampus')
    yeni_ofis = request.form.get('yeni_ofis')
    
    if ids:
        query = Personel.query.filter(Personel.id.in_(ids))
        for p in query.all():
            p.ofis = yeni_ofis
            if yeni_birim: p.birimi = yeni_birim
            if yeni_kampus: p.kampus = yeni_kampus
            
        db.session.commit()
        flash(f"{len(ids)} personel taşındı.", "success")
        
    return redirect(url_for('main.index', tab='personel'))

# --- PERSONEL DETAY VE ZİMMET GÖRÜNTÜLEME ---
@bp.route('/personel-detay/<int:id>')
@login_required
def personel_detay(id):
    kisi = Personel.query.get_or_404(id)
    
    # Aynı ofisteki arkadaşları
    arkadaslar = Personel.query.filter(Personel.ofis == kisi.ofis, Personel.id != id).all()
    
    # Zimmet Mantığı (Ofis eşleşmesiyle çalışıyor şimdilik)
    # ORM'de LIKE sorgusu için .like() kullanıyoruz
    k_ofis = kisi.ofis.replace('i', 'İ').upper() # Basit bir normalize (Geliştirilebilir)
    
    esyalar = Demirbas.query.filter(Demirbas.konum.contains(kisi.ofis)).all()
    
    return render_template('personel_detay.html', kisi=kisi, arkadaslar=arkadaslar, esyalar=esyalar)

@bp.route('/tasi-personel', methods=['POST'])
@login_required
def tasi_personel():
    p_id = request.form.get('personel_id')
    yeni_kampus = request.form.get('yeni_kampus')
    yeni_ofis = request.form.get('yeni_ofis')
    
    personel = Personel.query.get(p_id)
    
    if personel:
        eski_yer = f"{personel.kampus}/{personel.ofis}"
        
        personel.kampus = yeni_kampus
        personel.ofis = yeni_ofis
        
        db.session.commit()
        
        log_kaydet(f"{personel.ad_soyad} Taşındı", f"{eski_yer} -> {yeni_kampus}/{yeni_ofis}", "Taşıma")
        flash("Personel başarıyla taşındı.", "success")
        
    return redirect(url_for('main.index', tab='personel'))