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
            dosya_adi=baslik, 
            hedef_konum=detay, 
            tur=tur, 
            tarih=datetime.now().strftime("%d-%m-%Y %H:%M"),
            # session yerine current_user kullanmak daha güvenlidir
            islem_yapan=current_user.ad_soyad if current_user.is_authenticated else "Sistem"
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"LOG HATASI: {e}") #pass eğer uygulama bitmişse

# --- ARIZA İŞLEMLERİ ---

@bp.route('/ekle-ariza', methods=['POST'])
@login_required
def ekle_ariza():
    konum = request.form.get('konum')
    baslik = request.form.get('baslik')
    aciklama = request.form.get('aciklama')
    bildiren = request.form.get('bildiren')
    oncelik = request.form.get('oncelik')
    d_id = request.form.get('demirbas_id') 

    yeni_ariza = Ariza(
        konum=konum,
        baslik=baslik,
        aciklama=aciklama,
        bildiren=bildiren,
        durum="Bekliyor",
        oncelik=oncelik,
        demirbas_id=d_id, 
        tarih=datetime.now().strftime("%d-%m-%Y %H:%M")
    )

    db.session.add(yeni_ariza)
    db.session.commit()
    
    log_kaydet(f"Yeni Arıza Kaydı: {baslik}", f"Konum: {konum}", "Arıza")
    
    flash("Arıza kaydı oluşturuldu.", "success")
    return redirect(url_for('main.index', tab='ariza'))

@bp.route('/guncelle-ariza-durum', methods=['POST'])
@login_required
def guncelle_ariza_durum():
    if not current_user.rol in ['teknik', 'admin']:
        return "Yetkisiz işlem", 403

    try:
        ariza_id = request.form.get('id')
        yeni_durum = request.form.get('durum')
        aciklama_notu = request.form.get('aciklama')
        
        ariza = Ariza.query.get(ariza_id)
        if ariza:
            eski_durum = ariza.durum
            if eski_durum == yeni_durum:
                # JavaScript fetch kullandığı için JSON veya sade metin dönebiliriz
                return "Değişiklik yok", 200

            ariza.durum = yeni_durum
            ariza.islem_yapan = current_user.ad_soyad
            
            if aciklama_notu:
                mevcut_aciklama = ariza.cozum if ariza.cozum else ""
                zaman = datetime.now().strftime("%d-%m %H:%M")
                ariza.cozum = f"{mevcut_aciklama} \n[{zaman}] {yeni_durum}: {aciklama_notu}"

            db.session.commit()
            
            log_mesaji = f"Durum: {eski_durum} -> {yeni_durum}"
            if aciklama_notu:
                log_mesaji += f" (Not: {aciklama_notu})"
                
            log_kaydet(log_mesaji, f"Arıza ID: {ariza_id}", "Arıza")

            # FETCH İSTEĞİ OLDUĞU İÇİN BURADA REDIRECT DEĞİL, ONAY DÖNÜYORUZ
            return "Başarılı", 200
        else:
            return "Arıza bulunamadı", 404
    except Exception as e:
        db.session.rollback()
        return str(e), 500

@bp.route('/sil-ariza/<int:id>')
@login_required
def sil_ariza(id):
    # DÜZELTME: 'teknik' rolünü buradan kaldırdık. Sadece 'admin' silebilir.
    if current_user.rol != 'admin':
        flash("Bu işlem için yetkiniz yok. Sadece yönetici silebilir.", "danger")
        return redirect(url_for('main.index', tab='ariza'))
        
    ariza = Ariza.query.get(id)
    if ariza:
        baslik_yedek = ariza.baslik
        db.session.delete(ariza)
        db.session.commit()
        log_kaydet(f"Arıza Silindi: {baslik_yedek}", f"ID: {id}", "Arıza")
        flash("Arıza silindi.", "warning")
        
    return redirect(url_for('main.index', tab='ariza'))

@bp.route('/toplu-sil-ariza', methods=['POST'])
@login_required
def toplu_sil_ariza():
    if current_user.rol != 'teknik' and current_user.rol != 'admin':
        return redirect(url_for('main.index', tab='ariza'))
        
    ids = request.form.getlist('secilen_ids')
    if ids:
        count = len(ids)
        Ariza.query.filter(Ariza.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        
        log_kaydet(f"Toplu Arıza Silme ({count} Kayıt)", f"Silinen ID'ler: {', '.join(ids)}", "Arıza")
        
        flash(f"{count} arıza başarıyla silindi.", "success")
        
    return redirect(url_for('main.index', tab='ariza'))