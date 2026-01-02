# app/maintenance/routes.py

from flask import redirect, url_for, request, session, flash
from app.maintenance import bp
from app import db
from app.models import Ariza, Demirbas, YuklemeGecmisi
from flask_login import login_required, current_user
from app.utils import turkce_normalize
from datetime import datetime

# --- LOG FONKSİYONU ---
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

# --- ARIZA İŞLEMLERİ ---

# app/maintenance/routes.py - ekle_ariza fonksiyonu

@bp.route('/ekle-ariza', methods=['POST'])
@login_required
def ekle_ariza():
    # 1. Formdan verileri al
    konum = request.form.get('konum')
    baslik = request.form.get('baslik')
    aciklama = request.form.get('aciklama')
    bildiren = request.form.get('bildiren')
    oncelik = request.form.get('oncelik')
    
    # "d_id" değişkenini burada tanımlıyoruz (Hatayı çözen kısım)
    d_id = request.form.get('demirbas_id') 

    # 2. Veritabanı Nesnesi Oluştur
    yeni_ariza = Ariza(
        konum=konum,
        baslik=baslik,
        aciklama=aciklama,
        bildiren=bildiren,
        durum="Bekliyor",
        oncelik=oncelik,
        
        # Sadece bir kere yazılıyor:
        demirbas_id=d_id, 
        
        tarih=datetime.now().strftime("%d-%m-%Y %H:%M")
    )

    db.session.add(yeni_ariza)
    db.session.commit()
    
    flash("Arıza kaydı oluşturuldu.", "success")
    return redirect(url_for('main.index', tab='ariza'))

@bp.route('/guncelle-ariza-durum/<int:id>/<durum_kodu>')
@login_required
def guncelle_ariza_durum(id, durum_kodu):
    if session.get('rol') not in ['teknik', 'admin']:
        return redirect(url_for('main.index', tab='ariza'))
        
    ariza = Ariza.query.get(id)
    if not ariza: return redirect(url_for('main.index', tab='ariza'))
    
    yeni_durum = ""
    if durum_kodu == 'islem': yeni_durum = "İşlemde"
    elif durum_kodu == 'tamam': yeni_durum = "Tamamlandı"
    else: return redirect(url_for('main.index', tab='ariza'))
    
    islem_yapan = session.get('ad_soyad', 'Yetkili')
    
    ariza.durum = yeni_durum
    ariza.islem_yapan = islem_yapan
    
    db.session.commit()
    log_kaydet(f"Arıza Durumu: {yeni_durum}", f"ID: {id}", "Arıza")
    
    return redirect(request.referrer or url_for('main.index', tab='ariza'))

@bp.route('/iptal-et-ariza', methods=['POST'])
@login_required
def iptal_et_ariza():
    if session.get('rol') not in ['teknik', 'admin']: return redirect(url_for('main.index'))
    
    a_id = request.form.get('ariza_id')
    neden = request.form.get('iptal_nedeni')
    
    ariza = Ariza.query.get(a_id)
    if ariza:
        ariza.durum = "İptal Edildi"
        ariza.iptal_nedeni = neden
        ariza.islem_yapan = session.get('ad_soyad')
        db.session.commit()
        
    return redirect(url_for('main.index', tab='ariza'))

@bp.route('/sil-ariza/<int:id>')
@login_required
def sil_ariza(id):
    if session.get('rol') != 'teknik' and int(session.get('yetki_duzeyi', 0)) < 3:
        flash("Yetkisiz işlem.", "danger")
        return redirect(url_for('main.index', tab='ariza'))
        
    ariza = Ariza.query.get(id)
    if ariza:
        db.session.delete(ariza)
        db.session.commit()
        flash("Arıza silindi.", "warning")
        
    return redirect(url_for('main.index', tab='ariza'))

@bp.route('/toplu-sil-ariza', methods=['POST'])
@login_required
def toplu_sil_ariza():
    if session.get('rol') != 'teknik' and int(session.get('yetki_duzeyi', 0)) < 3:
        return redirect(url_for('main.index', tab='ariza'))
        
    ids = request.form.getlist('secilen_ids')
    if ids:
        Ariza.query.filter(Ariza.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        flash(f"{len(ids)} arıza silindi.", "success")
        
    return redirect(url_for('main.index', tab='ariza'))